"""
Annotation context menu component (Phase 4k.3 / refactored 4k.3.1).

Single global overlay mounted once in deployment(). The menu_target_kind
state var drives which root subview renders:
  "task"  → task annotation options   (4k.3 — live)
  "tm"    → TM annotation options     (4k.4 — stub returning rx.fragment())
  "card"  → card annotation options   (4k.5 — stub returning rx.fragment())

Sub-menus (color picker, symbol picker, note editor) are SHARED across all
three target_kind values via the same menu_subview switcher.

The symbol picker uses inline GLCR SVG icons (via glcr_icons.py) instead
of unicode glyphs, storing {"section": ..., "slug": ...} JSONB so the PDF
renderer can reproduce them exactly via glcr_icon().
"""

from __future__ import annotations

import reflex as rx

from ..state import ZdsState
from .glcr_icons import glcr_icon


# ── Highlight color palette (6 colors — Phase 4k.3.1 adds purple) ────────────

_HL_COLORS: list[tuple[str, str]] = [
    ("yellow", "var(--c-yellow)"),
    ("red",    "var(--c-red)"),
    ("green",  "var(--c-green)"),
    ("blue",   "var(--c-blue)"),
    ("purple", "var(--c-purple)"),
    ("orange", "var(--c-orange)"),
]

# ── Symbol palette (8 GLCR icons — Phase 4k.3.1 replaces unicode chars) ─────
# Each tuple: (section, slug, display_label)
_SYMBOLS: list[tuple[str, str, str]] = [
    ("ui",     "star-favorite",  "Priority"),
    ("ui",     "pin-bookmark",   "Remember"),
    ("status", "warning",        "Watch"),
    ("status", "info",           "Note"),
    ("status", "clock-pending",  "Time-sensitive"),
    ("ops",    "alerts",         "Alert"),
    ("maint",  "inspection",     "Inspect"),
    ("maint",  "safety-check",   "Safety"),
]


# ── Shared sub-components ─────────────────────────────────────────────────────

def _back_link(label: str = "← Back") -> rx.Component:
    return rx.el.button(
        label,
        on_click=ZdsState.set_menu_subview("root"),
        style={
            "background": "none",
            "border":     "none",
            "cursor":     "pointer",
            "fontSize":   "11px",
            "color":      "var(--ink3, #6b7280)",
            "padding":    "0",
            "fontFamily": "var(--font, sans-serif)",
        },
    )


def _menu_btn(
    label: str,
    icon: str,
    on_click,
    danger: bool = False,
) -> rx.Component:
    color = "#ef4444" if danger else "var(--ink1, #111827)"
    return rx.el.button(
        rx.el.span(icon,  style={"marginRight": "8px", "fontSize": "14px"}),
        rx.el.span(label, style={"fontSize": "12px"}),
        on_click=on_click,
        style={
            "display":    "flex",
            "alignItems": "center",
            "width":      "100%",
            "padding":    "6px 12px",
            "border":     "none",
            "background": "transparent",
            "cursor":     "pointer",
            "color":      color,
            "fontFamily": "var(--font, sans-serif)",
            "textAlign":  "left",
        },
    )


# ── Shared sub-menus (color / symbol / note) ──────────────────────────────────

def _color_view() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _back_link(),
            rx.el.span(
                "Choose highlight",
                style={"fontSize": "11px", "color": "var(--ink3, #6b7280)",
                       "marginLeft": "8px"},
            ),
            style={"display": "flex", "alignItems": "center",
                   "padding": "6px 12px 4px"},
        ),
        rx.el.div(
            *[
                rx.el.button(
                    style={
                        "width":        "28px",
                        "height":       "28px",
                        "borderRadius": "50%",
                        "background":   hex_val,
                        "border":       "2px solid white",
                        "boxShadow":    "0 0 0 1px rgba(0,0,0,0.15)",
                        "cursor":       "pointer",
                    },
                    on_click=ZdsState.set_task_highlight(color_key),
                    title=color_key,
                )
                for color_key, hex_val in _HL_COLORS
            ],
            style={"display": "flex", "gap": "8px", "padding": "8px 12px",
                   "flexWrap": "wrap"},
        ),
    )


