"""
test_annotations.py — Round-trip smoke test for zds_annotations (Phase 4k.2)

Uses a far-future test week (2099-12-31) that will never collide with real data.
Cleans up after itself — safe to run repeatedly.

Run from repo root:
    python -m apps.zds.engine.test_annotations
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from datetime import date

from shared.db import (
    upsert_annotation,
    list_annotations,
    list_annotations_grouped,
    get_annotation,
    delete_annotation,
)

WEEK = date(2099, 12, 31)   # safe far-future test week


def main() -> None:
    print("Phase 4k.2 annotation smoke test …")

    # ── Write ────────────────────────────────────────────────────────────────
    upsert_annotation(WEEK, "fri", "task", "test-task-id", "highlight", {"color": "yellow"})
    upsert_annotation(WEEK, "fri", "task", "test-task-id", "note",      {"text": "smoke test note"})
    upsert_annotation(WEEK, "fri", "tm",   "tm_test",      "note",      {"text": "tm note"})
    print("  Write: 3 annotations inserted")

    # ── list_annotations ─────────────────────────────────────────────────────
    rows = list_annotations(WEEK, "fri")
    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
    print(f"  list_annotations: {len(rows)} rows ✓")

    # ── list_annotations_grouped ──────────────────────────────────────────────
    grouped = list_annotations_grouped(WEEK, "fri")
    assert grouped["task"]["test-task-id"]["highlight"]["color"] == "yellow", \
        f"highlight color wrong: {grouped}"
    assert grouped["task"]["test-task-id"]["note"]["text"] == "smoke test note", \
        f"task note wrong: {grouped}"
    assert grouped["tm"]["tm_test"]["note"]["text"] == "tm note", \
        f"tm note wrong: {grouped}"
    print("  list_annotations_grouped: shape + values ✓")

    # ── Filtered list_annotations ─────────────────────────────────────────────
    task_rows = list_annotations(WEEK, "fri", target_kind="task")
    assert len(task_rows) == 2, f"Expected 2 task rows, got {len(task_rows)}"
    ref_rows = list_annotations(WEEK, "fri", target_ref="tm_test")
    assert len(ref_rows) == 1, f"Expected 1 ref row, got {len(ref_rows)}"
    print("  Filtered list_annotations: target_kind + target_ref filters ✓")

    # ── Upsert (update) ───────────────────────────────────────────────────────
    upsert_annotation(WEEK, "fri", "task", "test-task-id", "highlight", {"color": "red"})
    a = get_annotation(WEEK, "fri", "task", "test-task-id", "highlight")
    assert a is not None, "get_annotation returned None after upsert"
    assert a["value"]["color"] == "red", f"Expected red, got {a['value']}"
    print("  Upsert (update): color yellow→red ✓")

    # ── Delete ────────────────────────────────────────────────────────────────
    delete_annotation(WEEK, "fri", "task", "test-task-id", "highlight")
    assert get_annotation(WEEK, "fri", "task", "test-task-id", "highlight") is None, \
        "Row still present after delete"
    print("  delete_annotation + get_annotation None ✓")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    delete_annotation(WEEK, "fri", "task", "test-task-id", "note")
    delete_annotation(WEEK, "fri", "tm",   "tm_test",      "note")
    remaining = list_annotations(WEEK, "fri")
    assert len(remaining) == 0, f"Cleanup incomplete, {len(remaining)} rows remain"
    print("  Cleanup: 0 rows remain ✓")

    print("\nOK — annotations round-trip clean")


if __name__ == "__main__":
    main()
