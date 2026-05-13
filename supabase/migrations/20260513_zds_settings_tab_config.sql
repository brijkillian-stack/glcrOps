-- ZDS Settings table — generic key/value JSON store for Control Panel config.
-- First use: task_tab_config (configurable task picker tabs in the day planner).
-- Applied 2026-05-13 via Supabase MCP.

CREATE TABLE IF NOT EXISTS public.zds_settings (
  key        TEXT        PRIMARY KEY,
  value      JSONB       NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the default tab config (mirrors the hardcoded CATEGORY_TABS constant).
INSERT INTO public.zds_settings (key, value)
VALUES (
  'task_tab_config',
  '[
    {"id": "zone",  "label": "Zone",  "cats": ["zone", "rr", "aux"]},
    {"id": "sweep", "label": "Sweep", "cats": ["sweep"]},
    {"id": "am",    "label": "AM",    "cats": ["overlap_am"]},
    {"id": "pm",    "label": "PM",    "cats": ["overlap_pm"]}
  ]'::jsonb
)
ON CONFLICT (key) DO NOTHING;

-- Auto-update updated_at on every write.
CREATE OR REPLACE FUNCTION public.zds_settings_touch()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS zds_settings_touch ON public.zds_settings;
CREATE TRIGGER zds_settings_touch
  BEFORE UPDATE ON public.zds_settings
  FOR EACH ROW EXECUTE PROCEDURE public.zds_settings_touch();
