-- ============================================================================
-- Migration 4: HR document domain
-- Purpose:   Schema-only. Bulk ingestion of Sorted_PDFs_2026-04-27 deferred
--            until the Memory Brain UI surfaces them; new docs land here
--            individually as they come in.
-- Date:      2026-05-05
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. HR_DOCUMENTS — metadata for stored HR PDFs (binaries live in Storage)
-- ----------------------------------------------------------------------------
CREATE TABLE public.hr_documents (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_id         text REFERENCES public.tm_profiles(tm_id) ON DELETE SET NULL,
                                                  -- nullable: templates / general docs not tied to a TM
    doc_type      text NOT NULL CHECK (doc_type IN (
                      'progressive_discipline',
                      'attendance_infraction',
                      'voluntary_statement',
                      'job_coach_onboarding',
                      'payroll_deduction',
                      'locker_request',
                      'offer_letter',
                      'shift_swap',
                      'schedule',
                      'adp_timecard',
                      'template',
                      'other'
                  )),
    doc_date      date,                           -- date the document refers to (incident date, schedule period, etc.)
    title         text,                           -- e.g. 'Verbal Warning - Late Arrival - 2026-04-15'
    file_path     text NOT NULL,                  -- 'hr-docs/{tm_id}/{filename}.pdf' or 'hr-docs/_templates/...'
    mime_type     text DEFAULT 'application/pdf',
    file_bytes    bigint,
    captured_at   timestamptz NOT NULL DEFAULT now(),
    captured_by   text,                           -- agent role or actor identifier
    notes         text,
    metadata      jsonb NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.hr_documents IS
  'Metadata for HR documents stored in Supabase Storage bucket "hr-docs". Schema-only landing — historical PDFs in OneDrive Sorted_PDFs_2026-04-27 ingested as-needed.';

CREATE INDEX hr_documents_tm_idx       ON public.hr_documents (tm_id, doc_date DESC);
CREATE INDEX hr_documents_type_date_idx ON public.hr_documents (doc_type, doc_date DESC);
CREATE INDEX hr_documents_captured_idx ON public.hr_documents (captured_at DESC);

ALTER TABLE public.hr_documents ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 2. STORAGE BUCKET — created via storage.buckets insert (Supabase pattern)
-- ----------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public, avif_autodetection, file_size_limit, allowed_mime_types)
VALUES (
    'hr-docs',
    'hr-docs',
    false,                                          -- private bucket; all access via signed URLs / service role
    false,
    52428800,                                       -- 50 MB per-file cap
    ARRAY['application/pdf','image/png','image/jpeg','application/octet-stream']
)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: deny anon/authenticated; service-role bypasses (default Supabase behavior)
CREATE POLICY hr_docs_no_anon_access
    ON storage.objects
    FOR ALL
    TO anon, authenticated
    USING (bucket_id <> 'hr-docs')
    WITH CHECK (bucket_id <> 'hr-docs');