def _symbol_view() -> rx.Component:
    """Symbol picker — 8 GLCR SVG icons loaded inline via glcr_icons.py."""
    return rx.el.div(
        rx.el.div(
            _back_link(),
            rx.el.span(
                "Choose symbol",
                style={"fontSize": "11px", "color": "var(--ink3, #6b7280)",
                       "marginLeft": "8px"},
            ),
            style={"display": "flex", "alignItems": "center",
                   "padding": "6px 12px 4px"},
        ),
        rx.el.div(
            *[
                rx.el.button(
                    rx.html(glcr_icon(section, slug, size=18, css_class="sym-icon")),
                    rx.el.span(
                        label,
                        style={"fontSize": "10px", "display": "block",
                               "textAlign": "center", "marginTop": "2px",
                               "color": "var(--ink3, #6b7280)"},
                    ),
                    on_click=ZdsState.set_task_symbol(section, slug),
                    title=label,
                    style={
                        "display":       "flex",
                        "flexDirection": "column",
                        "alignItems":    "center",
                        "background":    "none",
                        "border":        "1px solid #e5e7eb",
                        "borderRadius":  "6px",
                        "padding":       "6px 8px",
                        "cursor":        "pointer",
                        "minWidth":      "48px",
                    },
                )
                for section, slug, label in _SYMBOLS
            ],
            style={"display": "flex", "gap": "6px", "padding": "8px 12px",
                   "flexWrap": "wrap"},
        ),
    )


def _note_view() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            _back_link(),
            style={"padding": "6px 12px 4px"},
        ),
        rx.el.div(
            rx.text_area(
                value=ZdsState.menu_note_text,
                on_change=ZdsState.set_menu_note_text,
                placeholder="Short note for this task tonight…",
                rows="3",
                size="1",
                width="100%",
                resize="none",
                auto_focus=True,
            ),
            rx.button(
                "Save note",
                on_click=ZdsState.save_task_note,
                size="1",
                color_scheme="blue",
                width="100%",
                margin_top="6px",
                cursor="pointer",
            ),
            style={"padding": "4px 12px 10px"},
        ),
    )


# ── Root subviews by target_kind ──────────────────────────────────────────────

def _menu_task_root() -> rx.Component:
    """Root menu for target_kind="task" (4k.3)."""
    return rx.el.div(
        # Header — task name
        rx.el.div(
            ZdsState.menu_target_name,
            style={
                "padding":       "6px 12px 4px",
                "fontSize":      "11px",
                "fontWeight":    "700",
                "color":         "var(--ink3, #6b7280)",
                "textTransform": "uppercase",
                "letterSpacing": "0.06em",
                "borderBottom":  "1px solid rgba(0,0,0,0.06)",
                "fontFamily":    "var(--font, sans-serif)",
            },
        ),
        _menu_btn("Highlight color",      "🎨", ZdsState.set_menu_subview("color")),
        _menu_btn("Symbol",               "◈",  ZdsState.set_menu_subview("symbol")),
        _menu_btn("Add / edit note",      "📝",  ZdsState.set_menu_subview("note")),
        rx.el.div(style={"height": "1px", "background": "rgba(0,0,0,0.06)",
                         "margin": "2px 0"}),
        _menu_btn("Skip tonight",          "🚫", ZdsState.toggle_task_skip),
        _menu_btn("Clear all annotations", "✕",  ZdsState.clear_task_annotation,
                  danger=True),
    )


def _tm_note_view(
    save_handler,
    caption: str,
    placeholder: str = "Short note…",
) -> rx.Component:
    """Shared note-editor subview for TM pre-shift note and profile-log.

    Reuses menu_note_text + set_menu_note_text from the generic menu_* namespace.
    `save_handler` is the ZdsState event to fire on Save.
    """
    return rx.el.div(
        rx.el.div(
            _back_link(),
            rx.el.span(
                caption,
                style={"fontSize": "10px", "color": "var(--ink3, #6b7280)",
                       "marginLeft": "8px", "fontFamily": "var(--font, sans-serif)"},
            ),
            style={"display": "flex", "alignItems": "center",
                   "padding": "6px 12px 4px"},
        ),
        rx.el.div(
            rx.text_area(
                value=ZdsState.menu_note_text,
                on_change=ZdsState.set_menu_note_text,
                placeholder=placeholder,
                rows="3",
                size="1",
                width="100%",
                resize="none",
                auto_focus=True,
            ),
            rx.button(
                "Save",
                on_click=save_handler,
                size="1",
                color_scheme="blue",
                width="100%",
                margin_top="6px",
                cursor="pointer",
            ),
            style={"padding": "4px 12px 10px"},
        ),
    )


