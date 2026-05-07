"""
shared/components/admin_section_head.py — Admin hub section header + breadcrumb.

Two exports:
  admin_section_head(title)  — gold-accent section header for the 3-column
                                card groups on /admin.
  admin_breadcrumb(section, page_title)
                             — 11px eyebrow sub-bar shown at the top of
                               /admin/* sub-pages (today, deployment, engine).
                               Renders:  ← Sudo Admin  ·  {section}  ·  {page_title}
"""

import reflex as rx


def admin_section_head(title: str) -> rx.Component:
    """Section header: Eb-style label + 22px gold rule below.

    Matches the SectionHead atom in shift-hud-hifi.jsx:
      Eb ink2 label · 2px × 22px gold bar below.
    """
    return rx.el.div(
        rx.el.div(
            title,
            style={
                "fontSize": "10px",
                "fontWeight": "700",
                "letterSpacing": "0.14em",
                "textTransform": "uppercase",
                "color": "var(--ink2)",
                "fontFamily": "var(--font)",
            },
        ),
        rx.el.div(
            style={
                "height": "2px",
                "width": "22px",
                "background": "var(--gold)",
                "marginTop": "5px",
            },
        ),
        style={"marginBottom": "12px"},
    )


def admin_breadcrumb(section: str, page_title: str) -> rx.Component:
    """Sub-bar shown at top of /admin/* pages.

    Layout:  ← Sudo Admin  ·  {section}  ·  {page_title}
    Style:   11px, ink3, 0.08em tracking, uppercase. Link is var(--blue).
    """
    _sep = rx.el.span(
        "·",
        style={"color": "var(--line2)", "padding": "0 4px"},
    )

    return rx.el.div(
        rx.el.a(
            "← Sudo Admin",
            href="/admin",
            style={
                "color": "var(--blue)",
                "textDecoration": "none",
                "fontWeight": "600",
            },
        ),
        _sep,
        rx.el.span(
            section,
            style={"color": "var(--ink3)"},
        ),
        _sep,
        rx.el.span(
            page_title,
            style={"color": "var(--ink2)", "fontWeight": "600"},
        ),
        class_name="admin-breadcrumb",
    )
