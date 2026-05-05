"""
storage.py — Supabase Storage helpers for the unified app.

Originally used by ZDS to persist uploaded weekly schedule xlsx files in a
private bucket so the Render container can run fill_engine.py against them
across deploys / restarts (the local Inputs/ folder is ephemeral). Now also
serves the Phase K iPad/Pencil features (signed-URL retrieval, annotation
upload).

Buckets:
    schedules      — weekly ADP exports (private, 25 MB)
    casino-assets  — floor map, brand assets, reference imagery (private, 25 MB)
    annotations    — user-generated Pencil drawings (private, 10 MB)
    hr-docs        — HR documents (private, 50 MB)

All buckets are private; we authenticate with the service-role key and
files are served via signed URLs at render time.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from shared.db import get_client

log = logging.getLogger(__name__)

SCHEDULES_BUCKET = "schedules"
CASINO_ASSETS_BUCKET = "casino-assets"
ANNOTATIONS_BUCKET = "annotations"
HR_DOCS_BUCKET = "hr-docs"

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PNG_MIME = "image/png"


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


def delete_schedule(filename: str) -> bool:
    """Remove an xlsx from the schedules bucket. Idempotent — silently
    succeeds if the file is already gone."""
    if not filename:
        return False
    sb = get_client()
    try:
        sb.storage.from_(SCHEDULES_BUCKET).remove([filename])
        return True
    except Exception as exc:
        log.exception("Failed to delete schedule %s: %s", filename, exc)
        return False


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


# =============================================================================
# Phase K — signed URLs + annotation upload helpers
# =============================================================================


def get_signed_url(
    bucket: str,
    path: str,
    *,
    ttl_seconds: int = 3600,
    download: bool = False,
) -> str:
    """Generate a signed URL for a private-bucket object.

    Used to render images stored in casino-assets, annotations, hr-docs
    without making the buckets public. URLs expire — defaults to 1 hour,
    which is plenty for a single page render. For long-lived embeds
    (e.g. a deployment book HTML that's archived to disk), pass a longer
    ttl_seconds — but those should usually fetch a fresh URL on view
    instead of relying on a stale embedded one.

    Returns the signed URL string. Raises if the object doesn't exist.
    """
    sb = get_client()
    res = sb.storage.from_(bucket).create_signed_url(
        path=path, expires_in=ttl_seconds
    )
    # supabase-py returns {"signedURL": "..."} or {"signed_url": "..."} depending on version
    return res.get("signedURL") or res.get("signed_url") or res.get("signedUrl") or ""


def get_floor_map_url(*, ttl_seconds: int = 3600) -> str:
    """Convenience wrapper — current canonical floor map for canvas rendering."""
    return get_signed_url(
        CASINO_ASSETS_BUCKET,
        "floor-maps/glcr_floor_map_dec_2025_no_logos.png",
        ttl_seconds=ttl_seconds,
    )


def upload_annotation(
    *,
    image_data: bytes,
    kind: str,
    target_type: str,
    target_id: Optional[str] = None,
    author: Optional[str] = None,
    pen_settings: Optional[dict[str, Any]] = None,
    text_value: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    notes: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    expires_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Upload a Pencil annotation PNG and create the metadata row in one call.

    This is the single entry point for the K.1 PencilCanvas component's save
    flow. The frontend ships PNG bytes; this function:
      1. Uploads to the annotations bucket at:
            annotations/{kind}/{date}/{uuid}.png
      2. Inserts the matching public.annotations row pointing at that path.
      3. Returns the inserted row (with id) so the UI can confirm.

    `kind` must be one of: floor_map, deployment_book, signature, tm_comment, scratch.
    `target_type` must be one of: night, event, tm_profile, hr_document, note, generic.
    """
    sb = get_client()

    if kind not in {"floor_map", "deployment_book", "signature", "tm_comment", "scratch"}:
        raise ValueError(f"invalid annotation kind: {kind!r}")
    if target_type not in {"night", "event", "tm_profile", "hr_document", "note", "generic"}:
        raise ValueError(f"invalid target_type: {target_type!r}")

    today = date.today().isoformat()
    obj_id = uuid.uuid4().hex
    storage_path = f"{kind}/{today}/{obj_id}.png"

    # 1. Upload to Storage
    sb.storage.from_(ANNOTATIONS_BUCKET).upload(
        path=storage_path,
        file=image_data,
        file_options={"content-type": _PNG_MIME, "upsert": "false"},
    )

    # 2. Insert metadata row
    row = {
        "kind": kind,
        "target_type": target_type,
        "target_id": target_id,
        "image_path": storage_path,
        "width": width,
        "height": height,
        "author": author,
        "pen_settings": pen_settings or {},
        "text_value": text_value,
        "notes": notes,
        "metadata": metadata or {},
    }
    if expires_at is not None:
        row["expires_at"] = expires_at.astimezone(timezone.utc).isoformat()

    inserted = sb.table("annotations").insert(row).execute().data[0]
    inserted["signed_url"] = get_signed_url(ANNOTATIONS_BUCKET, storage_path)
    return inserted


def list_annotations(
    *,
    target_type: str,
    target_id: Optional[str] = None,
    kind: Optional[str] = None,
    include_expired: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List annotations attached to a given target. Each row is augmented with
    a fresh signed_url for immediate rendering."""
    sb = get_client()
    q = sb.table("annotations").select("*").eq("target_type", target_type)
    if target_id is not None:
        q = q.eq("target_id", target_id)
    if kind is not None:
        q = q.eq("kind", kind)
    if not include_expired:
        # Postgres OR via .or_() — annotations either have no expiry or expiry in future
        q = q.or_(
            "expires_at.is.null,expires_at.gt." + datetime.now(timezone.utc).isoformat()
        )
    rows = q.order("created_at", desc=True).limit(limit).execute().data or []
    for r in rows:
        try:
            r["signed_url"] = get_signed_url(ANNOTATIONS_BUCKET, r["image_path"])
        except Exception as exc:
            log.warning("failed to sign url for %s: %s", r.get("image_path"), exc)
            r["signed_url"] = None
    return rows


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
