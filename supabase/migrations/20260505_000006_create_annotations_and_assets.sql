-- ============================================================================
-- Migration 6: Annotations + asset Storage buckets (Phase K — iPad/Pencil)
-- Purpose:   Foundation for Apple Pencil annotation features:
--             - public.annotations: metadata for every Pencil drawing
--             - casino-assets bucket: floor map, brand assets, reference imagery
--             - annotations bucket: user-generated Pencil drawings (PNG)
-- Date:      2026-05-05
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. public.annotations
--    One row per saved Pencil annotation. Image binary lives in Storage.
-- ----------------------------------------------------------------------------
CREATE TABLE public.annotations (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind          text NOT NULL CHECK (kind IN (
                      'floor_map',          -- annotation on the casino floor map
                      'deployment_book',    -- annotation on a deployment book HTML
                      'signature',          -- signature region (write-ups, appraisals)
                      'tm_comment',         -- handwritten TM comment + Scribble text
                      'scratch'             -- ephemeral, not auto-persisted long-term
                  )),
    target_type   text NOT NULL CHECK (target_type IN (
                      'night','event','tm_profile','hr_document','note','generic'
                  )),
    target_id     text,                     -- FK target (text or uuid; resolved at app layer)
    image_path    text NOT NULL,            -- 'annotations/{kind}/{date}/{uuid}.png'
    width         int,
    height        int,
    author        text,                     -- email or display_name of the author
    pen_settings  jsonb NOT NULL DEFAULT '{}'::jsonb,
                                            -- { tool, color, stroke_widths[], pressure_used }
    text_value    text,                     -- Scribble-converted text (when handwritten comment)
    notes         text,
    metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz               -- nullable; for kind='scratch' or temporary uses
);

COMMENT ON TABLE public.annotations IS
  'Metadata for every Pencil annotation. Image binaries in Storage bucket "annotations".';
COMMENT ON COLUMN public.annotations.target_type IS
  'What this annotation attaches to. target_id is interpreted per type (e.g. tm_profile.tm_id, night.id, hr_document.id).';
COMMENT ON COLUMN public.annotations.expires_at IS
  'Optional TTL. Scratch annotations default to ~24h. Persistent annotations leave this NULL.';

CREATE INDEX annotations_target_idx       ON public.annotations (target_type, target_id, created_at DESC);
CREATE INDEX annotations_kind_idx         ON public.annotations (kind, created_at DESC);
CREATE INDEX annotations_author_idx       ON public.annotations (author, created_at DESC);
CREATE INDEX annotations_expires_idx      ON public.annotations (expires_at) WHERE expires_at IS NOT NULL;

ALTER TABLE public.annotations ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 2. Storage buckets
--    casino-assets: static reference imagery (floor map, brand assets, logos)
--    annotations:   user-generated Pencil drawings
--    Both private; service-role bypasses, anon/authenticated denied at the
--    storage.objects policy level (anon already denied via existing
--    hr_docs_no_anon_access policy; we widen it below).
-- ----------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public, avif_autodetection, file_size_limit, allowed_mime_types)
VALUES
  ('casino-assets', 'casino-assets', false, false, 26214400,            -- 25 MB
      ARRAY['image/png','image/jpeg','image/webp','image/svg+xml','application/pdf']),
  ('annotations',   'annotations',   false, false, 10485760,            -- 10 MB
      ARRAY['image/png','image/jpeg','image/webp'])
ON CONFLICT (id) DO NOTHING;

-- Replace the prior hr_docs_no_anon_access policy with a generic "no anon
-- access to private buckets" policy that covers all three private buckets.
DROP POLICY IF EXISTS hr_docs_no_anon_access ON storage.objects;

CREATE POLICY private_buckets_no_anon_access
    ON storage.objects
    FOR ALL
    TO anon, authenticated
    USING (bucket_id NOT IN ('hr-docs', 'casino-assets', 'annotations'))
    WITH CHECK (bucket_id NOT IN ('hr-docs', 'casino-assets', 'annotations'));
