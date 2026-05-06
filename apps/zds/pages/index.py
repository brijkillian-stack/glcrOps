"""Landing page — week selector."""

import reflex as rx
from ..state import ZdsState
from ..components.zds_header import zds_header


def _week_card(week: dict) -> rx.Component:
    """A week row — title, status, linked schedule, primary + secondary actions.
    Phase P: dense single-row layout with linked-schedule visibility + reset/unlink."""
    title = rx.cond(week["label"] != "", week["label"], week["week_ending"])
    status_color = rx.cond(
        week["status"] == "published", "green",
        rx.cond(week["status"] == "archived", "gray", "yellow")
    )
    has_schedule = week["schedule_path"] != ""
    return rx.box(
        rx.hstack(
            # Left: title + week_ending + linked schedule
            rx.vstack(
                rx.hstack(
                    rx.icon("calendar-days", size=15, color="#0065BF"),
                    rx.text(title, weight="bold", size="3"),
                    rx.badge(
                        week["status"],
                        color_scheme=status_color,
                        size="1",
                        style={"fontSize": "9px", "padding": "1px 6px"},
                    ),
                    gap="6px", align="center",
                ),
                rx.hstack(
                    rx.text(
                        rx.cond(
                            week["date_range"] != "",
                            week["date_range"],
                            week["week_ending"],
                        ),
                        size="1", color="#9ca3af",
                        font_variant_numeric="tabular-nums",
                    ),
                    rx.cond(
                        has_schedule,
                        rx.hstack(
                            rx.icon("link-2", size=10, color="#059669"),
                            rx.text(week["schedule_path"], size="1", color="#059669",
                                    style={"fontFamily": "ui-monospace, monospace"}),
                            gap="3px", align="center",
                        ),
                        rx.hstack(
                            rx.icon("unlink", size=10, color="#9ca3af"),
                            rx.text("no schedule linked", size="1",
                                    color="#9ca3af", style={"fontStyle": "italic"}),
                            gap="3px", align="center",
                        ),
                    ),
                    gap="10px", align="center", flex_wrap="wrap",
                ),
                gap="2px", align="start", flex="1",
            ),
            rx.spacer(),
            # Right: actions
            rx.hstack(
                rx.button(
                    rx.icon("layout-dashboard", size=13), "Open",
                    size="1", color_scheme="blue",
                    on_click=ZdsState.open_week(week["id"]),
                ),
                rx.menu.root(
                    rx.menu.trigger(
                        rx.icon_button(
                            rx.icon("ellipsis-vertical", size=14),
                            variant="ghost", size="1", color_scheme="gray",
                            cursor="pointer",
                        ),
                    ),
                    rx.menu.content(
                        rx.menu.item(
                            rx.hstack(
                                rx.icon("upload", size=13, color="#0ea5e9"),
                                rx.text("Reset from new upload"),
                                gap="8px", align="center",
                            ),
                            on_click=ZdsState.open_reset_week_modal(week["id"], title),
                        ),
                        rx.cond(
                            has_schedule,
                            rx.menu.item(
                                rx.hstack(
                                    rx.icon("unlink", size=13, color="#9ca3af"),
                                    rx.text("Unlink schedule"),
                                    gap="8px", align="center",
                                ),
                                on_click=ZdsState.unlink_schedule_from_week(week["id"]),
                            ),
                            rx.fragment(),
                        ),
                        rx.cond(
                            week["status"] == "draft",
                            rx.fragment(
                                rx.menu.separator(),
                                rx.menu.item(
                                    rx.hstack(
                                        rx.icon("check-check", size=13, color="#059669"),
                                        rx.text("Publish"),
                                        gap="8px", align="center",
                                    ),
                                    on_click=ZdsState.update_week_status(
                                        week["id"], "published",
                                    ),
                                ),
                            ),
                            rx.fragment(),
                        ),
                    ),
                ),
                gap="6px", align="center",
            ),
            width="100%", align="center", gap="10px",
        ),
        background="white",
        border="1px solid #e5e7eb",
        border_radius="8px",
        padding="10px 14px",
        _hover={"box_shadow": "0 2px 8px rgba(0,0,0,0.06)",
                "border_color": "#dbeafe"},
        transition="all 0.15s ease",
        width="100%",
        class_name="week-night-card",
    )


