"""
ZDS Forge — Full endpoint integration test suite.

Covers every public API endpoint with happy-path, error, caching, and
content-shape assertions.  Tests are marked ``integration`` and skipped
automatically when the server env vars are absent so CI Tier 1/2 is
unaffected.

Environment
───────────
  PRINT_SERVICE_URL      Base URL of a running Forge instance (e.g. http://localhost:8001)
  PRINT_SERVICE_WEEK_ID  UUID from: SELECT id FROM weeks WHERE week_ending='2026-05-14'
  PRINT_SERVICE_NIGHT_ID UUID from: SELECT id FROM nights WHERE week_id='<above>' LIMIT 1

Quick run
─────────
  uvicorn apps.zds.api.main:app --port 8001 &
  export PRINT_SERVICE_URL=http://localhost:8001
  export PRINT_SERVICE_WEEK_ID=7f31103a-4bcd-4f65-99e8-dd6bbae580a9
  export PRINT_SERVICE_NIGHT_ID=$(python3 -c "
      import os; from dotenv import load_dotenv; load_dotenv()
      import sys; sys.path.insert(0,'.')
      from apps.zds import database
      rows = database._client().table('nights').select('id').eq('week_id', os.environ['PRINT_SERVICE_WEEK_ID']).limit(1).execute()
      print(rows.data[0]['id'])
  ")
  pytest tests/integration/ -v
"""

from __future__ import annotations

import os
import re
import time

import pytest

# ── Env ───────────────────────────────────────────────────────────────────────

BASE_URL  = os.environ.get("PRINT_SERVICE_URL",      "").rstrip("/")
WEEK_ID   = os.environ.get("PRINT_SERVICE_WEEK_ID",  "").strip()
NIGHT_ID  = os.environ.get("PRINT_SERVICE_NIGHT_ID", "").strip()

FAKE_UUID = "00000000-0000-0000-0000-000000000000"

pytestmark = pytest.mark.integration


def _has_server() -> bool:
    return bool(BASE_URL and WEEK_ID)


def _has_night() -> bool:
    return _has_server() and bool(NIGHT_ID)


def _client():
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed — pip install httpx")
    return httpx.Client(base_url=BASE_URL, timeout=90)


def _skip():
    if not _has_server():
        pytest.skip(
            "Set PRINT_SERVICE_URL + PRINT_SERVICE_WEEK_ID to run integration tests. "
            "Start the Forge API first: uvicorn apps.zds.api.main:app --port 8001"
        )


def _pdf_ok(r) -> bool:
    """True unless the server reports weasyprint is not installed."""
    if r.status_code == 500:
        try:
            if r.json().get("detail", {}).get("error") == "render_failed":
                return False
        except Exception:
            pass
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Health / meta
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    """GET /health — always available, no auth, no DB required."""

    def setup_method(self):
        _skip()

    def test_health_200(self):
        with _client() as c:
            r = c.get("/health")
        assert r.status_code == 200

    def test_health_json_shape(self):
        with _client() as c:
            r = c.get("/health")
        body = r.json()
        assert body.get("status") == "ok"
        assert "service" in body

    def test_health_fast(self):
        """Health check must respond in under 2 seconds."""
        with _client() as c:
            t0 = time.monotonic()
            r = c.get("/health")
            elapsed = time.monotonic() - t0
        assert r.status_code == 200
        assert elapsed < 2.0, f"Health endpoint took {elapsed:.2f}s — should be <2s"


# ══════════════════════════════════════════════════════════════════════════════
# Week HTML — GET /v1/print/week/{id}.html
# ══════════════════════════════════════════════════════════════════════════════

