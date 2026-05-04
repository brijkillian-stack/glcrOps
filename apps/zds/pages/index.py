"""Landing page — week selector."""

import reflex as rx
from ..state import ZdsState
from ..components.zds_header import zds_header


def _week_card(week: dict) -> rx.Component:
    # All values are Vars — use rx.cond, never Python `or`/`if` on them.
    title = rx.cond(week["label"] != "", week["label"], week["week_ending"])
    status_color = rx.cond(
        week["status"] == "published", "green",
        rx.cond(week["status"] == "archived", "gray", "yellow")
    )
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(title, weight="bold", size="4"),
                rx.spacer(),
                rx.badge(
                    week["status"],
                    color_scheme=status_color,
                    font_size="10px", padding="2px 8px", border_radius="full",
                ),
                width="100%", align="center",
            ),
            rx.text("Week ending ", week["week_ending"],
                    size="2", color="#6b7280"),
            rx.hstack(
                rx.button(
                    rx.icon("layout-dashboard", size=14), "Open Sheet",
                    size="2", color_scheme="blue",
                    on_click=ZdsState.open_week(week["id"]),
                ),
                rx.cond(
                    week["status"] == "draft",
                    rx.button(
                        rx.icon("check", size=14), "Publish",
                        size="2", variant="ghost", color_scheme="green",
                        on_click=ZdsState.update_week_status(week["id"], "published"),
                    ),
                    rx.fragment(),
                ),
                gap="8px", margin_top="8px",
            ),
            gap="4px", width="100%",
        ),
        background="white",
        border="1px solid #e5e7eb",
        border_radius="10px",
        padding="16px",
        _hover={"box_shadow": "0 2px 12px rgba(0,0,0,0.08)"},
        transition="box-shadow 0.15s ease",
        width="100%",
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


def _schedule_upload_section() -> rx.Component:
    """Card on the index page for uploading / replacing the weekly schedule file."""
    return rx.box(
        rx.vstack(
            # Row: icon + label + current file name
            rx.hstack(
                rx.icon("calendar-check", size=16, color="#6b7280"),
                rx.vstack(
                    rx.text("Weekly Schedule", size="2", weight="bold"),
                    rx.text(
                        ZdsState.schedule_file_label,
                        size="1", color="#9ca3af",
                    ),
                    gap="0",
                ),
                rx.spacer(),
                # Upload drop zone — styled as a button
                rx.upload(
                    rx.button(
                        rx.icon("upload", size=13),
                        rx.cond(
                            ZdsState.schedule_loaded,
                            "Replace Schedule",
                            "Upload Schedule",
                        ),
                        size="2",
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
                width="100%", align="center", gap="10px",
            ),
            # Loaded indicator
            rx.cond(
                ZdsState.schedule_loaded,
                rx.hstack(
                    rx.icon("circle-check", size=12, color="#059669"),
                    rx.text("Schedule loaded — TM Picker shows scheduled TMs first",
                            size="1", color="#059669"),
                    gap="4px", align="center",
                ),
                rx.hstack(
                    rx.icon("info", size=12, color="#9ca3af"),
                    rx.text("Upload a schedule Excel to enable schedule-aware TM Picker",
                            size="1", color="#9ca3af"),
                    gap="4px", align="center",
                ),
            ),
            gap="10px", width="100%",
        ),
        background="white",
        border="1px solid #e5e7eb",
        border_radius="10px",
        padding="16px",
        width="100%",
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
        background="#f9fafb",
        min_height="100vh",
        # Page-load is wired in apps/zds/routes.py (on_load=[ZdsState.load_weeks]).
        # Don't add a duplicate on_mount here or Supabase gets hit twice.
    )