def _menu_tm_root() -> rx.Component:
    """Root menu for target_kind="tm" — Phase 4k.4."""
    # has_note is True when the TM already has a pre-shift note this night.
    has_note = ZdsState.tm_annotation_data.contains(ZdsState.menu_target_ref)

    return rx.el.div(
        # Header — TM name
        rx.el.div(
            ZdsState.menu_target_name,
            style={
                "padding":       "6px 12px 4px",
                "fontSize":      "11px",
                "fontWeight":    "700",
                "color":         "var(--ink3, #6b7280)",
                "textTransform": "uppercase",
                "letterSpacing": "0.06em",
                "borderBottom":  "1px solid rgba(0,0,0,0.06)",
                "fontFamily":    "var(--font, sans-serif)",
            },
        ),
        _menu_btn(
            "Add pre-shift note",
            rx.html(glcr_icon("actions", "edit-pencil", size=14)),
            ZdsState.set_menu_subview("tm_preshift_note"),
        ),
        _menu_btn(
            "Log observation to TM profile",
            rx.html(glcr_icon("ui", "pin-bookmark", size=14)),
            ZdsState.set_menu_subview("tm_profile_log"),
        ),
        _menu_btn(
            "View TM profile",
            rx.html(glcr_icon("people", "person-user", size=14)),
            ZdsState.navigate_to_tm_profile,
        ),
        rx.el.div(style={"height": "1px", "background": "rgba(0,0,0,0.06)",
                         "margin": "2px 0"}),
        rx.cond(
            has_note,
            _menu_btn(
                "Clear pre-shift note",
                rx.html(glcr_icon("actions", "delete-trash", size=14)),
                ZdsState.clear_tm_note,
                danger=True,
            ),
            rx.fragment(),
        ),
        _menu_btn(
            "Cancel",
            rx.html(glcr_icon("ui", "close-x", size=14)),
            ZdsState.close_menu,
        ),
    )


def _card_adhoc_input_view() -> rx.Component:
    """Subview: text field for adding a new adhoc task to the current card."""
    return rx.el.div(
        rx.el.div(
            _back_link(),
            rx.el.span(
                "Add an ad-hoc task to this zone",
                style={"fontSize": "10px", "color": "var(--ink3, #6b7280)",
                       "marginLeft": "8px", "fontFamily": "var(--font, sans-serif)"},
            ),
            style={"display": "flex", "alignItems": "center",
                   "padding": "6px 12px 4px"},
        ),
        rx.el.div(
            rx.text_area(
                value=ZdsState.menu_note_text,
                on_change=ZdsState.set_menu_note_text,
                placeholder="Task description…",
                rows="2",
                size="1",
                width="100%",
                resize="none",
                auto_focus=True,
            ),
            rx.button(
                "Add task",
                on_click=ZdsState.add_card_adhoc_task,
                size="1",
                color_scheme="blue",
                width="100%",
                margin_top="6px",
                cursor="pointer",
            ),
            style={"padding": "4px 12px 10px"},
        ),
    )


def _card_adhoc_manage_view() -> rx.Component:
    """Subview: list existing adhoc tasks for the current card with delete buttons."""
    return rx.el.div(
        rx.el.div(
            _back_link(),
            rx.el.span(
                "Ad-hoc tasks",
                style={"fontSize": "10px", "color": "var(--ink3, #6b7280)",
                       "marginLeft": "8px", "fontFamily": "var(--font, sans-serif)"},
            ),
            style={"display": "flex", "alignItems": "center",
                   "padding": "6px 12px 4px"},
        ),
        rx.el.div(
            rx.foreach(
                ZdsState.card_menu_adhoc_tasks,
                lambda task: rx.el.div(
                    rx.el.span(
                        task["name"],
                        style={"fontSize": "12px", "flex": "1",
                               "fontFamily": "var(--font, sans-serif)",
                               "color": "var(--ink1, #111827)"},
                    ),
                    rx.el.button(
                        rx.html(glcr_icon("actions", "delete-trash", size=12)),
                        on_click=ZdsState.delete_card_adhoc_task(task["ref"]),
                        style={
                            "background": "none", "border": "none",
                            "cursor": "pointer", "color": "#ef4444",
                            "padding": "2px 4px",
                        },
                        title="Remove",
                    ),
                    style={"display": "flex", "alignItems": "center",
                           "gap": "8px", "padding": "4px 0"},
                ),
            ),
            rx.button(
                "Add another",
                on_click=ZdsState.set_menu_subview("card_adhoc_input"),
                size="1",
                variant="soft",
                width="100%",
                margin_top="6px",
                cursor="pointer",
            ),
            style={"padding": "4px 12px 10px"},
        ),
    )


