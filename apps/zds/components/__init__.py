"""Reflex UI components for the ZDS frontend.

These imports require ``reflex`` to be installed.  When the package is
loaded in API-only mode (e.g. the Forge FastAPI server on Render, where
reflex is intentionally not installed), the reflex components are simply
unavailable — but pure-Python submodules like ``glcr_icons`` still import
cleanly because they don't go through this __init__.
"""

try:
    from .zone_card import zone_card, rr_card, aux_card
    from .tm_picker import tm_picker_drawer
    from .night_tabs import night_tab_bar
    from .save_banner import save_banner

    __all__ = [
        "zone_card", "rr_card", "aux_card",
        "tm_picker_drawer",
        "night_tab_bar",
        "save_banner",
    ]
except ImportError:
    # Reflex not installed — API-only deployment.
    # glcr_icons and other pure-Python submodules remain importable.
    __all__ = []
