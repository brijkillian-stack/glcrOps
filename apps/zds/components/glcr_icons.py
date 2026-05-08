"""
GLCR icon loader (Phase 4k.3.1).

Reads SVG files from assets/icons/glcr/{section}/{slug}.svg and returns
them as inline SVG strings with injectable width/height/class attributes.
Caches reads to avoid repeated disk I/O in hot paths.

Callable from both Reflex components (at render time) and the PDF renderer.

Usage:
    from apps.zds.components.glcr_icons import glcr_icon
    svg_str = glcr_icon("ui", "star-favorite", size=16)
    svg_str = glcr_icon("status", "warning", size=12, css_class="task-symbol")
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

# Resolve relative to this file: apps/zds/components/ → up 3 → project root
ICONS_ROOT: Path = (
    Path(__file__).resolve().parent  # .../apps/zds/components
    .parent                          # .../apps/zds
    .parent                          # .../apps
    .parent                          # project root
    / "assets"
    / "icons"
    / "glcr"
)


@lru_cache(maxsize=256)
def _read_icon(section: str, slug: str) -> str:
    """Read and cache one SVG file. Raises FileNotFoundError if missing."""
    return (ICONS_ROOT / section / f"{slug}.svg").read_text(encoding="utf-8")


def glcr_icon(
    section: str,
    slug: str,
    *,
    size: int = 16,
    css_class: str = "",
) -> str:
    """Return inline SVG markup with width/height overridden and optional class.

    Args:
        section:   Icon directory name under assets/icons/glcr/
                   (e.g. "ui", "status", "ops", "maint")
        slug:      SVG filename without extension (e.g. "star-favorite")
        size:      Pixel size applied to both width and height attributes.
        css_class: Optional CSS class injected onto the <svg> element.

    Returns the full SVG string, ready for inline HTML embedding.

    Raises FileNotFoundError if the icon does not exist.
    """
    svg = _read_icon(section, slug)
    # Override width / height attributes (SVGs may have hardcoded values)
    svg = re.sub(r'\swidth="[^"]*"',  f' width="{size}"',  svg, count=1)
    svg = re.sub(r'\sheight="[^"]*"', f' height="{size}"', svg, count=1)
    if css_class:
        svg = svg.replace("<svg ", f'<svg class="{css_class}" ', 1)
    return svg
