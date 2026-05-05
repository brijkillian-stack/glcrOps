-- ============================================================================
-- Migration 2: Canonical slot vocabulary + TM domain
-- Purpose:   Replace TM Profiles.json + Eligibility Roster.xlsx with normalized
--            Postgres tables. Adds public.slots as the canonical slot vocabulary
--            (FK target for every other slot reference in the schema).
-- Source:    GLCR/Rules/TM Profiles.json (58 profiles, schema v2.1)
--            GLCR/Rules/Eligibility Roster.xlsx (53 rows × 35 cols)
-- Date:      2026-05-05
-- Decisions: TM keys reconciled against public.entities (text PK matching
--            tm_<key> pattern). Eligibility stored long-form. Strict slot
--            vocabulary. History on tm_profiles + tm_eligibility only.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. SLOTS — canonical vocabulary
--    Every slot reference in the schema points here. Categories taken from
--    the natural groupings in the source files.
-- ----------------------------------------------------------------------------
CREATE TABLE public.slots (
    slot_id       text PRIMARY KEY,
    display_name  text NOT NULL,
    category      text NOT NULL CHECK (category IN (
                      'zone',
                      'restroom_mens',
                      'restroom_womens',
                      'trash',
                      'admin',
                      'multipurpose',
                      'support',
                      'overlap_pm',
                      'overlap_am',
                      'special'
                  )),
    active        boolean NOT NULL DEFAULT true,
    sort_order    int,
    notes         text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.slots IS
  'Canonical slot vocabulary. All slot references in tm_eligibility, slot_difficulty, slot_load_scores, overlap_tasks, etc. FK here.';

-- Seed canonical slot list (matches the keys in Slot Difficulty.json + Load Scores)
INSERT INTO public.slots (slot_id, display_name, category, sort_order) VALUES
  -- Admin
  ('Admin',       'Admin',         'admin',          1),
  -- Zones
  ('Zone1',       'Zone 1',        'zone',          11),
  ('Zone2',       'Zone 2',        'zone',          12),
  ('Zone3',       'Zone 3',        'zone',          13),
  ('Zone4',       'Zone 4',        'zone',          14),
  ('Zone5',       'Zone 5',        'zone',          15),
  ('Zone6',       'Zone 6',        'zone',          16),
  ('Zone7',       'Zone 7',        'zone',          17),
  ('Zone8',       'Zone 8',        'zone',          18),
  ('Zone9',       'Zone 9',        'zone',          19),
  ('Zone10',      'Zone 10',       'zone',          20),
  -- Special
  ('Zone9SR',     'Zone 9 SR',     'special',       21),
  ('Z9SRBuddy',   'Z9 SR Buddy',   'special',       22),
  -- Men's restrooms
  ('MRR1',        'Men''s 1+2',    'restroom_mens', 31),
  ('MRR6',        'Men''s 6',      'restroom_mens', 32),
  ('MRR7',        'Men''s 7',      'restroom_mens', 33),
  ('MRR8',        'Men''s 8',      'restroom_mens', 34),
  ('MRR10',       'Men''s 10',     'restroom_mens', 35),
  -- Women's restrooms
  ('WRR1',        'Women''s 1+2',  'restroom_womens', 41),
  ('WRR6',        'Women''s 6',    'restroom_womens', 42),
  ('WRR7',        'Women''s 7',    'restroom_womens', 43),
  ('WRR8',        'Women''s 8',    'restroom_womens', 44),
  ('WRR10',       'Women''s 10',   'restroom_womens', 45),
  -- Trash
  ('Trash1',      'Trash 1',       'trash',         51),
  ('Trash2',      'Trash 2',       'trash',         52),
  -- Multipurpose
  ('MP1',         'MP 1',          'multipurpose',  61),
  ('MP2',         'MP 2',          'multipurpose',  62),
  -- Support
  ('Support1',    'Support 1',     'support',       71),
  ('Support2',    'Support 2',     'support',       72),
  ('Support3',    'Support 3',     'support',       73),
  -- Overlap PM
  ('PMOL1',       'PM Overlap 1',  'overlap_pm',    81),
  ('PMOL2',       'PM Overlap 2',  'overlap_pm',    82),
  ('PMOL3',       'PM Overlap 3',  'overlap_pm',    83),
  ('PMOL4',       'PM Overlap 4',  'overlap_pm',    84),
  ('PMOL5',       'PM Overlap 5',  'overlap_pm',    85),
  ('PMOL6',       'PM Overlap 6',  'overlap_pm',    86),
  -- Overlap AM
  ('AMOL1',       'AM Overlap 1',  'overlap_am',    91),
  ('AMOL2',       'AM Overlap 2',  'overlap_am',    92),
  ('AMOL3',       'AM Overlap 3',  'overlap_am',    93),
  ('AMOL4',       'AM Overlap 4',  'overlap_am',    94),
  ('AMOL5',       'AM Overlap 5',  'overlap_am',    95),
  ('AMOL6',       'AM Overlap 6',  'overlap_am',    96);

CREATE INDEX slots_category_idx ON public.slots (category, sort_order);

-- ----------------------------------------------------------------------------
-- 2. TM_PROFILES — canonical TM record
--    Combines top-level fields from TM Profiles.json + the metadata columns
--    from Eligibility Roster (Active / Grave Pool / Primary Section / Tie
--    Break Rank / Notes). FK to public.entities — same tm_<key> string.
-- ----------------------------------------------------------------------------
CREATE TABLE public.tm_profiles (
    tm_id            text PRIMARY KEY REFERENCES public.entities(id) ON DELETE CASCADE,
    full_name        text,                    -- TM Profiles.full_name ("Christopher Shepard")
    employee_name    text,                    -- Eligibility "Employee Name" (ADP form)
    display_name     text NOT NULL,           -- Eligibility "Display Name" ("Chris", "Sheri O")
    active           boolean NOT NULL DEFAULT true,
    grave_pool       text,                    -- 'Grave' | 'AM' | 'PM' | 'Day' | …
    primary_section  text,                    -- 'Zone' | 'AM' | 'Admin' | …
    tie_break_rank   int,
    skill_score      numeric(3,1),
    status           text NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active','LOA','transferred','separated','other')),
    status_date      date,                    -- loa_start / transferred_date / separated_date
    status_note      text,                    -- loa_note / separation_note
    slot_preference  text,                    -- legacy field (still honored by engine)
    schema_version   text DEFAULT '2.1',
    notes            text,                    -- Eligibility "Notes" column
    metadata         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.tm_profiles IS
  'Canonical TM record. tm_id matches public.entities.id (tm_<key> pattern).';

CREATE INDEX tm_profiles_active_idx     ON public.tm_profiles (active);
CREATE INDEX tm_profiles_grave_pool_idx ON public.tm_profiles (grave_pool);
CREATE INDEX tm_profiles_status_idx     ON public.tm_profiles (status);

-- ----------------------------------------------------------------------------
-- 3. TM_ELIGIBILITY — long-form (tm × slot × eligible)
-- ----------------------------------------------------------------------------
CREATE TABLE public.tm_eligibility (
    tm_id     text NOT NULL REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    slot_id   text NOT NULL REFERENCES public.slots(slot_id),
    eligible  boolean NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tm_id, slot_id)
);

COMMENT ON TABLE public.tm_eligibility IS
  'Per-TM × per-slot eligibility. Y/N from Eligibility Roster, with category-level columns (PM OL / AM OL) expanded to per-slot rows during ingest.';

CREATE INDEX tm_eligibility_slot_idx ON public.tm_eligibility (slot_id) WHERE eligible = true;

-- ----------------------------------------------------------------------------
-- 4. TM_SCORE_HISTORY — TM Profiles.score_history[]
-- ----------------------------------------------------------------------------
CREATE TABLE public.tm_score_history (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_id        text NOT NULL REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    change_date  date NOT NULL,
    old_score    numeric(3,1),
    new_score    numeric(3,1) NOT NULL,
    reason       text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX tm_score_history_tm_idx ON public.tm_score_history (tm_id, change_date DESC);

-- ----------------------------------------------------------------------------
-- 5. TM_COMMENTS — TM Profiles.comments[]
-- ----------------------------------------------------------------------------
CREATE TABLE public.tm_comments (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_id                   text NOT NULL REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    comment_date            date NOT NULL,
    week_ending             date,
    day                     text,            -- 'Monday', 'Sunday', etc.
    slot_context            text REFERENCES public.slots(slot_id),
    category                text NOT NULL CHECK (category IN (
                                'Performance','Attitude','Physical',
                                'Request','Feedback','Administrative'
                            )),
    sentiment               text NOT NULL CHECK (sentiment IN (
                                'Positive','Negative','Neutral','Flag'
                            )),
    note                    text NOT NULL,
    linked_recommendation   text,
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX tm_comments_tm_date_idx     ON public.tm_comments (tm_id, comment_date DESC);
CREATE INDEX tm_comments_category_idx    ON public.tm_comments (category, sentiment, comment_date DESC);

-- ----------------------------------------------------------------------------
-- 6. TM_ACCOMMODATIONS — TM Profiles.accommodations[] (schema v2.1, 5/3/26)
-- ----------------------------------------------------------------------------
CREATE TABLE public.tm_accommodations (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_id        text NOT NULL REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    type         text NOT NULL CHECK (type IN (
                     'physical','sensory','medical','temporary','other'
                 )),
    severity     text NOT NULL CHECK (severity IN ('soft','hard','absolute')),
    target       text,                              -- nullable; freeform target spec
    note         text NOT NULL,
    added_date   date NOT NULL,
    status       text NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','resolved','review_due')),
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX tm_accommodations_tm_status_idx ON public.tm_accommodations (tm_id, status);

-- ----------------------------------------------------------------------------
-- 7. TM_PREFERENCES — TM Profiles.preferences[]
-- ----------------------------------------------------------------------------
CREATE TABLE public.tm_preferences (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_id           text NOT NULL REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    stance          text NOT NULL CHECK (stance IN ('avoid','prefer')),
    strength        text NOT NULL CHECK (strength IN ('soft','hard')),
    target          text NOT NULL,                  -- 'Zone 8' | 'area:Lobby' | 'category:sweeper' | etc.
    note            text,
    added_date      date,
    last_reviewed   date,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX tm_preferences_tm_idx ON public.tm_preferences (tm_id);

-- ----------------------------------------------------------------------------
-- 8. TM_PAIR_AFFINITIES — TM Profiles.pair_affinities[]
-- ----------------------------------------------------------------------------
CREATE TABLE public.tm_pair_affinities (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_id           text NOT NULL REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    with_tm_id      text REFERENCES public.tm_profiles(tm_id) ON DELETE CASCADE,
    with_label      text,                            -- if the "with" can't be resolved to a tm_id
    stance          text NOT NULL CHECK (stance IN ('avoid','prefer')),
    strength        text NOT NULL CHECK (strength IN ('soft','hard')),
    note            text,
    added_date      date,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (with_tm_id IS NOT NULL OR with_label IS NOT NULL)
);

CREATE INDEX tm_pair_affinities_tm_idx       ON public.tm_pair_affinities (tm_id);
CREATE INDEX tm_pair_affinities_with_tm_idx  ON public.tm_pair_affinities (with_tm_id);

-- ----------------------------------------------------------------------------
-- 9. HISTORY TABLES — JSONB-based audit, one shared shape
-- ----------------------------------------------------------------------------
CREATE TABLE public.tm_profiles_history (
    change_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_id        text NOT NULL,
    change_type  text NOT NULL CHECK (change_type IN ('insert','update','delete')),
    changed_at   timestamptz NOT NULL DEFAULT now(),
    changed_by   text,                              -- agent role or actor identifier
    old_value    jsonb,
    new_value    jsonb
);

CREATE INDEX tm_profiles_history_tm_idx ON public.tm_profiles_history (tm_id, changed_at DESC);

CREATE TABLE public.tm_eligibility_history (
    change_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_id        text NOT NULL,
    slot_id      text NOT NULL,
    change_type  text NOT NULL CHECK (change_type IN ('insert','update','delete')),
    changed_at   timestamptz NOT NULL DEFAULT now(),
    changed_by   text,
    old_value    jsonb,
    new_value    jsonb
);

CREATE INDEX tm_eligibility_history_tm_idx   ON public.tm_eligibility_history (tm_id, changed_at DESC);
CREATE INDEX tm_eligibility_history_slot_idx ON public.tm_eligibility_history (slot_id, changed_at DESC);

-- ----------------------------------------------------------------------------
-- 10. TRIGGER FUNCTIONS — per-table because the key columns differ
--     `changed_by` is read from app.changed_by GUC; default 'trigger' if unset.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_tm_profiles_history() RETURNS TRIGGER AS $$
DECLARE
    actor text := COALESCE(current_setting('app.changed_by', true), 'trigger');
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO public.tm_profiles_history (tm_id, change_type, changed_by, old_value)
        VALUES (OLD.tm_id, 'delete', actor, to_jsonb(OLD));
        RETURN OLD;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO public.tm_profiles_history (tm_id, change_type, changed_by, new_value)
        VALUES (NEW.tm_id, 'insert', actor, to_jsonb(NEW));
        RETURN NEW;
    ELSE  -- UPDATE
        INSERT INTO public.tm_profiles_history (tm_id, change_type, changed_by, old_value, new_value)
        VALUES (NEW.tm_id, 'update', actor, to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.fn_tm_eligibility_history() RETURNS TRIGGER AS $$
DECLARE
    actor text := COALESCE(current_setting('app.changed_by', true), 'trigger');
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO public.tm_eligibility_history (tm_id, slot_id, change_type, changed_by, old_value)
        VALUES (OLD.tm_id, OLD.slot_id, 'delete', actor, to_jsonb(OLD));
        RETURN OLD;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO public.tm_eligibility_history (tm_id, slot_id, change_type, changed_by, new_value)
        VALUES (NEW.tm_id, NEW.slot_id, 'insert', actor, to_jsonb(NEW));
        RETURN NEW;
    ELSE  -- UPDATE
        INSERT INTO public.tm_eligibility_history (tm_id, slot_id, change_type, changed_by, old_value, new_value)
        VALUES (NEW.tm_id, NEW.slot_id, 'update', actor, to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tm_profiles_history
AFTER INSERT OR UPDATE OR DELETE ON public.tm_profiles
FOR EACH ROW EXECUTE FUNCTION public.fn_tm_profiles_history();

CREATE TRIGGER trg_tm_eligibility_history
AFTER INSERT OR UPDATE OR DELETE ON public.tm_eligibility
FOR EACH ROW EXECUTE FUNCTION public.fn_tm_eligibility_history();

-- ----------------------------------------------------------------------------
-- 11. updated_at maintenance for tm_profiles
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tm_profiles_touch
BEFORE UPDATE ON public.tm_profiles
FOR EACH ROW EXECUTE FUNCTION public.fn_touch_updated_at();

CREATE TRIGGER trg_tm_eligibility_touch
BEFORE UPDATE ON public.tm_eligibility
FOR EACH ROW EXECUTE FUNCTION public.fn_touch_updated_at();

-- ----------------------------------------------------------------------------
-- 12. RLS — service-role-only, matching the existing public.* pattern
-- ----------------------------------------------------------------------------
ALTER TABLE public.slots                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_profiles            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_eligibility         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_score_history       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_comments            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_accommodations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_preferences         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_pair_affinities     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_profiles_history    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tm_eligibility_history ENABLE ROW LEVEL SECURITY;
