"""
shared/components/homepage.py — Three-card launchpad at /.

Cards are role-aware. Memory card is editor-only — viewers see it dimmed
with an "Editor only" tagline; clicking it routes to /login instead of
/search. Today and ZDS are accessible to viewers and editors alike.
"""

import reflex as rx

from shared.auth import AuthState


def _app_card(
    *,
    href,
    name: str,
    tagline,
    glyph: str,
    accent_class: str,
    locked=False,
) -> rx.Component:
    """One launchpad card. `href`, `tagline`, and `locked` may be Vars.

    When `locked` is truthy, the card renders dimmed; pass an elevation
    href (e.g. /login) so a click on a locked card prompts editor sign-in.
    """
    base_class   = f"home-card {accent_class}"
    locked_class = f"home-card {accent_class} home-card-locked"
    return rx.link(
        rx.el.div(
            rx.el.div(glyph, class_name="home-card-glyph"),
            rx.el.div(
                rx.el.div(name, class_name="home-card-name"),
                rx.el.div(tagline, class_name="home-card-tagline"),
                class_name="home-card-text",
            ),
            class_name=rx.cond(locked, locked_class, base_class),
        ),
        href=href,
        class_name="home-card-link",
    )


def home_page() -> rx.Component:
    # Memory card — editor only. Viewers see it dimmed; click goes to /login.
    memory_href = rx.cond(
        AuthState.is_zds_editor,
        "/search",
        "/login",
    )
    memory_tagline = rx.cond(
        AuthState.is_zds_editor,
        "The brain — search, people, threads, write-ups, patterns.",
        "Editor only — sign in to access the memory corpus.",
    )

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
                    href=memory_href,
                    name="Memory",
                    tagline=memory_tagline,
                    glyph="◎",
                    accent_class="home-card-memory",
                    locked=~AuthState.is_zds_editor,
                ),
                _app_card(
                    href="/today",
                    name="Shift",
                    tagline="Tonight — today's deployment, current tasks, what's open.",
                    glyph="⊙",
                    accent_class="home-card-shift",
                ),
                _app_card(
                    href="/zds",
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
