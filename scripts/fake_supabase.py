"""
A stand-in for the Supabase client that behaves like production where it
matters for this app: tables have FIXED COLUMNS (read from supabase/schema.sql)
and a row with any other key is refused, and JSON has no NaN/Infinity — both
exactly as PostgREST/Postgres refuse them. The app's JSON-file mode accepts
anything, which is how a PO write that failed on every live account passed
every local test.

Tables not in schema.sql (created elsewhere, e.g. `sites`, `media`) accept
any columns.

Use:  from scripts.fake_supabase import install; install()   # before requests
"""
from __future__ import annotations

import json
import os
import re
import threading
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def schema_columns() -> dict[str, set[str]]:
    sql = open(os.path.join(ROOT, "supabase", "schema.sql"), encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"create table if not exists public\.(\w+)\s*\((.*?)\n\);", sql, re.S):
        cols = set()
        for line in m.group(2).splitlines():
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            w = re.match(r"([a-z_][a-z0-9_]*)\s+[a-z]", line)
            if w and w.group(1) not in ("primary", "unique", "constraint", "foreign", "check"):
                cols.add(w.group(1))
        out[m.group(1)] = cols
    return out


class APIError(Exception):
    pass


class _Q:
    def __init__(self, db, table):
        self.db, self.table, self.op, self.payload = db, table, "select", None
        self.filters, self._limit, self._count, self.on_conflict = [], None, None, None

    # builders
    def select(self, *_a, count=None, **_k):
        self.op, self._count = "select", count
        return self

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def upsert(self, row, on_conflict=None, **_k):
        self.op, self.payload, self.on_conflict = "upsert", row, on_conflict
        return self

    def update(self, patch):
        self.op, self.payload = "update", patch
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, k, v):
        self.filters.append(("eq", k, v))
        return self

    def gte(self, k, v):
        self.filters.append(("gte", k, v))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    # checks that production makes
    def _check(self, row):
        cols = self.db.cols.get(self.table)
        if cols is not None:
            bad = sorted(k for k in row if k not in cols)
            if bad:
                raise APIError({"code": "PGRST204", "message":
                                f"Could not find the '{bad[0]}' column of '{self.table}' in the schema cache"})
        try:
            json.dumps(row, allow_nan=False, default=str)
        except ValueError as e:
            raise APIError({"code": "22P02", "message": f"invalid input syntax for type json: {e}"})

    def _match(self, r):
        for op, k, v in self.filters:
            if op == "eq" and str(r.get(k)) != str(v):
                return False
            if op == "gte" and str(r.get(k, "")) < str(v):
                return False
        return True

    def execute(self):
        with self.db.lock:
            rows = self.db.tables.setdefault(self.table, [])
            if self.op == "select":
                got = [dict(r) for r in rows if self._match(r)]
                if self._limit:
                    got = got[: self._limit]
                return SimpleNamespace(data=json.loads(json.dumps(got, default=str)), count=len(got))
            if self.op in ("insert", "upsert"):
                payload = self.payload if isinstance(self.payload, list) else [self.payload]
                for row in payload:
                    self._check(row)
                    row = json.loads(json.dumps(row, default=str))
                    key = self.on_conflict or "id"
                    hit = next((r for r in rows if key in row and r.get(key) == row.get(key)), None)
                    if hit is not None and self.op == "upsert":
                        hit.update(row)
                    elif hit is not None:
                        raise APIError({"code": "23505", "message": "duplicate key"})
                    else:
                        rows.append(row)
                return SimpleNamespace(data=payload, count=len(payload))
            if self.op == "update":
                self._check(self.payload)
                n = 0
                for r in rows:
                    if self._match(r):
                        r.update(json.loads(json.dumps(self.payload, default=str)))
                        n += 1
                return SimpleNamespace(data=[], count=n)
            if self.op == "delete":
                keep = [r for r in rows if not self._match(r)]
                n = len(rows) - len(keep)
                self.db.tables[self.table] = keep
                return SimpleNamespace(data=[], count=n)
        raise APIError("unknown op")


class _Bucket:
    def __init__(self, store):
        self.store = store

    def upload(self, path=None, file=None, file_options=None, *a):
        self.store[path] = bytes(file)
        return {"Key": path}

    update = upload

    def download(self, path):
        if path not in self.store:
            raise APIError("not found")
        return self.store[path]

    def remove(self, paths):
        for p in paths:
            self.store.pop(p, None)


class FakeClient:
    def __init__(self):
        self.cols = schema_columns()
        self.tables: dict[str, list[dict]] = {}
        self.blobs: dict[str, bytes] = {}
        self.lock = threading.RLock()
        self.storage = SimpleNamespace(
            from_=lambda _b: _Bucket(self.blobs),
            list_buckets=lambda: [SimpleNamespace(name=os.environ.get("SUPABASE_BUCKET", "user-datasets"))],
            create_bucket=lambda *a, **k: None)

    def table(self, name):
        return _Q(self, name)


def install() -> FakeClient:
    from backend.core import db
    fake = FakeClient()
    db.SUPABASE_ENABLED = True
    db.client = lambda: fake
    db._reset_client = lambda: None
    return fake
