"""Centralized settings for the ZDS Forge API.

Reads from environment variables (typically populated by the root
`.env` via python-dotenv elsewhere in the stack). Keeping this in one
place means routers and services can depend on `Settings` rather than
sprinkling `os.getenv` calls everywhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


@dataclass(frozen=True)
class Settings:
    # ── Supabase ─────────────────────────────────────────────────────
    supabase_url: str
    supabase_service_key: str

    # ── Redis (optional — service degrades gracefully if unset) ─────
    redis_url: Optional[str]

    # ── Misc ────────────────────────────────────────────────────────
    env: str  # "dev" | "prod" | etc.
    debug: bool


def _bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings.

    Cached so every request reuses the same dataclass instance — pair
    with `get_settings.cache_clear()` in tests if you need to swap envs.
    """
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
        redis_url=os.getenv("REDIS_URL") or None,
        env=os.getenv("APP_ENV", "dev"),
        debug=_bool(os.getenv("APP_DEBUG"), default=False),
    )
