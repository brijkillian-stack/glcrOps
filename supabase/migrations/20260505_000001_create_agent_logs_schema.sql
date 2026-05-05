-- ============================================================================
-- Migration: create agent_logs schema + sessions + actions
-- Purpose:   Cross-agent sync substrate. Every meaningful action by Opus,
--            Sonnet, or Haiku gets logged here so the next agent (or the
--            same one on the next turn) can read the table and catch up.
--            See webapp-delegation skill for the read/write protocol.
-- Date:      2026-05-05
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS agent_logs;

COMMENT ON SCHEMA agent_logs IS
  'Cross-agent action log. Read on session start, write on every meaningful action. Consumed by the webapp-delegation skill.';

-- ----------------------------------------------------------------------------
-- agent_logs.sessions
--   One row per delegation chain. The orchestrator (Opus) creates a session
--   when starting orchestrated work; spawned agents inherit the session_id.
-- ----------------------------------------------------------------------------
CREATE TABLE agent_logs.sessions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    initiated_by  text NOT NULL CHECK (initiated_by IN ('opus','sonnet','haiku','user')),
    title         text NOT NULL,
    status        text NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active','completed','aborted')),
    context       jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at    timestamptz NOT NULL DEFAULT now(),
    ended_at      timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE agent_logs.sessions IS
  'One row per delegation chain. Spawned agents inherit session_id from the orchestrator.';
COMMENT ON COLUMN agent_logs.sessions.context IS
  'Free-form orchestration context. Typically holds the original user request and any constraints the orchestrator wants downstream agents to know.';

CREATE INDEX sessions_status_started_idx
    ON agent_logs.sessions (status, started_at DESC);

-- ----------------------------------------------------------------------------
-- agent_logs.actions
--   One row per meaningful action. "Meaningful" = decisions, file writes,
--   spawns, handoffs, deliberate tool calls. NOT every Read/Grep — only
--   actions whose absence would leave the next agent confused.
-- ----------------------------------------------------------------------------
CREATE TABLE agent_logs.actions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     uuid NOT NULL REFERENCES agent_logs.sessions(id) ON DELETE CASCADE,
    parent_id      uuid REFERENCES agent_logs.actions(id) ON DELETE SET NULL,
    agent          text NOT NULL CHECK (agent IN ('opus','sonnet','haiku')),
    agent_role     text,                          -- 'exec' | 'implementer' | 'searcher' | freeform
    action_type    text NOT NULL CHECK (action_type IN (
                       'read',          -- read a file/table/resource for context
                       'write',         -- created/edited a file
                       'migration',     -- applied a DB migration
                       'sql',           -- ran a query that mattered
                       'spawn',         -- spawned/handed-off to another agent
                       'handoff',       -- explicit handoff with context
                       'decision',      -- recorded a design/architecture call
                       'tool_call',     -- significant external tool usage
                       'note'           -- freeform sync note for next agent
                   )),
    target         text,                           -- file path, table, URL, tool, etc.
    summary        text NOT NULL,                  -- one-liner of what was done
    payload        jsonb NOT NULL DEFAULT '{}'::jsonb,  -- inputs (truncate large)
    result         jsonb NOT NULL DEFAULT '{}'::jsonb,  -- outputs / what changed
    notes          text,                           -- "next agent should know X"
    status         text NOT NULL DEFAULT 'success'
                       CHECK (status IN ('pending','success','error')),
    started_at     timestamptz NOT NULL DEFAULT now(),
    completed_at   timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE agent_logs.actions IS
  'One row per meaningful agent action. Read on session start; write on every action. See webapp-delegation skill for protocol.';
COMMENT ON COLUMN agent_logs.actions.parent_id IS
  'Set when one action directly caused another (e.g. an opus spawn -> sonnet implementer chain).';
COMMENT ON COLUMN agent_logs.actions.notes IS
  'Free-form sync notes. The single most important field: "what does the next agent need to know?"';

-- Indexes for the common access patterns:
--   1. "Catch me up on this session"          -> (session_id, started_at DESC)
--   2. "What has Sonnet been doing"           -> (agent, started_at DESC)
--   3. "All decisions in this session"        -> (session_id, action_type)
--   4. "Children of action X"                 -> (parent_id)
CREATE INDEX actions_session_started_idx
    ON agent_logs.actions (session_id, started_at DESC);
CREATE INDEX actions_agent_started_idx
    ON agent_logs.actions (agent, started_at DESC);
CREATE INDEX actions_session_type_idx
    ON agent_logs.actions (session_id, action_type);
CREATE INDEX actions_parent_idx
    ON agent_logs.actions (parent_id) WHERE parent_id IS NOT NULL;

-- ----------------------------------------------------------------------------
-- Convenience view: last 50 actions per active session, newest first.
-- This is what every spawned agent SELECTs as its first read.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW agent_logs.recent_actions AS
SELECT a.id,
       a.session_id,
       s.title          AS session_title,
       s.status         AS session_status,
       a.parent_id,
       a.agent,
       a.agent_role,
       a.action_type,
       a.target,
       a.summary,
       a.notes,
       a.status,
       a.started_at,
       a.completed_at
  FROM agent_logs.actions a
  JOIN agent_logs.sessions s ON s.id = a.session_id
 ORDER BY a.started_at DESC;

COMMENT ON VIEW agent_logs.recent_actions IS
  'Default catch-up view. SELECT * FROM agent_logs.recent_actions WHERE session_id = $1 LIMIT 50.';

-- ----------------------------------------------------------------------------
-- RLS: enable on both tables, service-role-only by default.
-- Authenticated reads can be added later when the Brain app surfaces this.
-- ----------------------------------------------------------------------------
ALTER TABLE agent_logs.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs.actions  ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS by default in Supabase, so no SELECT/INSERT
-- policies are required for the agents (which use the service key).
-- Explicitly DENY all access to anon / authenticated roles for now:
CREATE POLICY agent_logs_sessions_no_anon
    ON agent_logs.sessions
    FOR ALL
    TO anon, authenticated
    USING (false)
    WITH CHECK (false);

CREATE POLICY agent_logs_actions_no_anon
    ON agent_logs.actions
    FOR ALL
    TO anon, authenticated
    USING (false)
    WITH CHECK (false);

-- ----------------------------------------------------------------------------
-- Grants: service_role gets full access (it bypasses RLS but USAGE on the
-- schema must still be granted explicitly).
-- ----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA agent_logs TO service_role;
GRANT ALL   ON ALL TABLES    IN SCHEMA agent_logs TO service_role;
GRANT ALL   ON ALL SEQUENCES IN SCHEMA agent_logs TO service_role;
GRANT SELECT ON agent_logs.recent_actions TO service_role;
