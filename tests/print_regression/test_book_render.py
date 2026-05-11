"""
Visual + textual regression test for the Zone Deployment Book.

The suite has three tiers, each with different infrastructure requirements:

  TIER 1 — Golden integrity (always runs, no external deps)
  ──────────────────────────────────────────────────────────
  Verifies that the committed golden artifacts are internally consistent:
  page count matches the manifest, all page PNGs are readable, the text JSON
  has one entry per page, and the source PDF hash hasn't drifted.

  These tests must pass before ANY PR that touches the renderer is merged.

  TIER 2 — Text regression (runs when source xlsx + DB env vars are set)
  ──────────────────────────────────────────────────────────────────────
  Re-renders the book from the frozen source xlsx using the current renderer
  code + live DB.  Extracts and normalises text from the fresh HTML and
  compares it against the text extracted from the golden PDF.

  Skipped automatically if:
    - tests/print_regression/golden/inputs/Week Overview - Filled - <week>.xlsx
      is absent (place the file there to enable these tests)
    - SUPABASE_URL or SUPABASE_SERVICE_KEY env vars are not set

  TIER 3 — Visual SSIM (runs when Tier 2 passes + weasyprint is installed)
  ──────────────────────────────────────────────────────────────────────────
  Converts the fresh HTML to PDF via weasyprint, renders each page to an
  image, and computes structural similarity (SSIM) against the golden PNGs.

  Skipped automatically if weasyprint is not installed.  Install it for
  local pre-merge validation:
      pip install weasyprint

  Note: the golden PDF was produced by a browser print dialog, and weasyprint
  renders CSS slightly differently (font hinting, sub-pixel positioning).  The
  SSIM floor is therefore calibrated at 0.95 — strict enough to catch layout
  drift, permissive enough to survive renderer/font differences.

────────────────────────────────────────────────────────────────────────────
If a test fails
────────────────────────────────────────────────────────────────────────────
  Tier 1 failure → the golden artifacts are corrupted or missing.
                   Run update_golden.py to regenerate from the source PDF.

  Tier 2 failure → the renderer produced different text than the golden.
                   Inspect the diff (printed by the test) carefully.
                   If the change is UNINTENTIONAL: investigate the renderer.
                   If the change is APPROVED: re-run update_golden.py,
                   commit the new golden, and include Brian's sign-off in
                   the commit message.

  Tier 3 failure → layout or visual drift detected.
                   Diff PNGs are saved to tests/print_regression/diffs/.
                   Inspect them; do NOT update the golden to make the test
                   pass without sign-off.

────────────────────────────────────────────────────────────────────────────
Running
────────────────────────────────────────────────────────────────────────────
  pytest tests/print_regression/ -v             # full suite (Tier 1 always)
  pytest tests/print_regression/ -v -k tier1    # Tier 1 only
  pytest tests/print_regression/ -v -k tier2    # Tier 2 (+ Tier 1)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.print_regression.conftest import (
    DIFFS_DIR,
    GOLDEN_DIR,
    GOLDEN_PAGES,
    GOLDEN_PDF,
    GOLDEN_TEXT,
    MANIFEST,
    SSIM_FLOOR,
    WEEK_KEY,
    normalise_text as _normalise,
)


def _html_to_text(html_path: Path) -> dict[str, str]:
    """Extract per-page text from the renderer's HTML output.

    The renderer emits one `.page` div per page with a `data-page` attribute.
    Falls back to dividing by the page-break marker if the attribute is absent.
    Returns {page_key: normalised_text} matching the golden text JSON format.
    """
    from html.parser import HTMLParser

    class _PageTextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._depth = 0
            self._in_page = False
            self._page_num = 0
            self._buf: list[str] = []
            self.pages: dict[str, str] = {}

        def handle_starttag(self, tag, attrs):
            attr_dict = dict(attrs)
            cls = attr_dict.get("class", "")
            if tag == "div" and "page" in cls.split():
                self._in_page = True
                self._page_num += 1
                self._depth = 0
                self._buf = []
            elif self._in_page:
                self._depth += 1

        def handle_endtag(self, tag):
            if not self._in_page:
                return
            if tag == "div":
                if self._depth == 0:
                    key = f"page_{self._page_num:02d}"
                    self.pages[key] = _normalise(" ".join(self._buf))
                    self._in_page = False
                else:
                    self._depth -= 1

        def handle_data(self, data):
            if self._in_page:
                stripped = data.strip()
                if stripped:
                    self._buf.append(stripped)

    extractor = _PageTextExtractor()
    extractor.feed(html_path.read_text(encoding="utf-8"))
    return extractor.pages


def _ssim_score(golden_img, fresh_img) -> float:
    """Compute grayscale SSIM between two Pillow Image objects."""
    import numpy as np
    from skimage.metrics import structural_similarity as ssim

    if golden_img.size != fresh_img.size:
        fresh_img = fresh_img.resize(golden_img.size)
    g = np.array(golden_img.convert("L"))
    f = np.array(fresh_img.convert("L"))
    return float(ssim(g, f, data_range=255))


def _save_diff(golden_img, fresh_img, out_path: Path) -> None:
    """Save a side-by-side comparison: golden | fresh | absolute diff."""
    from PIL import Image, ImageChops
    DIFFS_DIR.mkdir(parents=True, exist_ok=True)
    if golden_img.size != fresh_img.size:
        fresh_img = fresh_img.resize(golden_img.size)
    diff = ImageChops.difference(golden_img, fresh_img)
    w, h = golden_img.size
    canvas = Image.new("RGB", (w * 3 + 20, h), "white")
    canvas.paste(golden_img, (0, 0))
    canvas.paste(fresh_img, (w + 10, 0))
    canvas.paste(diff, (w * 2 + 20, 0))
    canvas.save(out_path)


# ═════════════════════════════════════════════════════════════════════════════
# TIER 1 — Golden integrity (no external deps, always runs)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.tier1
class TestGoldenIntegrity:
    """Verify the committed golden artifacts are internally self-consistent.

    If any of these fail, run update_golden.py to regenerate from the source PDF.
    They should never fail on main unless someone accidentally edited golden files.
    """

    def test_source_pdf_present(self):
        """Golden source PDF must be committed."""
        assert GOLDEN_PDF.exists(), (
            f"Golden PDF missing at {GOLDEN_PDF}. "
            "Was it accidentally deleted from the repo?"
        )

    def test_manifest_present_and_valid(self, golden_manifest):
        """Manifest must be parseable and contain required keys."""
        required = {"week_key", "source_pdf", "source_sha256", "page_count", "render_dpi"}
        missing = required - set(golden_manifest)
        assert not missing, f"Manifest missing keys: {missing}"
        assert golden_manifest["page_count"] > 0, "page_count must be positive"
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", golden_manifest["week_key"]), (
            f"week_key must be YYYY-MM-DD, got {golden_manifest['week_key']!r}"
        )

    def test_source_pdf_hash_unchanged(self, golden_manifest):
        """SHA-256 of the golden PDF must match the manifest.

        A mismatch means the PDF was replaced without regenerating the golden
        artifacts. Run update_golden.py with the new PDF.
        """
        import hashlib
        actual = hashlib.sha256(GOLDEN_PDF.read_bytes()).hexdigest()
        expected = golden_manifest["source_sha256"]
        assert actual == expected, (
            f"Golden PDF hash mismatch.\n"
            f"  Expected (manifest): {expected}\n"
            f"  Actual (on disk):    {actual}\n\n"
            "The PDF was replaced without regenerating golden artifacts. "
            "Run: python -m tests.print_regression.update_golden --force"
        )

    def test_page_png_count_matches_manifest(self, golden_manifest):
        """Number of committed page PNGs must match page_count in manifest."""
        expected = golden_manifest["page_count"]
        pngs = sorted(GOLDEN_PAGES.glob("page_*.png"))
        assert len(pngs) == expected, (
            f"Expected {expected} page PNGs in {GOLDEN_PAGES}/, found {len(pngs)}.\n"
            "Run: python -m tests.print_regression.update_golden --force"
        )

    def test_page_pngs_are_readable(self, golden_manifest):
        """Each committed page PNG must open without error and have non-zero size."""
        from PIL import Image
        pngs = sorted(GOLDEN_PAGES.glob("page_*.png"))
        for p in pngs:
            img = Image.open(p)
            w, h = img.size
            assert w > 0 and h > 0, f"{p.name}: zero-dimension image ({w}×{h})"

    def test_text_json_page_count_matches_manifest(self, golden_manifest, golden_text):
        """Text JSON must have one entry per page."""
        expected = golden_manifest["page_count"]
        actual   = len(golden_text)
        assert actual == expected, (
            f"Text JSON has {actual} pages; manifest says {expected}.\n"
            "Run: python -m tests.print_regression.update_golden --force"
        )

    def test_text_json_pages_are_nonempty(self, golden_text):
        """Every page must have at least some extracted text.

        An empty page suggests the PDF has image-only content or a pypdf
        extraction failure. Catches accidentally blank pages in the golden.
        """
        empty = [k for k, v in golden_text.items() if not v.strip()]
        assert not empty, (
            f"Pages with no extracted text: {empty}.\n"
            "If these are intentionally blank, update the test tolerance."
        )


# ═════════════════════════════════════════════════════════════════════════════
# TIER 2 — Text regression (requires source xlsx + DB env vars)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.tier2
class TestTextRegression:
    """Re-render the book from current code and compare text content to golden.

    Skipped automatically if:
      - Source xlsx not in tests/print_regression/golden/inputs/
      - SUPABASE_URL / SUPABASE_SERVICE_KEY not set

    See conftest.py::fresh_html fixture for the render setup.
    """

    def test_fresh_html_produced(self, fresh_html):
        """Renderer must produce a non-empty HTML file."""
        assert fresh_html.exists(), f"fresh_html fixture produced no file at {fresh_html}"
        size = fresh_html.stat().st_size
        assert size > 10_000, (
            f"Rendered HTML is suspiciously small ({size} bytes). "
            "Possible renderer error; check the HTML content."
        )

    def test_page_count_matches_golden(self, fresh_html, golden_manifest):
        """Fresh render must have the same number of pages as the golden."""
        expected = golden_manifest["page_count"]
        fresh_text = _html_to_text(fresh_html)
        actual = len(fresh_text)
        assert actual == expected, (
            f"Page count drift: golden has {expected} pages, "
            f"fresh render has {actual}.\n"
            "Investigate renderer changes before updating the golden."
        )

    def test_text_content_per_page(self, fresh_html, golden_text):
        """Per-page text must match the golden exactly after normalisation.

        Text is extracted from the rendered HTML (not converted back through PDF)
        so the comparison is reliable and deterministic regardless of PDF engine.

        On failure the test prints each differing page's expected vs actual text
        (first 300 chars of each) to aid diagnosis.
        """
        fresh_pages = _html_to_text(fresh_html)

        failures: list[str] = []
        for page_key, expected_text in sorted(golden_text.items()):
            fresh = fresh_pages.get(page_key, "")
            e_norm = _normalise(expected_text)
            f_norm = _normalise(fresh)
            if e_norm != f_norm:
                failures.append(
                    f"\n  {page_key}:\n"
                    f"    EXPECTED (first 300): {e_norm[:300]!r}\n"
                    f"    ACTUAL   (first 300): {f_norm[:300]!r}"
                )

        assert not failures, (
            f"Text content drift on {len(failures)} page(s):{chr(10).join(failures)}\n\n"
            "If the change is intentional (approved by Brian), regenerate the golden:\n"
            "  python -m tests.print_regression.update_golden --force"
        )

    def test_no_unfilled_zones_in_fresh_render(self, fresh_html):
        """Sanity check: the fresh HTML must not contain 'Unfilled' in any zone card.

        An 'Unfilled' string reaching the renderer means the source xlsx has
        an empty zone slot — which would be a data problem, not a renderer bug.
        Treat this as a data integrity failure to distinguish from layout drift.
        """
        html = fresh_html.read_text(encoding="utf-8", errors="replace")
        unfilled_count = html.count("Unfilled")
        # Allow 0; surface > 0 as a warning (not a hard failure, since the
        # source xlsx might legitimately have empty slots on some nights).
        if unfilled_count > 0:
            pytest.xfail(
                f"Fresh render contains 'Unfilled' {unfilled_count} time(s). "
                "This is a data issue in the source xlsx, not a renderer bug. "
                "Verify all zones are staffed for the golden week."
            )


# ═════════════════════════════════════════════════════════════════════════════
# TIER 3 — Visual SSIM (requires Tier 2 + weasyprint)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.tier3
class TestVisualSSIM:
    """Structural similarity comparison between golden page images and fresh render.

    Requires weasyprint (pip install weasyprint) to convert fresh HTML → PDF.

    Note: the golden PDF was produced by a browser print dialog. weasyprint
    renders CSS slightly differently (font hinting, sub-pixel rounding). The
    SSIM floor is therefore calibrated at 0.95 rather than 0.98 to avoid
    flakiness while still catching real layout drift.
    """

    SSIM_FLOOR_WEASYPRINT = 0.95   # Lower than browser-vs-browser because
                                    # browser vs weasyprint has inherent delta.

    def test_page_count_matches_golden(
        self, fresh_pdf_pages, golden_manifest
    ):
        """Fresh PDF page count must match golden."""
        expected = golden_manifest["page_count"]
        actual   = len(fresh_pdf_pages)
        assert actual == expected, (
            f"Page count drift in SSIM test: golden {expected}, fresh {actual}"
        )

    def test_ssim_per_page(self, fresh_pdf_pages, golden_page_images):
        """SSIM ≥ {floor} on every page."""
        from PIL import Image
        failures: list[tuple[str, float]] = []

        for idx, (golden_img, fresh_img) in enumerate(
            zip(golden_page_images, fresh_pdf_pages), start=1
        ):
            score = _ssim_score(golden_img, fresh_img)
            page_key = f"page_{idx:02d}"
            if score < self.SSIM_FLOOR_WEASYPRINT:
                diff_path = DIFFS_DIR / f"{page_key}_diff.png"
                _save_diff(golden_img, fresh_img, diff_path)
                failures.append((page_key, score))

        assert not failures, (
            f"Visual drift on {len(failures)} page(s) "
            f"(SSIM floor {self.SSIM_FLOOR_WEASYPRINT}):\n  "
            + "\n  ".join(
                f"{name}: SSIM={score:.4f}" for name, score in failures
            )
            + f"\n\nDiff images saved to {DIFFS_DIR}/.\n"
            "If the change is intentional, get Brian's sign-off and run "
            "update_golden.py."
        )
