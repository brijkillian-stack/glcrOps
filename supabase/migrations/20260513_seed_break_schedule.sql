-- Seed break_schedule into zds_settings.
-- Shape mirrors the BREAK_TIMES / WAVE_LABELS constants in the frontend.
-- Applied 2026-05-13 via Supabase MCP.

INSERT INTO public.zds_settings (key, value)
VALUES (
  'break_schedule',
  '{
    "wave_labels": {"1": "First Break", "2": "Main Break", "3": "Last Break"},
    "times": {
      "1": {"1": ["00:45", "01:00", 15], "2": ["02:30", "03:00", 30], "3": ["05:00", "05:15", 15]},
      "2": {"1": ["01:00", "01:15", 15], "2": ["03:00", "03:30", 30], "3": ["05:00", "05:15", 15]},
      "3": {"1": ["01:15", "01:30", 15], "2": ["03:30", "04:00", 30], "3": ["05:15", "05:30", 15]}
    }
  }'::jsonb
)
ON CONFLICT (key) DO NOTHING;