def _new_week_modal() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("New Deployment Week"),
            rx.vstack(
                rx.text("Week ending (Wednesday)", size="2", weight="medium"),
                rx.input(
                    type="date",
                    value=ZdsState.new_week_ending,
                    on_change=ZdsState.set_new_week_ending,
                    width="100%",
                ),
                rx.text("Label", size="2", weight="medium"),
                rx.input(
                    placeholder="e.g. Week of May 7",
                    value=ZdsState.new_week_label,
                    on_change=ZdsState.set_new_week_label,
                    width="100%",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("Cancel", variant="ghost",
                                  on_click=ZdsState.close_new_week_modal),
                    ),
                    rx.button("Create Week", color_scheme="blue",
                              on_click=ZdsState.create_week),
                    gap="8px", justify="end", width="100%",
                ),
                gap="8px", width="100%",
            ),
            max_width="400px",
        ),
        open=ZdsState.show_new_week,
        on_open_change=ZdsState.close_new_week_modal,
    )


def _unlinked_schedule_row(item: dict) -> rx.Component:
    """One row in the 'Schedules without Zone Sheet' list.

    Item shape (from database.list_unlinked_schedules):
        filename, week_ending, dates[7], matching_week | None
    """
    # Button label adapts: link existing week vs create a new one.
    btn_label = rx.cond(
        item["matching_week"],
        "Link to existing week",
        "Create Zone Sheet",
    )
    btn_icon = rx.cond(item["matching_week"], "link-2", "plus")
    return rx.hstack(
        rx.icon("calendar-clock", size=16, color="#0065BF"),
        rx.vstack(
            rx.text(
                "Week ending ", item["week_ending"],
                size="2", weight="bold",
            ),
            rx.text(item["filename"], size="1", color="#9ca3af"),
            gap="0",
            align="start",
        ),
        rx.spacer(),
        rx.button(
            rx.icon(btn_icon, size=13),
            btn_label,
            size="2",
            color_scheme="blue",
            variant="soft",
            cursor="pointer",
            on_click=ZdsState.create_week_from_schedule(item["filename"]),
        ),
        width="100%",
        align="center",
        padding="10px 14px",
        background="white",
        border="1px solid #dbeafe",
        border_radius="8px",
    )


def _unlinked_schedules_section() -> rx.Component:
    """Phase H — surfaces schedules in Storage that aren't yet linked to a Week."""
    return rx.cond(
        ZdsState.unlinked_schedules.length() > 0,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon("file-spreadsheet", size=15, color="#0065BF"),
                    rx.text(
                        "Schedules without a Zone Sheet",
                        size="2", weight="bold",
                    ),
                    rx.spacer(),
                    rx.badge(
                        ZdsState.unlinked_schedules.length(),
                        color_scheme="blue",
                        variant="soft",
                    ),
                    width="100%", align="center",
                ),
                rx.text(
                    "Click to create a Zone Sheet from the schedule, "
                    "or link the schedule to an existing week.",
                    size="1", color="#9ca3af",
                ),
                rx.vstack(
                    rx.foreach(ZdsState.unlinked_schedules, _unlinked_schedule_row),
                    gap="6px", width="100%",
                ),
                gap="8px", width="100%",
            ),
            padding="14px 16px",
            background="#eaf4ff",
            border="1px solid #bfdbfe",
            border_radius="10px",
            width="100%",
        ),
        rx.fragment(),
    )


def _humanize_size(n: int) -> str:
    """Reflex-side static helper — only used in component construction so
    we can pass plain ints to a static formatter (Vars handle the rendering)."""
    return f"{n:,} B"