class TestWeekHtml:
    """Happy path, content shape, headers, caching, error cases."""

    def setup_method(self):
        _skip()

    def test_200_for_valid_week(self):
        with _client() as c:
            r = c.get(f"/v1/print/week/{WEEK_ID}.html")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"

    def test_content_type_html(self):
        with _client() as c:
            r = c.get(f"/v1/print/week/{WEEK_ID}.html")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_body_size_at_least_100kb(self):
        """A real 14-page book must be ≥ 100 KB of HTML."""
        with _client() as c:
            r = c.get(f"/v1/print/week/{WEEK_ID}.html")
        assert r.status_code == 200
        assert len(r.content) >= 100_000, (
            f"Week HTML only {len(r.content):,} bytes — renderer returned an error page."
        )

    def test_html_contains_14_articles(self):
        """The HTML must contain exactly 14 page articles (7 zone + 7 break)."""
        with _client() as c:
            r = c.get(f"/v1/print/week/{WEEK_ID}.html")
        assert r.status_code == 200
        count = r.text.count('class="page"') + r.text.count('class="page break-page"')
        # Count opening <article> tags only
        import re as _re
        articles = _re.findall(r'<article\s+class="page[^"]*"', r.text)
        assert len(articles) == 14, (
            f"Expected 14 article pages, found {len(articles)}. "
            "Page count regression — check the renderer."
        )

    def test_cache_control_private(self):
        with _client() as c:
            r = c.get(f"/v1/print/week/{WEEK_ID}.html")
        assert r.status_code == 200
        cc = r.headers.get("cache-control", "")
        assert cc, "Cache-Control header missing"
        assert "private" in cc, f"Expected 'private' in Cache-Control, got: {cc!r}"

    def test_content_disposition_inline(self):
        with _client() as c:
            r = c.get(f"/v1/print/week/{WEEK_ID}.html")
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd
        assert ".html" in cd
        assert "attachment" not in cd

    def test_deterministic_consecutive_calls(self):
        """Two calls return byte-identical bodies (cache is stable)."""
        with _client() as c:
            r1 = c.get(f"/v1/print/week/{WEEK_ID}.html")
            r2 = c.get(f"/v1/print/week/{WEEK_ID}.html")
        assert r1.status_code == r2.status_code == 200
        assert r1.content == r2.content, (
            "Consecutive week HTML calls returned different content — "
            "cache layer broken or renderer is non-deterministic."
        )

    def test_404_for_fake_uuid(self):
        with _client() as c:
            r = c.get(f"/v1/print/week/{FAKE_UUID}.html")
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "not_found"

    def test_404_body_is_json(self):
        with _client() as c:
            r = c.get(f"/v1/print/week/{FAKE_UUID}.html")
        assert "application/json" in r.headers.get("content-type", "")


# ══════════════════════════════════════════════════════════════════════════════
# Week PDF — GET /v1/print/week/{id}.pdf
# ══════════════════════════════════════════════════════════════════════════════

class TestWeekPdf:

    def setup_method(self):
        _skip()

    def _get_pdf(self, client, week_id: str = WEEK_ID):
        r = client.get(f"/v1/print/week/{week_id}.pdf")
        if not _pdf_ok(r):
            pytest.skip("PDF render unavailable — WeasyPrint not installed on server")
        return r

    def test_200_for_valid_week(self):
        with _client() as c:
            r = self._get_pdf(c)
        assert r.status_code == 200

    def test_content_type_pdf(self):
        with _client() as c:
            r = self._get_pdf(c)
        assert r.headers.get("content-type") == "application/pdf"

    def test_pdf_magic_bytes(self):
        with _client() as c:
            r = self._get_pdf(c)
        assert r.content[:4] == b"%PDF", f"Not a PDF: {r.content[:20]!r}"

    def test_pdf_size_at_least_200kb(self):
        """A 14-page landscape PDF must be at least 200 KB."""
        with _client() as c:
            r = self._get_pdf(c)
        assert len(r.content) >= 200_000, (
            f"Week PDF only {len(r.content):,} bytes — may be truncated or empty."
        )

    def test_content_disposition_inline(self):
        with _client() as c:
            r = self._get_pdf(c)
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd
        assert ".pdf" in cd
        assert "attachment" not in cd

    def test_404_for_fake_uuid(self):
        with _client() as c:
            r = c.get(f"/v1/print/week/{FAKE_UUID}.pdf")
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "not_found"


# ══════════════════════════════════════════════════════════════════════════════
# Night HTML — GET /v1/print/night/{id}.html
# ══════════════════════════════════════════════════════════════════════════════

class TestNightHtml:

    def setup_method(self):
        _skip()
        if not _has_night():
            pytest.skip(
                "Set PRINT_SERVICE_NIGHT_ID to run night-endpoint tests. "
                f"SELECT id FROM nights WHERE week_id='{WEEK_ID}' LIMIT 1"
            )

    def test_200_for_valid_night(self):
        with _client() as c:
            r = c.get(f"/v1/print/night/{NIGHT_ID}.html")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"

    def test_content_type_html(self):
        with _client() as c:
            r = c.get(f"/v1/print/night/{NIGHT_ID}.html")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_body_size_at_least_20kb(self):
        """A single night (2 pages) must be at least 20 KB."""
        with _client() as c:
            r = c.get(f"/v1/print/night/{NIGHT_ID}.html")
        assert r.status_code == 200
        assert len(r.content) >= 20_000

    def test_html_contains_2_articles(self):
        """Night HTML must have exactly 2 pages: zone + break."""
        with _client() as c:
            r = c.get(f"/v1/print/night/{NIGHT_ID}.html")
        assert r.status_code == 200
        articles = re.findall(r'<article\s+class="page[^"]*"', r.text)
        assert len(articles) == 2, (
            f"Expected 2 article pages for a single night, found {len(articles)}."
        )

    def test_content_disposition_inline(self):
        with _client() as c:
            r = c.get(f"/v1/print/night/{NIGHT_ID}.html")
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd
        assert ".html" in cd

    def test_404_for_fake_uuid(self):
        with _client() as c:
            r = c.get(f"/v1/print/night/{FAKE_UUID}.html")
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "not_found"


