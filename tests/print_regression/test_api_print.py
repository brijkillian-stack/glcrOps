"""
API-tier regression tests for the ZDS Forge print endpoints.

Tier 2 — requires Supabase env vars (same skip conditions as test_book_render.py).

These tests assert that what the HTTP endpoints return matches what the sacred
renderer produces directly.  If they diverge, PrintService is altering the
renderer's output somewhere between function call and HTTP response — investigate.

The tests do NOT re-run the visual or text regressions from test_book_render.py;
they only verify that the API adapter layer is transparent.

──────────────────────────────────────────────────────────────────────────────
Running
──────────────────────────────────────────────────────────────────────────────
  pytest tests/print_regression/test_api_print.py -v          # full (Tier 2 auto-skips without DB)
  pytest tests/print_regression/test_api_print.py -v -k tier1 # fast structural checks only
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from tests.print_regression.conftest import (
    has_db_env as _has_db_env,
    has_print_service_env,
    normalise_text,
)

# ── Path constants (mirror conftest.py) ───────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_fastapi_client():
    """Build an async httpx test client backed by the real FastAPI app.

    Overrides get_placement_service and get_print_service with fakes so
    we don't need a live DB or Redis for structural Tier 1 tests.
    """
    try:
        from httpx import AsyncClient, ASGITransport  # type: ignore[import]
    except ImportError:
        pytest.skip("httpx not installed — pip install httpx")

    from apps.zds.api.main import app
    from apps.zds.api.core.dependencies import (
        get_placement_service,
        get_print_service,
    )
    from apps.zds.api.services.exceptions import WeekNotFoundError

    # Fake PrintService that returns canned output.
    class FakePrintService:
        async def render_week_html(self, week_id):
            if week_id == "nonexistent":
                raise WeekNotFoundError(week_id)
            html = f"<html><body>Week {week_id}</body></html>"
            return html.encode("utf-8"), f"book_{week_id}_abc12345.html"

        async def render_week_pdf(self, week_id):
            if week_id == "nonexistent":
                raise WeekNotFoundError(week_id)
            return b"%PDF-1.4 fake pdf content", f"book_{week_id}_abc12345.pdf"

        async def render_night_html(self, night_id):
            from apps.zds.api.services.exceptions import NightNotFoundError
            if night_id == "nonexistent":
                raise NightNotFoundError(night_id)
            html = f"<html><body>Night {night_id}</body></html>"
            return html.encode("utf-8"), f"night_{night_id}_abc12345.html"

        async def render_night_pdf(self, night_id):
            from apps.zds.api.services.exceptions import NightNotFoundError
            if night_id == "nonexistent":
                raise NightNotFoundError(night_id)
            return b"%PDF-1.4 fake pdf", f"night_{night_id}_abc12345.pdf"

    fake_print_svc = FakePrintService()
    app.dependency_overrides[get_print_service] = lambda: fake_print_svc

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test"), app


# ═════════════════════════════════════════════════════════════════════════════
# Tier 1 — Structural endpoint tests (always runs, no DB needed)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.tier1
class TestPrintEndpointStructure:
    """Verify the router wiring, content-types, headers, and error envelopes.

    These tests inject a fake PrintService so no DB or renderer is involved.
    They catch: wrong HTTP status, missing headers, wrong content-type,
    malformed error envelopes.
    """

    @pytest.mark.asyncio
    async def test_week_html_200(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/week/week-abc-123.html")
        app.dependency_overrides.clear()
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Zone" in r.text or "Week" in r.text  # content present

    @pytest.mark.asyncio
    async def test_week_html_has_cache_control(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/week/week-abc-123.html")
        app.dependency_overrides.clear()
        assert "cache-control" in r.headers
        cc = r.headers["cache-control"]
        assert "private" in cc
        assert "max-age" in cc

    @pytest.mark.asyncio
    async def test_week_html_has_content_disposition(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/week/week-abc-123.html")
        app.dependency_overrides.clear()
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd
        assert ".html" in cd

    @pytest.mark.asyncio
    async def test_week_pdf_200(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/week/week-abc-123.pdf")
        app.dependency_overrides.clear()
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_week_pdf_content_disposition_inline(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/week/week-abc-123.pdf")
        app.dependency_overrides.clear()
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd, "Content-Disposition must be inline (not attachment)"
        assert "attachment" not in cd

    @pytest.mark.asyncio
    async def test_week_html_404_for_missing_week(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/week/nonexistent.html")
        app.dependency_overrides.clear()
        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_week_pdf_404_for_missing_week(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/week/nonexistent.pdf")
        app.dependency_overrides.clear()
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_night_html_200(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/night/night-fri-001.html")
        app.dependency_overrides.clear()
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    @pytest.mark.asyncio
    async def test_night_pdf_200(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/night/night-fri-001.pdf")
        app.dependency_overrides.clear()
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_night_html_404_for_missing_night(self):
        client, app = _make_fastapi_client()
        async with client as c:
            r = await c.get("/v1/print/night/nonexistent.html")
        app.dependency_overrides.clear()
        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_render_error_returns_500(self):
        """A RenderError from PrintService must produce a structured 500."""
        from apps.zds.api.main import app
        from apps.zds.api.core.dependencies import get_print_service
        from apps.zds.api.services.exceptions import RenderError

        class ExplodingPrintService:
            async def render_week_html(self, week_id):
                raise RenderError("Renderer exploded")

        app.dependency_overrides[get_print_service] = lambda: ExplodingPrintService()

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/print/week/any-week.html")
        app.dependency_overrides.clear()

        assert r.status_code == 500
        body = r.json()
        assert body["detail"]["error"] == "render_failed"
        assert "detail" in body["detail"]

    @pytest.mark.asyncio
    async def test_openapi_schema_includes_print_routes(self):
        """OpenAPI schema must expose all four print endpoints."""
        from apps.zds.api.main import app
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/openapi.json")
        assert r.status_code == 200
        paths = r.json()["paths"]
        assert "/v1/print/week/{week_id}.html" in paths
        assert "/v1/print/week/{week_id}.pdf"  in paths
        assert "/v1/print/night/{night_id}.html" in paths
        assert "/v1/print/night/{night_id}.pdf"  in paths


# ═════════════════════════════════════════════════════════════════════════════
# Tier 2 — Adapter transparency test (requires DB env vars)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.tier2
class TestPrintAPIAdapterTransparency:
    """Assert that /v1/print/week/{id}.html output equals direct renderer output.

    If these differ, PrintService is mutating the renderer's output — investigate.

    Two paths tested:
      1. fresh_html (direct renderer call via source xlsx + DB) vs nothing —
         just verifies the renderer is producing content.
      2. fresh_html_via_api (fetched from a running PrintService) vs fresh_html —
         verifies the API adapter is transparent (no mutations in the HTTP layer).

    The second test is skipped if PRINT_SERVICE_URL + PRINT_SERVICE_WEEK_ID
    are not set (they require a running Forge API server).
    """

    @staticmethod
    def _html_to_normalised_text(html_path: Path) -> str:
        """Strip all HTML tags, collapse whitespace, return plain text."""
        import re
        raw = html_path.read_text(encoding="utf-8")
        stripped = re.sub(r"<[^>]+>", " ", raw)
        return normalise_text(stripped)

    @pytest.mark.asyncio
    async def test_direct_render_produces_content(self, fresh_html):
        """Renderer must produce a non-trivially long HTML output.

        Verifies the renderer is generating real content (not an empty page or
        error shell) via the direct render path.  Skipped without DB env vars.
        """
        if not _has_db_env():
            pytest.skip("DB env vars not set — Tier 2 adapter transparency test skipped")

        text = self._html_to_normalised_text(fresh_html)
        assert len(text) > 500, (
            f"Direct render produced suspiciously short output ({len(text)} chars). "
            "Check the fresh_html fixture and the source xlsx."
        )

    @pytest.mark.asyncio
    async def test_api_html_matches_direct_render(self, fresh_html, fresh_html_via_api):
        """HTML from the API endpoint must have the same text content as a
        direct render.

        Both outputs are stripped of HTML tags and whitespace-normalised before
        comparison, so minor formatting differences (attribute ordering, extra
        newlines) don't produce false failures — only content differences matter.

        Skipped if:
          - SUPABASE_URL / SUPABASE_SERVICE_KEY not set (no direct render)
          - PRINT_SERVICE_URL / PRINT_SERVICE_WEEK_ID not set (no API render)
          - Forge API server unreachable (fresh_html_via_api fixture auto-skips)
        """
        if not _has_db_env():
            pytest.skip("DB env vars not set — skipped")
        if not has_print_service_env():
            pytest.skip(
                "PRINT_SERVICE_URL / PRINT_SERVICE_WEEK_ID not set — "
                "start the Forge API and export those vars to enable this test"
            )

        direct_text = self._html_to_normalised_text(fresh_html)
        api_text    = self._html_to_normalised_text(fresh_html_via_api)

        assert direct_text and api_text, "One or both renders produced empty text"

        # Exact match required — any divergence means the API layer is mutating
        # the renderer's output, which violates the sacred-renderer contract.
        if direct_text != api_text:
            # Print first divergence point to aid diagnosis.
            min_len = min(len(direct_text), len(api_text))
            first_diff = next(
                (i for i in range(min_len) if direct_text[i] != api_text[i]),
                min_len,
            )
            ctx = slice(max(0, first_diff - 80), first_diff + 80)
            pytest.fail(
                f"API HTML text diverges from direct render at char {first_diff}.\n"
                f"  Direct context: {direct_text[ctx]!r}\n"
                f"  API    context: {api_text[ctx]!r}\n\n"
                "PrintService is altering the renderer's output — investigate "
                "print_service.py between render and HTTP response."
            )
