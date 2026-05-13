-- Add reporting fields to zone_tasks.
-- All new columns are nullable with sensible defaults so existing rows are unaffected.
-- Applied 2026-05-13 via Supabase MCP.

ALTER TABLE public.zone_tasks
  ADD COLUMN IF NOT EXISTS labor_category         TEXT     DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS is_compliance_required  BOOLEAN  NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS frequency              TEXT     DEFAULT 'once_per_shift',
  ADD COLUMN IF NOT EXISTS shift_phase            TEXT     DEFAULT 'all';

-- Partial indexes for common reporting queries
CREATE INDEX IF NOT EXISTS zone_tasks_compliance_idx
  ON public.zone_tasks (is_compliance_required)
  WHERE active = TRUE AND is_compliance_required = TRUE;

CREATE INDEX IF NOT EXISTS zone_tasks_labor_cat_idx
  ON public.zone_tasks (labor_category)
  WHERE active = TRUE AND labor_category IS NOT NULL;

COMMENT ON COLUMN public.zone_tasks.labor_category IS
  'cleaning | inspection | coverage | compliance | security | other';
COMMENT ON COLUMN public.zone_tasks.frequency IS
  'once_per_shift | ongoing | as_needed';
COMMENT ON COLUMN public.zone_tasks.shift_phase IS
  'all | opening | mid_shift | closing';
