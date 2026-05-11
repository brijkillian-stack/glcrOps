-- Phase 2: multi_area_assignments table
--
-- Records when a supervisor assigns one TM to cover multiple zone areas
-- during a single shift (live-ops override layer).  The pre-shift deployment
-- engine still uses single-slot zone_assignments; this table is the
-- supervisor's live adjustment on top of the engine's plan.
--
-- Unique on (night_id, tm_id): a TM can only have one multi-area record
-- per night.  Use the additional_areas array to list secondary zones.
--
-- Apply via:
--   supabase db push  (local dev)
--   Supabase MCP apply_migration  (CI / remote)

create table if not exists multi_area_assignments (
    id               uuid primary key default gen_random_uuid(),
    night_id         uuid not null references nights(id) on delete cascade,
    tm_id            uuid not null references entities(id),
    primary_area     text not null,
    additional_areas text[] not null default '{}',
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    unique (night_id, tm_id)
);

create index if not exists multi_area_assignments_night_id_idx on multi_area_assignments (night_id);
create index if not exists multi_area_assignments_tm_id_idx    on multi_area_assignments (tm_id);

-- Auto-update updated_at on any row change.
create or replace function _set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists multi_area_assignments_updated_at on multi_area_assignments;
create trigger multi_area_assignments_updated_at
    before update on multi_area_assignments
    for each row execute function _set_updated_at();

comment on table multi_area_assignments is
    'Phase 4 live-ops: supervisor record that a TM covers multiple zone areas in one shift.';
comment on column multi_area_assignments.primary_area     is 'Main zone area (e.g. "Z1")';
comment on column multi_area_assignments.additional_areas is 'Additional zones covered (e.g. ARRAY[''Z2'',''Z9''])';
