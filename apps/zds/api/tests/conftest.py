"""Shared fixtures + a fake Supabase client used by the shift tests.

The fake mimics just the slice of the supabase-py builder chain our
services actually call:

    sb.table(name).select(...).eq(...).limit(...).order(...).in_(...).execute()

`execute()` returns a small object with a `.data` attribute. Mutating
calls (`update`, `insert`, `delete`) are recorded so tests can assert
on the resulting SQL-shaped intent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pytest


@dataclass
class _Result:
    data: list[dict] = field(default_factory=list)


class _QueryBuilder:
    def __init__(self, fetch: Callable[[dict], list[dict]], table: str,
                 mutator: Callable[[str, dict, dict], list[dict]] | None = None):
        self._fetch = fetch
        self._mutator = mutator
        self._table = table
        self._filters: dict[str, Any] = {}
        self._mode = "select"
        self._payload: dict[str, Any] = {}

    def select(self, *_args, **_kwargs):
        self._mode = "select"
        return self

    def update(self, payload: dict):
        self._mode = "update"
        self._payload = dict(payload)
        return self

    def insert(self, payload: dict | list[dict]):
        self._mode = "insert"
        self._payload = payload if isinstance(payload, list) else [dict(payload)]
        return self

    def delete(self):
        self._mode = "delete"
        return self

    def eq(self, key: str, value: Any):
        self._filters[key] = value
        return self

    def in_(self, key: str, values: list[Any]):
        self._filters[f"in:{key}"] = list(values)
        return self

    def limit(self, _n: int):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._mode == "select":
            return _Result(data=self._fetch({"table": self._table, **self._filters}))
        if self._mode in {"update", "insert", "delete"}:
            assert self._mutator is not None, "fake client got a write call but no mutator"
            return _Result(data=self._mutator(self._mode, {"table": self._table,
                                                           "payload": self._payload,
                                                           **self._filters}, {}))
        return _Result(data=[])


class FakeSupabase:
    """Minimal fake of the supabase-py client.

    Build one via `FakeSupabase.with_tables({...})` for read-only tests,
    or pass `mutator=...` to capture writes.
    """

    def __init__(self, tables: dict[str, list[dict]],
                 mutator: Callable[[str, dict, dict], list[dict]] | None = None):
        self._tables = tables
        self._mutator = mutator

    @classmethod
    def with_tables(cls, tables: dict[str, list[dict]]) -> "FakeSupabase":
        return cls(tables=tables)

    def table(self, name: str) -> _QueryBuilder:
        return _QueryBuilder(
            fetch=lambda ctx: self._select(ctx),
            table=name,
            mutator=self._mutator,
        )

    # ── Internal: row filtering for select() ─────────────────────────

    def _select(self, ctx: dict) -> list[dict]:
        rows = list(self._tables.get(ctx["table"], []))
        for key, val in ctx.items():
            if key == "table":
                continue
            if key.startswith("in:"):
                col = key[3:]
                rows = [r for r in rows if r.get(col) in set(val)]
            else:
                rows = self._apply_eq(rows, key, val)
        # Inflate entity joins inline: zone_assignments + overlap_assignments
        # select a joined "entities(id, display_name)" payload — production
        # supabase resolves this server-side; we shim it here so the service
        # under test sees the same shape it sees in prod.
        if ctx["table"] in {"zone_assignments", "overlap_assignments"}:
            entities = {e.get("id"): e for e in self._tables.get("entities", [])}
            inflated = []
            for r in rows:
                r = dict(r)
                ent = entities.get(r.get("tm_id"))
                r["entities"] = {"id": ent["id"], "display_name": ent["display_name"]} if ent else None
                inflated.append(r)
            rows = inflated
        # nights join for fatigue read
        if ctx["table"] == "zone_assignments":
            nights = {n["id"]: n for n in self._tables.get("nights", [])}
            for r in rows:
                if "night_id" in r:
                    n = nights.get(r.get("night_id"))
                    if n:
                        r["nights"] = {"night_date": n["night_date"]}
        return rows

    @staticmethod
    def _apply_eq(rows: list[dict], key: str, val: Any) -> list[dict]:
        return [r for r in rows if r.get(key) == val]


@pytest.fixture
def fake_supabase_factory():
    """Return a builder so each test can shape its own DB snapshot."""
    return FakeSupabase.with_tables
