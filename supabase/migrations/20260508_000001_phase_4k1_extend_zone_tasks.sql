-- Phase 4k.1 · Step 1: Extend zone_tasks + create task_day_overrides
-- Applied 2026-05-08 via Supabase MCP apply_migration.
-- description and notes already exist from Phase 4i — IF NOT EXISTS guards.

ALTER TABLE public.zone_tasks
  ADD COLUMN IF NOT EXISTS code             TEXT,
  ADD COLUMN IF NOT EXISTS target_codes     TEXT[]  NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS days_active      TEXT[]  NOT NULL DEFAULT ARRAY['fri','sat','sun','mon','tue','wed','thu'],
  ADD COLUMN IF NOT EXISTS display_order    INT     NOT NULL DEFAULT 100;

-- Partial unique index on code (allows multiple NULL codes)
CREATE UNIQUE INDEX IF NOT EXISTS zone_tasks_code_uniq
  ON public.zone_tasks (code)
  WHERE code IS NOT NULL;

-- GIN index for target_codes array containment queries
CREATE INDEX IF NOT EXISTS zone_tasks_target_codes_gin
  ON public.zone_tasks USING GIN (target_codes);

-- Partial index for active tasks by kind (category)
CREATE INDEX IF NOT EXISTS zone_tasks_kind_idx
  ON public.zone_tasks (category)
  WHERE active = TRUE AND archived_at IS NULL;

-- Backfill target_codes from default_zone for existing Phase 4i rows
UPDATE public.zone_tasks
  SET target_codes = ARRAY[default_zone]
  WHERE target_codes = '{}'
    AND default_zone IS NOT NULL;

-- Sibling table: per-day task description overrides
CREATE TABLE IF NOT EXISTS public.task_day_overrides (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id         UUID        NOT NULL REFERENCES public.zone_tasks(id) ON DELETE CASCADE,
  override_date   DATE        NOT NULL,
  description     TEXT        NOT NULL,
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (task_id, override_date)
);

CREATE INDEX IF NOT EXISTS task_day_overrides_date_idx
  ON public.task_day_overrides (override_date);
