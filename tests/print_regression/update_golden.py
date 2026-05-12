"""
update_golden.py — Regenerate golden master artifacts from a source PDF.

Run this only when:
  - First-time setup (after placing the golden PDF in golden/)
  - An APPROVED layout change has been signed off by Brian
  - Migrating to a new golden source (e.g. browser-print → PrintService)

DO NOT run this to "fix" a failing regression test — that defeats the
test's purpose. A failure means the renderer drifted; investigate first.

Usage
─────
  # Source: manually-placed browser-print PDF (classic workflow)
  python -m tests.print_regression.update_golden --week 2026-05-14

  # Source: fetch PDF from a running PrintService instance
  python -m tests.print_regression.update_golden \\
      --source print-service \\
      --service-url http://localhost:8001 \\
      --service-week-id <week-uuid-from-db>

  # Use env vars instead of flags:
  PRINT_REGRESSION_WEEK=2026-05-14 \\
  PRINT_SERVICE_URL=http://localhost:8001 \\
  PRINT_SERVICE_WEEK_ID=<uuid> \\
  python -m tests.print_regression.update_golden --source print-service

Updating to PrintService goldens (Brian approval workflow)
──────────────────────────────────────────────────────────
  1. Start the Forge API: uvicorn apps.zds.api.main:app --port 8001
  2. Look up the week UUID:
       SELECT id FROM weeks WHERE week_ending = '2026-05-14';
  3. Run with --source print-service (flags or env vars above).
  4. Open the generated PDF and page PNGs — confirm they match what
     Brian visually approved.
  5. Commit golden/ with message:
       "Golden master regenerated from PrintService — Brian approved YYYY-MM-DD"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


GOLDEN_DIR = Path(__file__).parent / "golden"
DPI = 150   # High enough to catch visual drift; low enough for fast CI.
            # Calibrated: at 150 DPI a 1mm layout shift is ~6 pixels — well
            # above the SSIM 0.98 threshold. Changing this value requires
            # regenerating all golden PNGs (run this script again).


# ── PDF source helpers ────────────────────────────────────────────────────────

def _require_browser_pdf(source_pdf: Path) -> None:
    """Verify the manually-placed browser-print PDF is present."""
    if not source_pdf.exists():
        print(
            f"ERROR: Source golden PDF not found at:\n  {source_pdf}\n\n"
            "Place the canonical browser-print PDF there, OR use:\n"
            "  --source print-service  to fetch it from the Forge API.",
            file=sys.stderr,
        )
        sys.exit(1)


def _fetch_from_print_service(service_url: str, week_id: str, dest_pdf: Path) -> None:
    """Fetch the golden PDF from a running PrintService instance.

    The PrintService produces PDFs via weasyprint from the sacred renderer's
    HTML output.  This is the canonical source for new golden artifacts once
    Phase 3 (print endpoints) is in production.
    """
    try:
        import httpx
    except ImportError:
        print(
            "ERROR: httpx required for --source print-service.\n"
            "Install: pip install httpx",
            file=sys.stderr,
        )
        sys.exit(1)

    endpoint = f"{service_url.rstrip('/')}/v1/print/week/{week_id}.pdf"
    print(f"Fetching PDF from {endpoint}…")

    try:
        resp = httpx.get(endpoint, timeout=300)  # weasyprint cold render can take 2-5 min
    except Exception as exc:
        print(f"ERROR: Could not reach PrintService — {exc}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 404:
        print(
            f"ERROR: 404 — week {week_id!r} not found in the DB.\n"
            "Verify PRINT_SERVICE_WEEK_ID is the correct UUID from public.weeks.",
            file=sys.stderr,
        )
        sys.exit(1)
    if resp.status_code != 200:
        print(
            f"ERROR: PrintService returned {resp.status_code}:\n{resp.text[:500]}",
            file=sys.stderr,
        )
        sys.exit(1)

    dest_pdf.write_bytes(resp.content)
    print(f"  Saved {len(resp.content):,} bytes → {dest_pdf.name}")


def _fetch_html_render_locally(service_url: str, week_id: str, dest_pdf: Path) -> None:
    """Fetch HTML from the server; render PDF locally with weasyprint.

    Preferred over ``--source print-service`` on macOS dev machines where
    weasyprint's system libraries are present locally but may be unavailable
    inside the uvicorn process (hardened runtime, DYLD_LIBRARY_PATH stripping,
    or first-run font-cache latency causing the server request to hang).

    The HTML served by the print endpoint is identical to what the server would
    feed to weasyprint, so the resulting PDF is byte-equivalent.
    """
    try:
        import httpx
    except ImportError:
        print(
            "ERROR: httpx required for --source print-service-html.\n"
            "Install: pip install httpx",
            file=sys.stderr,
        )
        sys.exit(1)

    html_endpoint = f"{service_url.rstrip('/')}/v1/print/week/{week_id}.html"
    print(f"Fetching HTML from {html_endpoint}…")

    try:
        resp = httpx.get(html_endpoint, timeout=60)
    except Exception as exc:
        print(f"ERROR: Could not reach PrintService — {exc}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 404:
        print(
            f"ERROR: 404 — week {week_id!r} not found in the DB.\n"
            "Verify PRINT_SERVICE_WEEK_ID is the correct UUID from public.weeks.",
            file=sys.stderr,
        )
        sys.exit(1)
    if resp.status_code != 200:
        print(
            f"ERROR: PrintService returned {resp.status_code}:\n{resp.text[:500]}",
            file=sys.stderr,
        )
        sys.exit(1)

    html_content = resp.text
    print(f"  Got {len(resp.content):,} bytes of HTML")

    # Apply the same WeasyPrint compatibility injection that PrintService uses
    # for PDF endpoints.  The renderer's HTML is designed for browser Cmd+P;
    # WeasyPrint needs Flexbox overrides to resolve fr-unit heights correctly.
    try:
        sys.path.insert(0, str(Path(__file__).parents[2]))  # repo root on sys.path
        from apps.zds.api.services.print_service import PrintService
        html_content = PrintService._inject_weasyprint_compat(html_content)
        print("  WeasyPrint compat CSS injected.")
    except Exception as exc:
        print(f"WARNING: Could not inject WeasyPrint compat CSS — {exc}", file=sys.stderr)

    print("Rendering PDF locally with weasyprint (may take 1-3 min on first run)…")
    try:
        from weasyprint import HTML as WP_HTML  # type: ignore[import]
    except ImportError:
        print(
            "ERROR: weasyprint not installed.\n"
            "Install: pip install weasyprint",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        WP_HTML(string=html_content).write_pdf(str(dest_pdf))
    except Exception as exc:
        print(f"ERROR: weasyprint render failed — {exc}", file=sys.stderr)
        sys.exit(1)

    size = dest_pdf.stat().st_size
    print(f"  Rendered {size:,} bytes → {dest_pdf.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    manifest_week = ""
    if (GOLDEN_DIR / "manifest.json").exists():
        try:
            manifest_week = json.loads((GOLDEN_DIR / "manifest.json").read_text()).get("week_key", "")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Regenerate golden master artifacts from a source PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--week",
        default=os.environ.get("PRINT_REGRESSION_WEEK") or manifest_week or None,
        metavar="YYYY-MM-DD",
        help=(
            "ISO week-ending date.  Defaults to PRINT_REGRESSION_WEEK env var, "
            "then manifest.json week_key.  Required if neither is set."
        ),
    )
    parser.add_argument(
        "--source",
        choices=["browser-pdf", "print-service", "print-service-html"],
        default="browser-pdf",
        help=(
            "Where to get the golden PDF.  "
            "'browser-pdf' = manually placed in golden/ (classic).  "
            "'print-service' = fetch PDF from running Forge API (server needs weasyprint).  "
            "'print-service-html' = fetch HTML from server, render PDF locally (preferred on macOS)."
        ),
    )
    parser.add_argument(
        "--service-url",
        default=os.environ.get("PRINT_SERVICE_URL", ""),
        metavar="URL",
        help="PrintService base URL (env: PRINT_SERVICE_URL). Required for --source print-service.",
    )
    parser.add_argument(
        "--service-week-id",
        default=os.environ.get("PRINT_SERVICE_WEEK_ID", ""),
        metavar="UUID",
        help="Week UUID in public.weeks (env: PRINT_SERVICE_WEEK_ID). Required for --source print-service.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DPI,
        help=f"Render DPI for page PNGs (default: {DPI}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing golden artifacts without prompting.",
    )
    args = parser.parse_args(argv)

    if not args.week:
        parser.error(
            "--week is required (or set PRINT_REGRESSION_WEEK env var).  "
            "Example: --week 2026-05-14"
        )

    week = args.week
    dpi  = args.dpi

    source_pdf = GOLDEN_DIR / f"zone_deployment_book_{week}.pdf"
    pages_dir  = GOLDEN_DIR / f"zone_deployment_book_{week}"
    text_path  = GOLDEN_DIR / f"zone_deployment_book_{week}_text.json"
    manifest   = GOLDEN_DIR / "manifest.json"

    # ── Obtain the source PDF ─────────────────────────────────────────────
    if args.source in ("print-service", "print-service-html"):
        if not args.service_url:
            parser.error(f"--service-url (or PRINT_SERVICE_URL) required for --source {args.source}")
        if not args.service_week_id:
            parser.error(f"--service-week-id (or PRINT_SERVICE_WEEK_ID) required for --source {args.source}")
        if args.source == "print-service":
            _fetch_from_print_service(args.service_url, args.service_week_id, source_pdf)
        else:
            _fetch_html_render_locally(args.service_url, args.service_week_id, source_pdf)
    else:
        _require_browser_pdf(source_pdf)

    # ── Confirm overwrite ─────────────────────────────────────────────────
    if pages_dir.exists() and any(pages_dir.glob("page_*.png")) and not args.force:
        answer = input(
            f"\nGolden images already exist in {pages_dir}/.\n"
            "Regenerating will overwrite them. Proceed? [y/N] "
        ).strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted. Run with --force to skip this prompt.")
            return 0

    try:
        from pdf2image import convert_from_path
        from pypdf import PdfReader
    except ImportError as exc:
        print(
            f"ERROR: Missing dependency — {exc}.\n"
            "Install: pip install pdf2image pypdf Pillow",
            file=sys.stderr,
        )
        return 1

    # ── Step 1: render page images ────────────────────────────────────────
    print(f"Rendering {source_pdf.name} at {dpi} DPI…")
    pages_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(source_pdf, dpi=dpi, fmt="png")
    for idx, img in enumerate(images, start=1):
        out = pages_dir / f"page_{idx:02d}.png"
        img.save(out, optimize=True)
        print(f"  page_{idx:02d}.png  ({img.width}×{img.height})")

    # ── Step 2: extract per-page text ─────────────────────────────────────
    print("Extracting text…")
    reader = PdfReader(source_pdf)
    text_by_page: dict[str, str] = {}
    for i, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        normalised = re.sub(r"\s+", " ", raw).strip()
        text_by_page[f"page_{i:02d}"] = normalised
        print(f"  page_{i:02d}: {len(normalised)} chars")

    text_path.write_text(json.dumps(text_by_page, indent=2, ensure_ascii=False))

    # ── Step 3: write manifest ────────────────────────────────────────────
    source_hash = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    manifest_data = {
        "week_key":        week,
        "source_pdf":      source_pdf.name,
        "source_sha256":   source_hash,
        "page_count":      len(images),
        "render_dpi":      dpi,
        "golden_source":   args.source,
        "regenerated_at":  datetime.now(timezone.utc).isoformat(),
    }
    manifest.write_text(json.dumps(manifest_data, indent=2))

    print(
        f"\n✓ Golden master regenerated:\n"
        f"  {len(images)} pages at {dpi} DPI\n"
        f"  SHA-256: {source_hash[:16]}…\n"
        f"  Source:  {args.source}\n"
        f"\nNext steps:\n"
        f"  1. Open the PDF and inspect all {len(images)} pages visually.\n"
        f"  2. Get Brian's explicit sign-off.\n"
        f"  3. Commit everything in tests/print_regression/golden/ with message:\n"
        f'     "Golden master regenerated from {args.source} — Brian approved YYYY-MM-DD"\n'
        f"\nThe golden files are the regression contract — treat them as sacred."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
