-- Phase 2: Role-based Access Control — placements RLS + role helpers
-- Created: 2026-05-12
--
-- Access model:
--   Full access  (graves_ops_super, sudo_admin) → all CRUD on all data
--   Restricted   (all other roles)              → SELECT-only on published nights

-- ── Role helper functions ─────────────────────────────────────────────────────

-- Returns the role of the currently authenticated user.
-- SECURITY DEFINER so it can read the users table even under restrictive policies.
CREATE OR REPLACE FUNCTION current_user_role()
RETURNS user_role
LANGUAGE SQL
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT role FROM users WHERE id = auth.uid()
$$;

-- Returns true if the current user has full application access.
CREATE OR REPLACE FUNCTION user_has_full_access()
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT COALESCE(
    (SELECT role FROM users WHERE id = auth.uid()) IN ('graves_ops_super', 'sudo_admin'),
    false
  )
$$;

-- ── placements RLS policies ───────────────────────────────────────────────────
-- RLS was enabled in Phase 1 but no policies were added, so placements were
-- inaccessible to non-service-key callers. These policies make the intent
-- explicit and provide defence-in-depth for any future direct-client queries.

-- Full access: read everything
CREATE POLICY "Full access roles can read all placements"
  ON placements FOR SELECT
  USING (user_has_full_access());

-- Restricted roles: read-only, published nights only
-- A night is "published" when its parent week has status = 'published'.
CREATE POLICY "Restricted roles can read published placements"
  ON placements FOR SELECT
  USING (
    NOT user_has_full_access()
    AND EXISTS (
      SELECT 1
      FROM   nights n
      JOIN   weeks  w ON w.id = n.week_id
      WHERE  n.id      = placements.night_id
        AND  w.status  = 'published'
    )
  );

-- Full access: write (insert / update / delete) — restricted roles get nothing
CREATE POLICY "Full access roles can modify placements"
  ON placements FOR ALL
  USING (user_has_full_access())
  WITH CHECK (user_has_full_access());

-- ── weeks RLS policies ────────────────────────────────────────────────────────
-- Weeks table: full access roles see everything; restricted roles see only
-- published weeks (they have no need to see draft or archived scheduling data).

ALTER TABLE weeks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Full access roles can read all weeks"
  ON weeks FOR SELECT
  USING (user_has_full_access());

CREATE POLICY "Restricted roles can read published weeks"
  ON weeks FOR SELECT
  USING (
    NOT user_has_full_access()
    AND status = 'published'
  );

CREATE POLICY "Full access roles can modify weeks"
  ON weeks FOR ALL
  USING (user_has_full_access())
  WITH CHECK (user_has_full_access());

-- ── nights RLS policies ───────────────────────────────────────────────────────

ALTER TABLE nights ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Full access roles can read all nights"
  ON nights FOR SELECT
  USING (user_has_full_access());

CREATE POLICY "Restricted roles can read nights in published weeks"
  ON nights FOR SELECT
  USING (
    NOT user_has_full_access()
    AND EXISTS (
      SELECT 1 FROM weeks w
      WHERE  w.id     = nights.week_id
        AND  w.status = 'published'
    )
  );

CREATE POLICY "Full access roles can modify nights"
  ON nights FOR ALL
  USING (user_has_full_access())
  WITH CHECK (user_has_full_access());

-- ── users table — additional policies ────────────────────────────────────────
-- Phase 1 added SELECT policies; add write policies so admins can manage users.

-- Only sudo_admin can insert / update / delete users
CREATE POLICY "Sudo admin can manage users"
  ON users FOR ALL
  USING (
    (SELECT role FROM users WHERE id = auth.uid()) = 'sudo_admin'
  )
  WITH CHECK (
    (SELECT role FROM users WHERE id = auth.uid()) = 'sudo_admin'
  );

COMMENT ON FUNCTION current_user_role IS 'Phase 2: Returns the role of the authenticated user from the users table';
COMMENT ON FUNCTION user_has_full_access IS 'Phase 2: Returns true for graves_ops_super and sudo_admin roles';