def _managed_schedule_row(item: dict) -> rx.Component:
    """Phase P — single-row tight layout for a stored schedule."""
    is_delete_target  = ZdsState.delete_target_filename  == item["filename"]
    is_replace_target = ZdsState.replace_target_filename == item["filename"]
    is_linked         = item["linked_week_id"] != ""
    return rx.box(
        rx.hstack(
            rx.icon("file-spreadsheet", size=14, color="#0065BF"),
            rx.vstack(
                rx.hstack(
                    rx.text(item["filename"], size="2", weight="bold",
                            style={"whiteSpace": "nowrap", "overflow": "hidden",
                                   "textOverflow": "ellipsis"}),
                    rx.cond(
                        is_linked,
                        rx.hstack(
                            rx.icon("link-2", size=10, color="#0369a1"),
                            rx.text(item["linked_week_label"], size="1", color="#0369a1"),
                            gap="3px", align="center",
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        is_replace_target,
                        rx.badge("Replacing — drop file below", color_scheme="amber",
                                 variant="solid", font_size="9px"),
                        rx.fragment(),
                    ),
                    gap="6px", align="center", flex_wrap="wrap",
                ),
                rx.text(
                    rx.cond(
                        item["week_ending"] != "",
                        rx.fragment("Week ending ", item["week_ending"], "  ·  ",
                                    item["size_bytes"].to_string(), " bytes"),
                        rx.fragment(item["size_bytes"].to_string(), " bytes"),
                    ),
                    size="1", color="#9ca3af",
                ),
                gap="0", align="start", flex="1",
            ),
            rx.spacer(),
            # Action buttons OR delete confirmation
            rx.cond(
                is_delete_target,
                rx.hstack(
                    rx.text("Delete this schedule?", size="1", color="#dc2626"),
                    rx.button(
                        "Cancel",
                        size="1", variant="soft", color_scheme="gray",
                        on_click=ZdsState.cancel_delete_schedule,
                    ),
                    rx.button(
                        rx.icon("trash-2", size=12), "Delete",
                        size="1", color_scheme="red",
                        on_click=ZdsState.confirm_delete_schedule,
                    ),
                    gap="6px", align="center",
                ),
                rx.hstack(
                    rx.cond(
                        is_replace_target,
                        rx.button(
                            "Cancel replace",
                            size="1", variant="soft", color_scheme="gray",
                            on_click=ZdsState.cancel_replace_schedule,
                        ),
                        rx.button(
                            rx.icon("upload", size=12), "Replace",
                            size="1", variant="soft", color_scheme="amber",
                            on_click=ZdsState.request_replace_schedule(item["filename"]),
                        ),
                    ),
                    # Phase P — Unlink action (only when this file is linked to a week)
                    rx.cond(
                        is_linked,
                        rx.button(
                            rx.icon("unlink", size=12), "Unlink",
                            size="1", variant="ghost", color_scheme="gray",
                            on_click=ZdsState.unlink_schedule_from_week(
                                item["linked_week_id"],
                            ),
                            title="Detach this file from its linked week",
                        ),
                        rx.fragment(),
                    ),
                    rx.button(
                        rx.icon("trash-2", size=12),
                        size="1", variant="ghost", color_scheme="red",
                        on_click=ZdsState.request_delete_schedule(item["filename"]),
                        title="Delete this schedule",
                    ),
                    gap="4px", align="center",
                ),
            ),
            width="100%", align="center", gap="10px",
        ),
        padding="8px 12px",
        background="white",
        border=rx.cond(
            is_delete_target,
            "1px solid #fecaca",
            rx.cond(is_replace_target, "1px solid #fbbf24", "1px solid #e5e7eb"),
        ),
        border_radius="6px",
    )


def _managed_schedules_section() -> rx.Component:
    """Phase N.1 — Manage Schedules panel."""
    return rx.cond(
        ZdsState.managed_schedules.length() > 0,
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.icon("layers", size=15, color="#6b7280"),
                    rx.text("Schedules in Storage", size="2", weight="bold"),
                    rx.spacer(),
                    rx.badge(
                        ZdsState.managed_schedules.length(),
                        color_scheme="gray", variant="soft",
                    ),
                    width="100%", align="center",
                ),
                rx.vstack(
                    rx.foreach(ZdsState.managed_schedules, _managed_schedule_row),
                    gap="6px", width="100%",
                ),
                gap="8px", width="100%",
            ),
            padding="14px 16px",
            background="#f9fafb",
            border="1px solid #e5e7eb",
            border_radius="10px",
            width="100%",
        ),
        rx.fragment(),
    )


def _schedule_upload_section() -> rx.Component:
    """Phase P — compact single-row upload widget. The full management lives
    in the Schedules in Storage panel below."""
    return rx.box(
        rx.hstack(
            rx.icon("calendar-check", size=14, color="#6b7280"),
            rx.text("Weekly Schedule", size="2", weight="bold"),
            rx.cond(
                ZdsState.schedule_loaded,
                rx.hstack(
                    rx.text("·", size="1", color="#d1d5db"),
                    rx.text(
                        ZdsState.schedule_file_label,
                        size="1", color="#6b7280",
                        style={"fontFamily": "ui-monospace, monospace"},
                    ),
                    rx.icon("circle-check", size=11, color="#059669"),
                    gap="6px", align="center",
                ),
                rx.text(" — none loaded", size="1", color="#9ca3af",
                        style={"fontStyle": "italic"}),
            ),
            rx.spacer(),
            rx.upload(
                rx.button(
                    rx.icon("upload", size=12),
                    rx.cond(ZdsState.schedule_loaded, "Replace", "Upload"),
                    size="1",
                    variant="soft",
                    color_scheme=rx.cond(ZdsState.schedule_loaded, "gray", "blue"),
                    cursor="pointer",
                ),
                id="schedule_upload",
                accept={
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
                },
                max_files=1,
                on_drop=ZdsState.handle_schedule_upload(
                    rx.upload_files(upload_id="schedule_upload")
                ),
                no_drag=True,
            ),
            width="100%", align="center", gap="8px", flex_wrap="wrap",
        ),
        background="white",
        border="1px solid #e5e7eb",
        border_radius="8px",
        padding="10px 14px",
        width="100%",
    )