# ══════════════════════════════════════════════════════════════════════════════
# Night PDF — GET /v1/print/night/{id}.pdf
# ══════════════════════════════════════════════════════════════════════════════

class TestNightPdf:

    def setup_method(self):
        _skip()
        if not _has_night():
            pytest.skip("Set PRINT_SERVICE_NIGHT_ID to run night-endpoint tests.")

    def test_200_or_skip_if_weasyprint_absent(self):
        with _client() as c:
            r = c.get(f"/v1/print/night/{NIGHT_ID}.pdf")
        if not _pdf_ok(r):
            pytest.skip("WeasyPrint not installed on server")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"

    def test_404_for_fake_uuid(self):
        with _client() as c:
            r = c.get(f"/v1/print/night/{FAKE_UUID}.pdf")
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Planning overview — GET /v1/planning/weekly/{id}
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanningWeekly:

    def setup_method(self):
        _skip()

    def test_200_for_valid_week(self):
        with _client() as c:
            r = c.get(f"/v1/planning/weekly/{WEEK_ID}")
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"

    def test_content_type_json(self):
        with _client() as c:
            r = c.get(f"/v1/planning/weekly/{WEEK_ID}")
        assert "application/json" in r.headers.get("content-type", "")

    def test_response_top_level_keys(self):
        """Response must contain all required top-level keys."""
        required = {"week", "nights", "metrics", "planning_notes",
                    "active_overrides", "links", "cached_at"}
        with _client() as c:
            body = c.get(f"/v1/planning/weekly/{WEEK_ID}").json()
        missing = required - set(body)
        assert not missing, f"Planning response missing keys: {missing}"

    def test_week_id_in_response_matches_request(self):
        with _client() as c:
            body = c.get(f"/v1/planning/weekly/{WEEK_ID}").json()
        assert body["week"]["id"] == WEEK_ID

    def test_nights_is_list_of_7(self):
        """A GLCR week is always Fri–Thu = 7 nights."""
        with _client() as c:
            body = c.get(f"/v1/planning/weekly/{WEEK_ID}").json()
        nights = body.get("nights", [])
        assert isinstance(nights, list)
        assert len(nights) == 7, (
            f"Expected 7 nights in planning response, got {len(nights)}."
        )

    def test_links_reference_correct_week_endpoints(self):
        with _client() as c:
            body = c.get(f"/v1/planning/weekly/{WEEK_ID}").json()
        links = body["links"]
        assert WEEK_ID in links["print_week_html"]
        assert WEEK_ID in links["print_week_pdf"]
        assert links["print_week_html"].endswith(".html")
        assert links["print_week_pdf"].endswith(".pdf")

    def test_cache_control_max_age_le_15(self):
        """Planning is a live tool — max-age must be ≤ 15 s."""
        with _client() as c:
            r = c.get(f"/v1/planning/weekly/{WEEK_ID}")
        cc = r.headers.get("cache-control", "")
        m = re.search(r"max-age=(\d+)", cc)
        assert m, f"No max-age in Cache-Control: {cc!r}"
        assert int(m.group(1)) <= 15

    def test_metrics_present_and_typed(self):
        """metrics block must have fill_rate and staffing_gap as numbers."""
        with _client() as c:
            body = c.get(f"/v1/planning/weekly/{WEEK_ID}").json()
        metrics = body.get("metrics", {})
        assert "fill_rate" in metrics,    "metrics.fill_rate missing"
        assert "staffing_gap" in metrics, "metrics.staffing_gap missing"
        assert isinstance(metrics["fill_rate"],    (int, float))
        assert isinstance(metrics["staffing_gap"], (int, float))

    def test_404_for_fake_uuid(self):
        with _client() as c:
            r = c.get(f"/v1/planning/weekly/{FAKE_UUID}")
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "not_found"

    def test_consecutive_calls_return_same_week_id(self):
        """Cache must not serve a different week on a second hit."""
        with _client() as c:
            b1 = c.get(f"/v1/planning/weekly/{WEEK_ID}").json()
            b2 = c.get(f"/v1/planning/weekly/{WEEK_ID}").json()
        assert b1["week"]["id"] == b2["week"]["id"]
