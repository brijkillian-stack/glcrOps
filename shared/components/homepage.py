"""
shared/components/homepage.py — Phase: better homepage (2026-05-05)

Three-card launchpad rendered at /. Memory / Shift / ZDS, each tappable into
its own app surface. Static labels for v1; live data hookups (recent captures
feed, open-task counts, current week status) come in a follow-up.

Routes after the homepage lands:
    /               this homepage
    /today          GLCR Today (was /)
    /search, /people, /logs, /tasks, ...   GLCR Memory pages (unchanged)
    /zds/...        ZDS unchanged

After the Memory + Shift split (separate spec), the card targets evolve:
    Memory  → /memory or /search
    Shift   → /shift or /today
    ZDS     → /zds/
For now Memory and Shift point at their representative landing routes.
"""

import reflex as rx


def _app_card(
    *,
    href: str,
    name: str,
    tagline: str,
    glyph: str,
    accent_class: str,
) -> rx.Component:
    """One launchpad card. Anchor-styled link so iPad/Pencil tap is native."""
    return rx.link(
        rx.el.div(
            rx.el.div(glyph, class_name="home-card-glyph"),
            rx.el.div(
                rx.el.div(name, class_name="home-card-name"),
                rx.el.div(tagline, class_name="home-card-tagline"),
                class_name="home-card-text",
            ),
            class_name=f"home-card {accent_class}",
        ),
        href=href,
        class_name="home-card-link",
    )


def home_page() -> rx.Component:
    return rx.el.main(
        rx.el.div(
            # Header
            rx.el.div(
                rx.el.h1("Graves Ops", class_name="home-title"),
                rx.el.p(
                    "Pick a surface to enter.",
                    class_name="home-subtitle",
                ),
                class_name="home-header",
            ),

            # Three-card grid
            rx.el.div(
                _app_card(
                    href="/search",
                    name="Memory",
                    tagline="The brain — search, people, threads, write-ups, patterns.",
                    glyph="◎",
                    accent_class="home-card-memory",
                ),
                _app_card(
                    href="/today",
                    name="Shift",
                    tagline="Tonight — today, tasks, recap, floor walk, areas, deployment.",
                    glyph="⊙",
                    accent_class="home-card-shift",
                ),
                _app_card(
                    href="/zds/",
                    name="ZDS",
                    tagline="Zone Deployment — weekly schedules, fill engine, deployment book.",
                    glyph="▦",
                    accent_class="home-card-zds",
                ),
                class_name="home-cards",
            ),

            # Footer
            rx.el.div(
                rx.el.span(
                    "GLCR Ops · Internal Maintenance · Grave Shift",
                    class_name="home-footer-line",
                ),
                class_name="home-footer",
            ),
            class_name="home-page-inner",
        ),
        class_name="home-page",
    )
