"""GLCR Memory route definitions."""

from shared.components.homepage import home_page

# Phase 3 (GShiftPage): /today now renders the new Shift HUD instead of
# the legacy Memory dashboard. The old today_page + TodayState are kept
# in the codebase for /admin/today (legacy view) and any deep-link
# bookmarks that haven't been audited yet.
from apps.shift.pages.index import shift_page
from apps.shift.state import ShiftState
from .pages.today import today_page  # legacy — still used by /admin/today
from .pages.search import search_page
from .pages.tasks import tasks_page
from .pages.people import people_page
from .pages.recap import recap_page
from .pages.logs import logs_page
from .pages.floor import floor_page
from .pages.areas import areas_page
from .pages.deployment import deployment_page
from .pages.patterns import patterns_page
from .pages.unlock import unlock_page
from .pages.login import login_page
from .pages.auth_callback import auth_callback_page
from .pages.health import health_page
# Path C+ (2026-05-05): /unlock is the site-PIN gate (anyone). /login and
# /auth/callback are the magic-link elevation flow that promotes a known
# email to ZDS Editor or Editor based on EDITOR_EMAILS / ZDS_EDITOR_EMAILS.
from .pages.threads import threads_page
from .pages.writeups import writeups_page

from .state.today import TodayState
from .state.search import SearchState
from .state.tasks import TasksState
from .state.people import PeopleState
from .state.recap import ShiftRecapState
from .state.logs import LogsState
from .state.floor import FloorState
from .state.areas import AreasState
from .state.deployment import DeploymentState
from .state.patterns import PatternsState
from .state.health import HealthState
from .state.threads import ThreadsState
from .state.writeups import WriteupsState

# Public routes (no authentication required)
# Path C+: /unlock is the PIN gate (everyone). /login + /auth/callback are
# the magic-link elevation flow (editor tier). All three are public so a
# locked user can reach them; the gating happens via on_load handlers.
PUBLIC_ROUTES = ["/unlock", "/login", "/auth/callback"]

# Viewer-permitted routes (PIN unlock is sufficient; no editor required).
# Brian's call (2026-05-05): viewers see the homepage launchpad, the Today
# page, and ZDS (all ZDS routes). Everything else in GLCR Memory requires
# any editor role. Routes not in this set get the require_editor_any guard.
VIEWER_OK_ROUTES = {"/", "/today"}
# Note: ZDS routes are handled separately in brijkillian_stack.py — they're
# all viewer-OK by virtue of being a different app.

# Route table: (page_fn, route_path, title, on_load_list)
ROUTES = [
    # Public routes — no PIN required
    (unlock_page,        "/unlock",        "Unlock · Graves Ops",   []),
    (login_page,         "/login",         "Sign in as editor",     []),
    (auth_callback_page, "/auth/callback", "Signing in…",           []),

    # Protected routes — gated by AuthState.require_unlock (PIN site session)
    # / is the three-card launchpad; /today + /shift both render the new
    # Shift HUD (Phase 3). The legacy Memory dashboard moved to
    # /admin/today behind the Sudo Admin hub.
    (home_page,  "/",      "Graves Ops",                 []),
    (shift_page, "/today", "Today · GLCR",               [ShiftState.on_load]),
    (search_page, "/search", "Search · GLCR Memory", [SearchState.clear_search]),
    (logs_page, "/logs", "Logs · GLCR Memory", [LogsState.load_logs]),
    (people_page, "/people", "People · GLCR Memory", [PeopleState.load_people]),
    (threads_page, "/threads", "Threads · GLCR Memory", [ThreadsState.load_threads]),
    (tasks_page, "/tasks", "Tasks · GLCR Memory", [TasksState.load_tasks]),
    (patterns_page, "/patterns", "Patterns · GLCR Memory", [PatternsState.load_patterns]),
    (health_page, "/health", "Health · GLCR Memory", [HealthState.load_health]),
    (recap_page, "/recap", "Shift Recap · GLCR Memory", [ShiftRecapState.load_recap]),
    (floor_page, "/floor", "Floor Walk · GLCR Memory", [FloorState.init_walk]),
    (areas_page, "/areas", "Areas · GLCR Memory", [AreasState.load_areas]),
    (writeups_page, "/writeups", "Write-Ups · GLCR Memory", [WriteupsState.load_writeups]),
    (deployment_page, "/deployment", "Deployment · GLCR Memory", [DeploymentState.load_roster]),
]