def _menu_card_root() -> rx.Component:
    """Root menu for target_kind="card" — Phase 4k.5."""
    has_adhoc = ZdsState.card_menu_adhoc_tasks.length() > 0

    return rx.el.div(
        # Header — card code
        rx.el.div(
            ZdsState.menu_target_name,
            style={
                "padding":       "6px 12px 4px",
                "fontSize":      "11px",
                "fontWeight":    "700",
                "color":         "var(--ink3, #6b7280)",
                "textTransform": "uppercase",
                "letterSpacing": "0.06em",
                "borderBottom":  "1px solid rgba(0,0,0,0.06)",
                "fontFamily":    "var(--font, sans-serif)",
            },
        ),
        _menu_btn(
            "Add ad-hoc task",
            rx.html(glcr_icon("actions", "add-new", size=14)),
            ZdsState.set_menu_subview("card_adhoc_input"),
        ),
        rx.cond(
            has_adhoc,
            _menu_btn(
                "Manage ad-hoc tasks",
                rx.html(glcr_icon("ui", "menu-hamburger", size=14)),
                ZdsState.set_menu_subview("card_adhoc_manage"),
            ),
            rx.fragment(),
        ),
        _menu_btn(
            "Add / edit note",
            rx.html(glcr_icon("actions", "edit-pencil", size=14)),
            ZdsState.set_menu_subview("card_note_input"),
        ),
        _menu_btn(
            rx.cond(
                ZdsState.card_menu_has_priority,
                "Remove priority ★",
                "Mark as priority ★",
            ),
            rx.html(glcr_icon("ui", "star-favorite", size=14)),
            ZdsState.toggle_card_priority,
        ),
        _menu_btn(
            "Print this card",
            rx.html(glcr_icon("actions", "print", size=14)),
            ZdsState.print_single_card,
        ),
        rx.el.div(style={"height": "1px", "background": "rgba(0,0,0,0.06)",
                         "margin": "2px 0"}),
        rx.cond(
            ZdsState.card_menu_has_note,
            _menu_btn(
                "Clear note",
                rx.html(glcr_icon("actions", "delete-trash", size=14)),
                ZdsState.clear_card_note,
                danger=True,
            ),
            rx.fragment(),
        ),
        _menu_btn(
            "Cancel",
            rx.html(glcr_icon("ui", "close-x", size=14)),
            ZdsState.close_menu,
        ),
    )


# ── Root component ────────────────────────────────────────────────────────────

def task_annotation_menu() -> rx.Component:
    """Global annotation context menu. Mount once in deployment()."""
    # Subview switcher — shared across all target_kinds
    subview_content = rx.match(
        ZdsState.menu_subview,
        ("color",  _color_view()),
        ("symbol", _symbol_view()),
        ("note",   _note_view()),
        # Phase 4k.4 — TM note-editor subviews
        ("tm_preshift_note", _tm_note_view(
            ZdsState.save_tm_preshift_note,
            caption="Pre-shift note (prints on tonight's deployment)",
            placeholder="Short note for tonight's deployment…",
        )),
        ("tm_profile_log", _tm_note_view(
            ZdsState.log_tm_to_profile,
            caption="Log observation to TM Profile (captures to Memory Backend; 📌 prints on deployment)",
            placeholder="Observation about this TM tonight…",
        )),
        # Phase 4k.5 — card annotation subviews
        ("card_adhoc_input",  _card_adhoc_input_view()),
        ("card_adhoc_manage", _card_adhoc_manage_view()),
        ("card_note_input", _tm_note_view(
            ZdsState.save_card_note,
            caption="Card note (prints on deployment page under zone header)",
            placeholder="Note about this zone tonight…",
        )),
        # default: route to the appropriate root by target_kind
        rx.cond(
            ZdsState.menu_target_kind == "task",
            _menu_task_root(),
            rx.cond(
                ZdsState.menu_target_kind == "tm",
                _menu_tm_root(),
                rx.cond(
                    ZdsState.menu_target_kind == "card",
                    _menu_card_root(),
                    rx.fragment(),
                ),
            ),
        ),
    )

    return rx.cond(
        ZdsState.menu_open,
        rx.el.div(
            # Backdrop — click outside to dismiss
            rx.el.div(
                on_click=ZdsState.close_menu,
                style={"position": "fixed", "inset": "0", "zIndex": "998"},
            ),
            # Panel
            rx.el.div(
                subview_content,
                style={
                    "position": "fixed",
                    "left": rx.cond(
                        ZdsState.menu_x.to(int) > 800,
                        f"{ZdsState.menu_x - 200}px",
                        f"{ZdsState.menu_x}px",
                    ),
                    "top":          f"{ZdsState.menu_y}px",
                    "zIndex":       "999",
                    "background":   "white",
                    "border":       "1px solid #e5e7eb",
                    "borderRadius": "8px",
                    "boxShadow":    "0 8px 24px rgba(0,0,0,0.12)",
                    "minWidth":     "200px",
                    "overflow":     "hidden",
                },
            ),
        ),
        rx.fragment(),
    )
