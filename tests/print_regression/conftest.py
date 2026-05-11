"""
conftest.py — pytest fixtures for the Zone Deployment Book print regression suite.

Session-scoped fixtures are used wherever possible so expensive operations
(PDF rendering, image conversion) happen once per pytest run, not once per test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths — all relative to the repo root so tests are portable
# ---------------------------------------------------------------------------

REPO_ROOT   = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR  = Path(__file__).parent / "golden"
DIFFS_DIR   = Path(__file__).parent / "diffs"
WEEK_KEY    = "2026-05-14"

GOLDEN_PDF   = GOLDEN_DIR / f"zone_deployment_book_{WEEK_KEY}.pdf"
GOLDEN_PAGES = GOLDEN_DIR / f"zone_deployment_book_{WEEK_KEY}"
GOLDEN_TEXT  = GOLDEN_DIR / f"zone_deployment_book_{WEEK_KEY}_text.json"
MANIFEST     = GOLDEN_DIR / "manifest.json"

# Schedule xlsx: renderer reads from this to re-produce the book.
# Stored in tests/print_regression/golden/inputs/ so the test is fully
# self-contained without Storage access. Brian places the file here once;
# it's committed (xlsx is ~30 KB).
INPUTS_DIR    = GOLDEN_DIR / "inputs"
SOURCE_XLSX   = INPUTS_DIR / f"Week Overview - Filled - {WEEK_KEY}.xlsx"

# ---------------------------------------------------------------------------
# Tolerance constants
# ---------------------------------------------------------------------------

DPI         = 150   # matches update_golden.py
SSIM_FLOOR  = 0.98  # structural similarity threshold; lower = more permissive


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_source_xlsx: test needs the source xlsx in golden/inputs/; "
        "skipped automatically if the file is absent",
    )
    config.addinivalue_line(
        "markers",
        "requires_db: test needs SUPABASE_URL + SUPABASE_SERVICE_KEY env vars",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_db_env() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def golden_manifest() -> dict:
    """Load and return the committed manifest.json."""
    import json
    if not MANIFEST.exists():
        pytest.skip(f"Golden manifest missing at {MANIFEST}. Run update_golden.py first.")
    return json.loads(MANIFEST.read_text())


@pytest.fixture(scope="session")
def golden_text() -> dict[str, str]:
    """Load per-page text extracted from the golden PDF."""
    import json
    if not GOLDEN_TEXT.exists():
        pytest.skip(f"Golden text JSON missing at {GOLDEN_TEXT}. Run update_golden.py first.")
    return json.loads(GOLDEN_TEXT.read_text())


@pytest.fixture(scope="session")
def golden_page_images() -> list:
    """Load the committed golden page PNGs as Pillow Image objects."""
    from PIL import Image
    pngs = sorted(GOLDEN_PAGES.glob("page_*.png"))
    if not pngs:
        pytest.skip(f"No golden page PNGs in {GOLDEN_PAGES}/. Run update_golden.py first.")
    return [Image.open(p) for p in pngs]


@pytest.fixture(scope="session")
def fresh_html(tmp_path_factory) -> Path:
    """Render the book fresh from current code + source xlsx.

    Skipped automatically if the source xlsx isn't present in golden/inputs/
    or if DB env vars are missing (the renderer reads tasks / roster from DB).

    Returns the path to the produced HTML file.
    """
    if not SOURCE_XLSX.exists():
        pytest.skip(
            f"Source xlsx not found at {SOURCE_XLSX}. "
            "Place 'Week Overview - Filled - 2026-05-14.xlsx' in "
            "tests/print_regression/golden/inputs/ to enable renderer tests."
        )
    if not _has_db_env():
        pytest.skip(
            "DB env vars (SUPABASE_URL, SUPABASE_SERVICE_KEY) not set. "
            "Renderer tests need live DB access to load tasks and roster."
        )

    import sys
    import importlib.util

    # Load the renderer module without executing __main__
    renderer_path = REPO_ROOT / "apps" / "zds" / "engine" / "render_deployment_book.py"
    if not renderer_path.exists():
        pytest.fail(f"Renderer not found at {renderer_path}")

    spec = importlib.util.spec_from_file_location("render_deployment_book", renderer_path)
    rdb = importlib.util.module_from_spec(spec)

    # Ensure the repo root is on sys.path so shared/ imports work
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    try:
        spec.loader.exec_module(rdb)
    except Exception as exc:
        pytest.fail(f"Failed to import renderer: {exc}")

    tmpdir = tmp_path_factory.mktemp("zds_render")
    out_html = tmpdir / f"book_{WEEK_KEY}.html"

    exit_code = rdb.main([str(SOURCE_XLSX), str(out_html)])
    if exit_code != 0:
        pytest.fail(
            f"Renderer exited with code {exit_code}. "
            "Check that the source xlsx matches the expected format."
        )
    if not out_html.exists():
        pytest.fail(f"Renderer reported success but HTML not found at {out_html}")

    return out_html


@pytest.fixture(scope="session")
def fresh_pdf_pages(fresh_html, tmp_path_factory) -> list:
    """Convert the fresh HTML render to page images using weasyprint + pdf2image.

    Skipped if weasyprint is not installed (it's an optional dep for local runs).
    In CI the text regression is the primary gate; SSIM is secondary.
    """
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        pytest.skip(
            "weasyprint not installed. Install it for SSIM visual regression: "
            "pip install weasyprint. Falls back gracefully to text-only CI checks."
        )

    from weasyprint import HTML as WPHTML
    from pdf2image import convert_from_path

    tmpdir = tmp_path_factory.mktemp("zds_pdf")
    fresh_pdf = tmpdir / f"book_{WEEK_KEY}.pdf"

    WPHTML(filename=str(fresh_html)).write_pdf(str(fresh_pdf))

    if not fresh_pdf.exists():
        pytest.fail("weasyprint produced no PDF")

    return convert_from_path(fresh_pdf, dpi=DPI, fmt="png")
