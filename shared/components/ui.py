"""
components/ui.py — Primitive UI components
chip, kpi_card, feed_row, task_card, brewing_card
"""

import reflex as rx


def chip(label: str, variant: str = "") -> rx.Component:
    cls = f"chip chip-{variant}" if variant else "chip"
    return rx.el.span(label, class_name=cls)


def status_dot(variant: str = "") -> rx.Component:
    cls = f"dot dot-{variant}" if variant else "dot"
    return rx.el.span(class_name=cls)


def kpi_card(
    label: str,
    value,
    delta="",
    delta_direction="flat",
    value_color: str = "",
) -> rx.Component:
    # Never use Python `if` on value_color — it may be a Reflex Var, and
    # Var.__bool__ raises VarTypeError. Always pass the style dict; an empty
    # string color is ignored by browsers (falls back to inherited color).
    value_style = {"color": value_color}
    delta_cls = rx.cond(
        delta_direction == "up",
        "kpi-delta up",
        rx.cond(delta_direction == "down", "kpi-delta down", "kpi-delta flat"),
    )
    return rx.el.div(
        rx.el.div(
            rx.el.div(label, class_name="kpi-label"),
            rx.el.div(delta, class_name=delta_cls),
        ),
        rx.el.div(value, class_name="kpi-value", style=value_style),
        class_name="kpi",
    )


def feed_row(item: dict) -> rx.Component:
    # Build icon class via rx.cond so Reflex gets Var[str] instead of Var[Any].
    # Dict access inside foreach returns Any, which class_name rejects at compile time.
    icon_cls = rx.cond(
        item["note_type"] == "kudos",
        "feed-icon feed-icon-gold",
        rx.cond(
            item["note_type"] == "flag",
            "feed-icon feed-icon-flag",
            rx.cond(
                item["note_type"] == "incident",
                "feed-icon feed-icon-flag",
                rx.cond(
                    item["note_type"] == "beo",
                    "feed-icon feed-icon-flag",
                    rx.cond(
                        item["note_type"] == "callout",
                        "feed-icon feed-icon-flag",
                        rx.cond(
                            item["note_type"] == "huddle",
                            "feed-icon feed-icon-blue",
                            rx.cond(
                                item["note_type"] == "floor_walk",
                                "feed-icon feed-icon-blue",
                                "feed-icon",  # observation, recap, request, etc.
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    return rx.el.div(
        rx.el.div(item["timestamp_display"], class_name="feed-time"),
        rx.el.div(item["icon"], class_name=icon_cls),
        rx.el.div(item["text"], class_name="feed-text"),
        class_name="feed-item",
    )


def task_card(item: dict) -> rx.Component:
    is_overdue = item["is_overdue"]
    priority   = item["priority"]
    title      = item["title"]
    category   = item["category"]
    due_date   = item["due_date"]

    leading_cls = rx.cond(
        is_overdue,
        "card-leading priority-urgent",
        rx.cond(
            priority == "urgent",
            "card-leading priority-urgent",
            rx.cond(
                priority == "high",
                "card-leading priority-high",
                rx.cond(
                    priority == "normal",
                    "card-leading priority-normal",
                    "card-leading priority-low",
                ),
            ),
        ),
    )
    chip_variant = rx.cond(is_overdue, "flag", "blue")
    chip_label   = rx.cond(is_overdue, "overdue", category)

    return rx.el.div(
        rx.el.div(
            rx.el.span(class_name=leading_cls),
            rx.el.div(
                rx.el.p(title, class_name="card-title"),
                rx.el.div(
                    rx.el.span(
                        chip_label,
                        class_name=rx.cond(
                            is_overdue, "chip chip-flag", "chip chip-blue"
                        ),
                    ),
                    rx.cond(
                        due_date != "",
                        rx.el.span(due_date, style={"font_size": "11px", "color": "var(--fg-3)"}),
                        rx.fragment(),
                    ),
                    class_name="card-meta",
                ),
                class_name="card-body",
            ),
            class_name="card-row",
        ),
        class_name="card",
    )


def brewing_card(item: dict) -> rx.Component:
    priority = item["priority"]
    title    = item["title"]
    excerpt  = item["excerpt"]

    leading_cls = rx.cond(
        priority == "urgent",
        "card-leading priority-urgent",
        rx.cond(
            priority == "high",
            "card-leading priority-high",
            "card-leading priority-normal",
        ),
    )

    return rx.el.div(
        rx.el.div(
            rx.el.span(class_name=leading_cls),
            rx.el.div(
                rx.el.p(title, class_name="card-title"),
                rx.cond(
                    excerpt != "",
                    rx.el.p(excerpt, class_name="card-excerpt"),
                    rx.fragment(),
                ),
                class_name="card-body",
            ),
            class_name="card-row",
        ),
        class_name="card",
    )


def skeleton_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            class_name="skeleton",
            style={"height": "14px", "width": "70%", "margin_bottom": "8px"},
        ),
        rx.el.div(
            class_name="skeleton",
            style={"height": "11px", "width": "40%"},
        ),
        class_name="card",
        style={"padding_top": "14px"},
    )


def empty_state(title: str, sub: str = "") -> rx.Component:
    return rx.el.div(
        rx.el.p(title, class_name="empty-title"),
        rx.cond(
            sub != "",
            rx.el.p(sub, class_name="empty-sub"),
            rx.fragment(),
        ),
        class_name="empty",
    )
