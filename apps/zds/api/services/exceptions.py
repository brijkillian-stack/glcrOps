"""Domain exceptions for the ZDS Forge API.

Route handlers catch these and translate them to the appropriate HTTP
status codes and structured error envelopes. Services raise them; the
HTTP layer translates them — services never know about HTTP.
"""

from __future__ import annotations


class WeekNotFoundError(Exception):
    """Raised when a week_id doesn't resolve to a known week row."""

    def __init__(self, week_id: str):
        super().__init__(f"Week not found: {week_id!r}")
        self.week_id = week_id


class NightNotFoundError(Exception):
    """Raised when a night_id doesn't resolve to a known night row."""

    def __init__(self, night_id: str):
        super().__init__(f"Night not found: {night_id!r}")
        self.night_id = night_id


class RenderError(Exception):
    """Raised when the renderer function call fails.

    Wraps the underlying exception in ``.__cause__`` so the original
    traceback is preserved.  Router logs the full trace and surfaces
    a structured error envelope to the client.
    """

    def __init__(self, message: str):
        super().__init__(message)
