-- Phase 4k.2 · zds_annotations table + updated_at trigger
-- Applied 2026-05-08 via Supabase MCP apply_migration.

CREATE TABLE IF NOT EXISTS public.zds_annotations (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  week_ending     DATE        NOT NULL,
  day             TEXT        NOT NULL CHECK (day IN ('fri','sat','sun','mon','tue','wed','thu')),
  target_kind     TEXT        NOT NULL CHECK (target_kind IN ('task','tm','card')),
  target_ref      TEXT        NOT NULL,
  annotation_kind TEXT        NOT NULL,
  value           JSONB       NOT NULL DEFAULT '{}'::jsonb,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by      TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (week_ending, day, target_kind, target_ref, annotation_kind)
);

CREATE INDEX IF NOT EXISTS zds_annotations_week_day_idx
  ON public.zds_annotations (week_ending, day);

CREATE INDEX IF NOT EXISTS zds_annotations_target_idx
  ON public.zds_annotations (target_kind, target_ref);

CREATE INDEX IF NOT EXISTS zds_annotations_kind_idx
  ON public.zds_annotations (annotation_kind);

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.trigger_set_zds_annotations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS zds_annotations_set_updated_at ON public.zds_annotations;
CREATE TRIGGER zds_annotations_set_updated_at
  BEFORE UPDATE ON public.zds_annotations
  FOR EACH ROW EXECUTE FUNCTION public.trigger_set_zds_annotations_updated_at();
