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
- `tests/print_regression/golden/inputs/Week Overview - Filled - 2026-05-14.xlsx`
  is missing
- `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` env vars are not set

To enable: place the source xlsx in `golden/inputs/` and export the DB env vars.

### Tier 3 — Visual SSIM (requires Tier 2 + weasyprint)

Converts the fresh HTML to PDF via weasyprint, renders each page to an image,
and compares structural similarity (SSIM) against the committed golden page
PNGs. SSIM threshold: **0.95** (browser-print vs weasyprint inherently differs
in font hinting; 0.95 catches real drift without flakiness).

Automatically **skipped** if weasyprint is not installed. Install it locally:

```
pip install weasyprint
```

---

## Running the tests

```bash
# Full suite (Tier 1 always; Tier 2/3 if deps present)
pytest tests/print_regression/ -v

# Tier 1 only (fast, no external deps)
pytest tests/print_regression/ -v -k tier1

# Tier 2 + Tier 1 (text regression; no weasyprint needed)
pytest tests/print_regression/ -v -k "tier1 or tier2"

# All three tiers
pytest tests/print_regression/ -v -k "tier1 or tier2 or tier3"
```

---

## Reading a failure

### Tier 1 failure

The committed golden is corrupted or missing. Run:

```
python -m tests.print_regression.update_golden --force
```

Commit the regenerated artifacts.

### Tier 2 failure (text drift)

The renderer produced different text than the golden. The test output shows
the differing pages and a preview of expected vs actual text.

1. **Read the diff carefully.** Is this an intentional change (e.g. a copy
   update from "ZONES" → "Zones") or an accidental regression?
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

1. Confirm the new renderer output looks correct (run Tier 2 + 3 locally,
   inspect diffs).
2. Have Brian review the new rendered book side-by-side with the current golden.
3. Once approved, regenerate:

```bash
python -m tests.print_regression.update_golden --force
```

4. Commit the regenerated golden + the renderer change **in the same commit**.
   Include the sign-off in the commit message:

```
Phase N: [description of layout change]

Golden master regenerated — Brian approved on YYYY-MM-DD.
```

5. Push and verify CI passes on the new golden.

---

## **Do NOT update the golden to make the test pass.**

A failing Tier 2 or Tier 3 test means the renderer drifted. Investigate first.
The golden is the contract. Updating it without sign-off breaks the contract.

---

## Directory layout

```
tests/print_regression/
├── __init__.py
├── conftest.py                         pytest fixtures
├── test_book_render.py                 the regression tests
├── update_golden.py                    CLI to regenerate golden artifacts
├── README.md                           this file
├── golden/
│   ├── zone_deployment_book_2026-05-14.pdf      source golden (browser print)
│   ├── zone_deployment_book_2026-05-14/
│   │   ├── page_01.png                          committed page images
│   │   └── …
│   ├── zone_deployment_book_2026-05-14_text.json  per-page extracted text
│   ├── manifest.json                            page count, DPI, hash
│   └── inputs/
│       └── Week Overview - Filled - 2026-05-14.xlsx   frozen source xlsx
└── diffs/                              generated on test failure (gitignored)
    └── .gitkeep
```

---

## System dependencies

- **poppler-utils** — required by `pdf2image` (page image extraction)
  - macOS: `brew install poppler`
  - Ubuntu/Render: `apt-get install poppler-utils`
- **weasyprint** (Tier 3 only) — HTML → PDF conversion
  - `pip install weasyprint`
  - May need `brew install pango cairo` on macOS

---

## SSIM threshold calibration

The 0.95 threshold for Tier 3 (browser-print golden vs weasyprint fresh render)
was calibrated empirically. Run the test multiple times on unchanged code and
confirm the baseline SSIM is consistently ≥ 0.97 before shipping.

If the test is flaky at 0.95, increase to 0.93. If it's too permissive, lower
toward 0.97. Document the calibration run in the manifest.