def _reset_week_modal() -> rx.Component:
    """Phase P — drop a fresh xlsx and reset the week to it. Wipes existing
    placements + overrides on confirm."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Reset week from new upload"),
            rx.vstack(
                rx.text(
                    "Drop a new schedule for ",
                    rx.el.b(ZdsState.reset_week_target_label),
                    ". This will:",
                    size="2", color="#374151",
                ),
                rx.el.ul(
                    rx.el.li(
                        "Link this week to the uploaded file",
                        style={"fontSize": "13px", "color": "#374151"},
                    ),
                    rx.el.li(
                        "Clear every TM placement on the week (locks too)",
                        style={"fontSize": "13px", "color": "#dc2626"},
                    ),
                    rx.el.li(
                        "Wipe schedule overrides from the previous file",
                        style={"fontSize": "13px", "color": "#dc2626"},
                    ),
                    style={"paddingLeft": "20px", "margin": "0"},
                ),
                rx.text(
                    "Run the deployment engine afterward to repopulate.",
                    size="1", color="#9ca3af", style={"fontStyle": "italic"},
                ),
                rx.upload(
                    rx.box(
                        rx.icon("upload-cloud", size=24, color="#0ea5e9"),
                        rx.text("Drop xlsx here or click to choose",
                                size="2", weight="medium", color="#0ea5e9"),
                        style={
                            "display": "flex", "flexDirection": "column",
                            "alignItems": "center", "gap": "6px",
                            "padding": "20px",
                            "border": "2px dashed #7dd3fc",
                            "borderRadius": "8px",
                            "background": "#f0f9ff",
                            "cursor": "pointer",
                        },
                    ),
                    id="reset_week_upload",
                    accept={
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
                    },
                    max_files=1,
                    on_drop=ZdsState.handle_reset_week_upload(
                        rx.upload_files(upload_id="reset_week_upload"),
                    ),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("Cancel", variant="ghost",
                                  on_click=ZdsState.close_reset_week_modal),
                    ),
                    gap="8px", justify="end", width="100%",
                ),
                gap="12px", width="100%",
            ),
            max_width="480px",
        ),
        open=ZdsState.reset_week_open,
        on_open_change=ZdsState.close_reset_week_modal,
    )


def index() -> rx.Component:
    return rx.box(
        zds_header(
            title="GLCR · Grave Deployment",
            subtitle="Zone Sheet Viewer & Editor",
            right=rx.button(
                rx.icon("plus", size=14), "New Week",
                color_scheme="blue",
                on_click=ZdsState.open_new_week_modal,
            ),
        ),
        # Content
        rx.vstack(
            rx.cond(
                ZdsState.loading,
                rx.spinner(size="3"),
                rx.vstack(
                    rx.cond(
                        ZdsState.error != "",
                        rx.callout(ZdsState.error, color_scheme="red", icon="triangle-alert"),
                        rx.fragment(),
                    ),
                    # Schedule upload card
                    _schedule_upload_section(),
                    # Phase N.1 — full Manage Schedules panel
                    _managed_schedules_section(),
                    # Phase H — schedules with no Zone Sheet yet (creatable)
                    _unlinked_schedules_section(),
                    rx.cond(
                        ZdsState.weeks.length() == 0,
                        rx.vstack(
                            rx.icon("calendar-x", size=48, color="#d1d5db"),
                            rx.text("No weeks yet — create one to get started.",
                                    size="3", color="#9ca3af"),
                            align="center", padding="64px",
                        ),
                        rx.vstack(
                            rx.foreach(ZdsState.weeks, _week_card),
                            gap="12px", width="100%",
                        ),
                    ),
                    gap="12px", width="100%",
                ),
            ),
            padding="32px",
            max_width="720px",
            margin="0 auto",
            width="100%",
        ),
        _new_week_modal(),
        # Phase P — Reset week from new upload modal
        _reset_week_modal(),
        background="#f9fafb",
        min_height="100vh",
        class_name="zds-index-page",
        # Page-load is wired in apps/zds/routes.py (on_load=[ZdsState.load_weeks]).
        # Don't add a duplicate on_mount here or Supabase gets hit twice.
    )
