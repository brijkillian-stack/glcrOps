"""GLCR Memory route definitions."""

from shared.components.homepage import home_page

from .pages.today import today_page
from .pages.search import search_page
from .pages.tasks import tasks_page
from .pages.people import people_page
from .pages.recap import recap_page
from .pages.logs import logs_page
from .pages.floor import floor_page
from .pages.areas import areas_page
from .pages.deployment import deployment_page
from .pages.patterns import patterns_page
from .pages.login import login_page
from .pages.auth_callback import auth_callback_page
from .pages.health import health_page
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
PUBLIC_ROUTES = ["/login", "/auth/callback"]

# Route table: (page_fn, route_path, title, on_load_list)
ROUTES = [
    # Public routes
    (login_page, "/login", "Sign in · GLCR Memory", []),
    (auth_callback_page, "/auth/callback", "Signing in...", []),

    # Protected routes (mapped to /glcr/* prefix for unified app)
    # / is now the three-card launchpad; Today moves to /today.
    (home_page, "/", "Graves Ops", []),
    (today_page, "/today", "Today · GLCR Memory", [TodayState.load_today, TodayState.start_live_updates]),
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
