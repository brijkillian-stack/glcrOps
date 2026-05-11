"""
update_golden.py — Regenerate golden master images + text from the source golden PDF.

Run this only when:
  - First-time setup (after placing the golden PDF in golden/)
  - An APPROVED layout change has been signed off by Brian
  - The source PDF is replaced with a new canonical version

DO NOT run this to "fix" a failing regression test — that defeats the
test's purpose. A failure means the renderer drifted; investigate first.

Usage:
    python -m tests.print_regression.update_golden

    # Or from repo root with the --week flag to specify a different week:
    python -m tests.print_regression.update_golden --week 2026-05-14
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


GOLDEN_DIR = Path(__file__).parent / "golden"
DPI = 150   # High enough to catch visual drift; low enough for fast CI.
            # Calibrated: at 150 DPI a 1mm layout shift is ~6 pixels — well
            # above the SSIM 0.98 threshold. Changing this value requires
            # regenerating all golden PNGs (run this script again).


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate golden master from a source PDF."
    )
    parser.add_argument(
        "--week",
        default="2026-05-14",
        help="ISO week-ending date (YYYY-MM-DD). Determines source PDF filename.",
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

    week = args.week
    dpi  = args.dpi

    source_pdf = GOLDEN_DIR / f"zone_deployment_book_{week}.pdf"
    pages_dir  = GOLDEN_DIR / f"zone_deployment_book_{week}"
    text_path  = GOLDEN_DIR / f"zone_deployment_book_{week}_text.json"
    manifest   = GOLDEN_DIR / "manifest.json"

    # ── Pre-flight ────────────────────────────────────────────────────────
    if not source_pdf.exists():
        print(
            f"ERROR: Source golden PDF not found at:\n  {source_pdf}\n\n"
            "Place the canonical PDF there before running this script.\n"
            "Do NOT re-render it from current code — the whole point is that\n"
            "this file is the pre-approved snapshot of truth.",
            file=sys.stderr,
        )
        return 1

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
            "Install with: pip install pdf2image pypdf Pillow",
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
        # Normalise whitespace so minor PDF-layer diffs don't trip the test.
        # Collapse runs of whitespace to a single space; strip leading/trailing.
        import re
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
        "regenerated_at":  datetime.utcnow().isoformat() + "Z",
    }
    manifest.write_text(json.dumps(manifest_data, indent=2))

    print(
        f"\n✓ Golden master regenerated:\n"
        f"  {len(images)} pages at {dpi} DPI\n"
        f"  SHA-256: {source_hash[:16]}…\n"
        f"\nCommit everything in tests/print_regression/golden/ to the repo.\n"
        f"These files are the regression contract — treat them as sacred."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
