"""
storage.py — Supabase Storage helpers for the unified app.

Currently used by ZDS to persist uploaded weekly schedule xlsx files in a
private bucket so the Render container can run fill_engine.py against them
across deploys / restarts (the local Inputs/ folder is ephemeral).

Bucket layout:
    schedules/
        IM Schedule 05-08-26.xlsx
        Weekly TM EOW 5-07.xlsx
        ...

The bucket is private; we authenticate with the service-role key and the
files are never directly served to browsers.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from shared.db import get_client

log = logging.getLogger(__name__)

SCHEDULES_BUCKET = "schedules"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def ensure_schedules_bucket() -> None:
    """Idempotently create the `schedules` bucket if it doesn't exist.

    Safe to call on every upload — Supabase's create_bucket throws if the
    bucket already exists, so we catch that and proceed.
    """
    sb = get_client()
    try:
        existing = sb.storage.list_buckets()
        names = {b.name if hasattr(b, "name") else b.get("name") for b in existing}
        if SCHEDULES_BUCKET in names:
            return
        sb.storage.create_bucket(
            SCHEDULES_BUCKET,
            options={"public": False, "file_size_limit": 25 * 1024 * 1024},
        )
        log.info("Created Supabase Storage bucket: %s", SCHEDULES_BUCKET)
    except Exception as exc:
        # If the bucket got created between list_buckets and create_bucket,
        # we'll see a "Bucket already exists" error — safe to swallow.
        msg = str(exc).lower()
        if "already exists" in msg or "duplicate" in msg:
            return
        log.exception("Failed to ensure schedules bucket: %s", exc)
        raise


def upload_schedule(filename: str, data: bytes) -> str:
    """Upload an xlsx into the schedules bucket. Overwrites if the same
    filename is already present (upsert)."""
    ensure_schedules_bucket()
    sb = get_client()
    sb.storage.from_(SCHEDULES_BUCKET).upload(
        path=filename,
        file=data,
        file_options={
            "content-type": _XLSX_MIME,
            "upsert": "true",
        },
    )
    return filename


def list_schedules() -> list[dict]:
    """Return all schedules in the bucket, newest first.

    Each entry has at minimum: name, updated_at (str), created_at, metadata.
    """
    ensure_schedules_bucket()
    sb = get_client()
    items = sb.storage.from_(SCHEDULES_BUCKET).list(
        path="",
        options={
            "limit": 200,
            "sortBy": {"column": "updated_at", "order": "desc"},
        },
    )
    # The SDK sometimes returns a "placeholder" entry .emptyFolderPlaceholder —
    # filter it out.
    return [it for it in (items or []) if it.get("name") and not it["name"].startswith(".")]


def download_latest_schedule(dest_dir: Path) -> Optional[Path]:
    """Download the most-recently-updated schedule from Storage into dest_dir.

    Returns the local Path of the saved file, or None if the bucket is empty.
    """
    schedules = list_schedules()
    if not schedules:
        return None

    latest = schedules[0]
    name = latest["name"]
    sb = get_client()
    blob: bytes = sb.storage.from_(SCHEDULES_BUCKET).download(name)

    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / name
    out.write_bytes(blob)
    return out


def sync_schedules_to(dest_dir: Path) -> int:
    """Mirror every schedule in the bucket into dest_dir.

    Useful when fill_engine.py auto-detects the most recent xlsx by mtime
    inside Inputs/Weekly Schedules/ — we want all of them present locally
    so the engine sees the same set of options it would on Brian's Mac.

    Returns the number of files synced.
    """
    schedules = list_schedules()
    if not schedules:
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    sb = get_client()
    for s in schedules:
        name = s["name"]
        target = dest_dir / name
        # Skip if local is at least as new as remote — avoids re-downloading
        # the same file every engine run.
        try:
            remote_ts = s.get("updated_at") or s.get("created_at") or ""
            if target.exists() and remote_ts:
                # Cheap heuristic: if local exists and remote_ts is unchanged
                # since last sync, skip. We don't track per-file timestamps
                # on disk, so re-download anyway — tiny files, fast.
                pass
        except Exception:
            pass
        try:
            blob: bytes = sb.storage.from_(SCHEDULES_BUCKET).download(name)
            target.write_bytes(blob)
        except Exception as exc:
            log.warning("Failed to sync %s: %s", name, exc)
    return len(schedules)
