-- ============================================================================
-- Migration 3: Engine config tables
-- Purpose:   Replace the smaller Rules/*.json files with normalized tables.
-- Source:    Slot Difficulty.json, Slot Load Scores.json, Scorecard Weights.json,
--            Overlap Tasks.json, Utility Porters.json, Training Config.json,
--            zone_geometry.json
-- Date:      2026-05-05
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. SLOT_DIFFICULTY
-- ----------------------------------------------------------------------------
CREATE TABLE public.slot_difficulty (
    slot_id     text PRIMARY KEY REFERENCES public.slots(slot_id),
    difficulty  smallint NOT NULL CHECK (difficulty BETWEEN 1 AND 10),
    notes       text,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.slot_difficulty IS
  'Per-slot difficulty 1-10. Source: GLCR/Rules/Slot Difficulty.json.';

-- ----------------------------------------------------------------------------
-- 2. SLOT_LOAD_SCORES — fatigue load + global tuning constants
-- ----------------------------------------------------------------------------
CREATE TABLE public.slot_load_scores (
    slot_id     text PRIMARY KEY REFERENCES public.slots(slot_id),
    load        smallint NOT NULL CHECK (load BETWEEN 1 AND 5),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.slot_load_config (
    id                       smallint PRIMARY KEY CHECK (id = 1),
    sweeper_tag_bonus        smallint NOT NULL DEFAULT 2,
    training_role_bonus      jsonb NOT NULL DEFAULT '{"trainer":1,"trainee":1}'::jsonb,
    updated_at               timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.slot_load_config IS
  'Global load tuning constants. Single-row config (id=1).';

-- ----------------------------------------------------------------------------
-- 3. SCORECARD_CONFIG — single-row Scorecard Weights.json
-- ----------------------------------------------------------------------------
CREATE TABLE public.scorecard_config (
    id                                  smallint PRIMARY KEY CHECK (id = 1),
    weights                             jsonb NOT NULL,
    hard_preference_override_severity   text NOT NULL DEFAULT 'warning',
    fatigue_index_window_days           int NOT NULL DEFAULT 7,
    fatigue_threshold                   jsonb NOT NULL,
    pair_affinity_check_scope           text[] NOT NULL DEFAULT ARRAY[]::text[],
    notes                               text,
    updated_at                          timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.scorecard_config IS
  'Scorecard tuning. Single row (id=1). Source: GLCR/Rules/Scorecard Weights.json.';

-- ----------------------------------------------------------------------------
-- 4. OVERLAP_TASKS — canonical AM/PM task→slot map
-- ----------------------------------------------------------------------------
CREATE TABLE public.overlap_tasks (
    period      text NOT NULL CHECK (period IN ('AM','PM')),
    slot_id     text NOT NULL REFERENCES public.slots(slot_id),
    task        text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (period, slot_id)
);
COMMENT ON TABLE public.overlap_tasks IS
  'Canonical AM/PM Overlap task assignments by slot. The task is fixed per slot; the person rotates.';

-- ----------------------------------------------------------------------------
-- 5. OVERLAP_TASK_OVERRIDES — per-day deviations
-- ----------------------------------------------------------------------------
CREATE TABLE public.overlap_task_overrides (
    override_date  date NOT NULL,
    period         text NOT NULL CHECK (period IN ('AM','PM')),
    slot_id        text NOT NULL REFERENCES public.slots(slot_id),
    task           text NOT NULL,
    note           text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (override_date, period, slot_id)
);

-- ----------------------------------------------------------------------------
-- 6. UTILITY_PORTERS — daily utility porter assignments (1-8 per date)
-- ----------------------------------------------------------------------------
CREATE TABLE public.utility_porters (
    porter_date  date NOT NULL,
    position     smallint NOT NULL CHECK (position BETWEEN 1 AND 8),
    role         text CHECK (role IN ('AM','PM','')) ,
    name         text,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (porter_date, position)
);

CREATE INDEX utility_porters_date_idx ON public.utility_porters (porter_date);

-- ----------------------------------------------------------------------------
-- 7. TRAINING_SCHEDULE — active training pairs (Day 1-6)
-- ----------------------------------------------------------------------------
CREATE TABLE public.training_schedule (
    training_date  date NOT NULL,
    trainee_id     text NOT NULL REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    day_number     smallint NOT NULL CHECK (day_number BETWEEN 1 AND 6),
    trainer_id     text REFERENCES public.tm_profiles(tm_id) ON DELETE SET NULL,
    status         text NOT NULL DEFAULT 'scheduled'
                       CHECK (status IN ('scheduled','completed','cancelled','no_show')),
    notes          text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (training_date, trainee_id)
);

CREATE INDEX training_schedule_trainee_idx ON public.training_schedule (trainee_id, training_date DESC);
CREATE INDEX training_schedule_trainer_idx ON public.training_schedule (trainer_id, training_date DESC);

-- ----------------------------------------------------------------------------
-- 8. ZONE_GEOMETRY — single-row JSONB blob (static map data)
-- ----------------------------------------------------------------------------
CREATE TABLE public.zone_geometry (
    id          smallint PRIMARY KEY CHECK (id = 1),
    geometry    jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.zone_geometry IS
  'Static casino floor geometry. Single row (id=1). Source: GLCR/Rules/zone_geometry.json.';

-- ----------------------------------------------------------------------------
-- 9. RLS — service-role-only
-- ----------------------------------------------------------------------------
ALTER TABLE public.slot_difficulty         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.slot_load_scores        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.slot_load_config        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scorecard_config        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.overlap_tasks           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.overlap_task_overrides  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.utility_porters         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_schedule       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.zone_geometry           ENABLE ROW LEVEL SECURITY;
