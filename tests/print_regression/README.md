# Zone Deployment Book — Print Regression Suite

The printed Zone Deployment Book is the most trusted operational artifact on
the floor. Brian's crew reads it at the start of every grave shift; every zone
assignment, break wave, and coverage callout on it matters. This test suite
exists so changes to the renderer are caught before they touch the floor.

**The rule:** if `render_deployment_book.py` or `print_renderer.py` changes,
this suite must pass before the PR merges.

---

## What the tests do

Tests are organised into three tiers with different infrastructure requirements.

### Tier 1 — Golden integrity (always runs, no deps)

Validates that the committed golden artifacts are self-consistent:

- Source PDF is present and its SHA-256 matches the manifest
- Page PNG count matches manifest
- Each PNG is readable and non-zero-dimension
- Text JSON has one entry per page and every page has content

**These always run in CI.** They should never fail unless someone edited golden
files by hand or deleted them. If they fail, run `update_golden.py`.

### Tier 2 — Text regression (requires source xlsx + DB)

Re-renders the book from the current renderer code using the frozen source xlsx
and live DB, then compares extracted text per page against the golden.

Automatically **skipped** if:
- `tests/print_regression/golden/inputs/Week Overview - Filled - <week>.xlsx`
  is missing
- `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` env vars are not set

The active week is read from `golden/manifest.json` (`week_key` field) — no
hardcoded date in the code.

To enable: place the source xlsx in `golden/inputs/` and export the DB env vars.

### Tier 3 — Visual SSIM (requires Tier 2 + weasyprint)

Converts the fresh HTML to PDF via weasyprint, renders each page to an image,
and compares structural similarity (SSIM) against the committed golden page
PNGs. SSIM threshold: **0.95** (browser-print vs weasyprint inherently differs
in font hinting; 0.95 catches real drift without flakiness).

Automatically **skipped** if weasyprint is not installed. Install it locally:

```bash
pip install weasyprint
# macOS also needs:
brew install pango cairo
```

---

## Running the tests

```bash
# Full suite (Tier 1 always; Tier 2/3 if deps present)
pytest tests/print_regression/ -v

# Tier 1 only (fast, no external deps)
pytest tests/print_regression/ -v -m tier1

# Tier 2 + Tier 1 (text regression; no weasyprint needed)
pytest tests/print_regression/ -v -m "tier1 or tier2"

# All three tiers
pytest tests/print_regression/ -v -m "tier1 or tier2 or tier3"
```

---

## Reading a failure

### Tier 1 failure

The committed golden is corrupted or missing. Run:

```bash
python -m tests.print_regression.update_golden --force
```

Commit the regenerated artifacts.

### Tier 2 failure (text drift)

The renderer produced different text than the golden. The test output shows
the differing pages and a preview of expected vs actual text.

1. **Read the diff carefully.** Is this an intentional change or an accidental
   regression?
2. If unintentional → fix the renderer. Do not update the golden.
3. If intentional (Brian's approval required) → regenerate the golden (see
   below) and include the approval in the commit message.

### Tier 3 failure (visual drift)

Diff PNGs are saved to `tests/print_regression/diffs/`. Each diff shows:
**golden | fresh render | absolute diff** side by side.

CI uploads these as artifacts automatically on failure — check the GitHub
Actions run's "Artifacts" tab to download them.

1. Open the diff PNGs and inspect which pages drifted.
2. Is this a real visual change or a rendering-engine difference (fonts,
   sub-pixel rounding)?
3. If real → investigate the renderer change.
4. If approved → regenerate the golden.

---

## Updating the golden after an approved layout change

**This workflow requires Brian's explicit sign-off before running.**

### Classic (browser-print PDF) workflow

1. Print the book from the browser to PDF and save it as:
   `tests/print_regression/golden/zone_deployment_book_<week>.pdf`
2. Run:

```bash
python -m tests.print_regression.update_golden --week YYYY-MM-DD --force
```

### PrintService workflow (recommended for Phase 3+)

Once the Forge API is running, fetch the golden directly from the service:

1. Start the Forge API: `uvicorn apps.zds.api.main:app --port 8001`
2. Look up the week UUID: `SELECT id FROM weeks WHERE week_ending = 'YYYY-MM-DD';`
3. Run:

```bash
python -m tests.print_regression.update_golden \
    --source print-service \
    --service-url http://localhost:8001 \
    --service-week-id <uuid>
```

Or via env vars:
```bash
PRINT_SERVICE_URL=http://localhost:8001 \
PRINT_SERVICE_WEEK_ID=<uuid> \
python -m tests.print_regression.update_golden --source print-service
```

4. Open the generated PDF and page PNGs — confirm they match what Brian
   visually approved.
5. Commit everything in `tests/print_regression/golden/` with message:

```
Golden master regenerated from PrintService — Brian approved YYYY-MM-DD
```

---

## Git LFS — large binary golden artifacts

The golden PDF and page PNGs are large binary files stored in Git LFS to keep
clone times fast. They are tracked via `.gitattributes`:

```
tests/print_regression/golden/*.pdf    filter=lfs diff=lfs merge=lfs -text
tests/print_regression/golden/**/*.png filter=lfs diff=lfs merge=lfs -text
```

**First-time LFS setup** (if golden files weren't already in LFS):

```bash
git lfs install
git lfs migrate import \
    --include="tests/print_regression/golden/*.pdf,tests/print_regression/golden/**/*.png" \
    --everything
git push --force origin main   # rewrites history — coordinate with team
```

After that, `git add / commit / push` automatically uses LFS for those paths.

**CI:** The workflow calls `git lfs pull` after checkout to ensure the golden
files are fully materialized before the tests run.

---

## **Do NOT update the golden to make the test pass.**

A failing Tier 2 or Tier 3 test means the renderer drifted. Investigate first.
The golden is the contract. Updating it without sign-off breaks the contract.

---

## Directory layout

```
tests/print_regression/
├── __init__.py
├── conftest.py              pytest fixtures + shared helpers
├── test_book_render.py      Tier 1/2/3 regression tests
├── test_api_print.py        API endpoint structural + adapter-transparency tests
├── update_golden.py         CLI to regenerate golden artifacts
├── README.md                this file
├── golden/
│   ├── zone_deployment_book_<week>.pdf      source golden PDF (LFS)
│   ├── zone_deployment_book_<week>/
│   │   ├── page_01.png                      committed page images (LFS)
│   │   └── …
│   ├── zone_deployment_book_<week>_text.json  per-page extracted text
│   ├── manifest.json                        page count, DPI, hash, week_key
│   └── inputs/
│       └── Week Overview - Filled - <week>.xlsx   frozen source xlsx (not in LFS)
└── diffs/                   generated on test failure (gitignored)
    └── .gitkeep
```

---

## System dependencies

- **poppler-utils** — required by `pdf2image` (page image extraction)
  - macOS: `brew install poppler`
  - Ubuntu/CI: `apt-get install poppler-utils`
- **weasyprint** (Tier 3 only) — HTML → PDF conversion
  - `pip install weasyprint`
  - May need `brew install pango cairo` on macOS

Install all Python test deps at once:

```bash
pip install -r requirements-dev.txt
```

---

## SSIM threshold calibration

The 0.95 threshold for Tier 3 (browser-print golden vs weasyprint fresh render)
was calibrated empirically. Run the test multiple times on unchanged code and
confirm the baseline SSIM is consistently ≥ 0.97 before shipping.

If the test is flaky at 0.95, lower toward 0.93. If it's too permissive, raise
toward 0.97. Document the calibration run in the manifest.
