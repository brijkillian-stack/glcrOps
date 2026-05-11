"""
conftest.py — pytest fixtures for the Zone Deployment Book print regression suite.

Session-scoped fixtures are used wherever possible so expensive operations
(PDF rendering, image conversion) happen once per pytest run, not once per test.

Configuration via environment variables
──────────────────────────────────────
  PRINT_REGRESSION_WEEK       ISO week-ending date (YYYY-MM-DD).
                              Defaults to the week_key recorded in manifest.json.
  PRINT_SERVICE_URL           Base URL of a running ZDS Forge API server,
                              e.g. http://localhost:8001
                              Required for integration + fresh_html_via_api fixtures.
  PRINT_SERVICE_WEEK_ID       DB UUID of the golden week (from public.weeks).
                              Required for integration + fresh_html_via_api fixtures.
  PRINT_SERVICE_NIGHT_ID      DB UUID of one night in the golden week (public.nights).
                              Required for night-endpoint integration tests only.
                              Skipped automatically if absent.
  SUPABASE_URL                Required for Tier 2 (direct renderer path).
  SUPABASE_SERVICE_KEY        Required for Tier 2 (direct renderer path).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT  = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = Path(__file__).parent / "golden"
DIFFS_DIR  = Path(__file__).parent / "diffs"
MANIFEST   = GOLDEN_DIR / "manifest.json"
INPUTS_DIR = GOLDEN_DIR / "inputs"

# ── Week key — driven by manifest, overridable via env ───────────────────────

def _resolve_week_key() -> str:
    """Resolve the active week key: env → manifest → last-resort fallback.

    In normal operation this reads from manifest.json so the value stays in
    sync with committed golden artifacts without any hardcoding.
    """
    if k := os.environ.get("PRINT_REGRESSION_WEEK", "").strip():
        return k
    if MANIFEST.exists():
        try:
            data = json.loads(MANIFEST.read_text())
            if k := data.get("week_key", "").strip():
                return k
        except Exception:
            pass
    return "2026-05-14"   # last-resort; should never be reached in normal use


WEEK_KEY = _resolve_week_key()

GOLDEN_PDF   = GOLDEN_DIR / f"zone_deployment_book_{WEEK_KEY}.pdf"
GOLDEN_PAGES = GOLDEN_DIR / f"zone_deployment_book_{WEEK_KEY}"
GOLDEN_TEXT  = GOLDEN_DIR / f"zone_deployment_book_{WEEK_KEY}_text.json"
SOURCE_XLSX  = INPUTS_DIR / f"Week Overview - Filled - {WEEK_KEY}.xlsx"

# ── PrintService integration config ──────────────────────────────────────────

PRINT_SERVICE_URL      = os.environ.get("PRINT_SERVICE_URL",      "").rstrip("/")
PRINT_SERVICE_WEEK_ID  = os.environ.get("PRINT_SERVICE_WEEK_ID",  "").strip()
PRINT_SERVICE_NIGHT_ID = os.environ.get("PRINT_SERVICE_NIGHT_ID", "").strip()

# ── Tolerance constants ───────────────────────────────────────────────────────

DPI        = 150    # matches update_golden.py
SSIM_FLOOR = 0.98   # structural similarity threshold; lower = more permissive


# ── Helpers (exported so test files share the same logic) ─────────────────────

def has_db_env() -> bool:
    """Return True if Supabase env vars are present (Tier 2 gate)."""
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def has_print_service_env() -> bool:
    """Return True if PrintService week integration env vars are set."""
    return bool(PRINT_SERVICE_URL and PRINT_SERVICE_WEEK_ID)


def has_night_service_env() -> bool:
    """Return True if PRINT_SERVICE_NIGHT_ID is also set (enables night-endpoint tests)."""
    return has_print_service_env() and bool(PRINT_SERVICE_NIGHT_ID)


def normalise_text(text: str) -> str:
    """Collapse whitespace runs to single space; strip.

    Exported so test files share the same normalisation as update_golden.py.
    """
    return re.sub(r"\s+", " ", text or "").strip()


# Backward-compat alias used by fixtures below.
_has_db_env = has_db_env


# ── Markers ───────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "tier1: always-runs golden-integrity checks (no external deps)")
    config.addinivalue_line("markers", "tier2: text regression — requires source xlsx + Supabase env vars")
    config.addinivalue_line("markers", "tier3: SSIM visual regression — requires tier2 + weasyprint")
    config.addinivalue_line(
        "markers",
        "integration: live-server integration tests — requires PRINT_SERVICE_URL + "
        "PRINT_SERVICE_WEEK_ID (and optionally PRINT_SERVICE_NIGHT_ID for night endpoints). "
        "Start the Forge API first: uvicorn apps.zds.api.main:app --port 8001",
    )


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
            f"Place 'Week Overview - Filled - {WEEK_KEY}.xlsx' in "
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
def fresh_html_via_api(tmp_path_factory) -> Path:
    """Fetch the current week's HTML from a running PrintService instance.

    Full end-to-end path: HTTP → PrintService → sacred renderer → HTML.
    Compared against golden text to verify the API layer is transparent.

    Requires:
      PRINT_SERVICE_URL      e.g. http://localhost:8001 (Forge API)
      PRINT_SERVICE_WEEK_ID  DB UUID of the golden week (public.weeks.id)

    Skipped if either env var is absent or the server is unreachable.

    To set up:
      1. Start the Forge API: uvicorn apps.zds.api.main:app --port 8001
      2. Look up the week UUID: SELECT id FROM weeks WHERE week_ending='YYYY-MM-DD'
      3. Export PRINT_SERVICE_URL=http://localhost:8001
         Export PRINT_SERVICE_WEEK_ID=<uuid>
    """
    if not has_print_service_env():
        pytest.skip(
            "PRINT_SERVICE_URL and PRINT_SERVICE_WEEK_ID not set — "
            "PrintService integration tests skipped.  "
            "Start the Forge API and export those env vars to enable."
        )
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed — pip install httpx")

    endpoint = f"{PRINT_SERVICE_URL}/v1/print/week/{PRINT_SERVICE_WEEK_ID}.html"
    try:
        resp = httpx.get(endpoint, timeout=30)
    except Exception as exc:
        pytest.skip(f"PrintService unreachable at {endpoint}: {exc}")

    if resp.status_code == 404:
        pytest.fail(
            f"PrintService 404 for week {PRINT_SERVICE_WEEK_ID!r}. "
            "Verify PRINT_SERVICE_WEEK_ID is a valid week UUID in the DB."
        )
    if resp.status_code != 200:
        pytest.fail(f"PrintService returned {resp.status_code} for {endpoint}:\n{resp.text[:500]}")

    tmpdir = tmp_path_factory.mktemp("zds_api_render")
    out    = tmpdir / f"api_{PRINT_SERVICE_WEEK_ID[:8]}.html"
    out.write_text(resp.text, encoding="utf-8")
    return out


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
