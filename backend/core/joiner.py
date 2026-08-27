"""
Auto-join — when someone uploads more than one file (e.g. an orders sheet +
an items sheet + a customers sheet), find the join keys automatically and
produce one combined table for mapping and insights.

How keys are detected (no user input needed):
  1. For every pair of tables and every pair of columns, compute the overlap
     of their normalized values (share of the smaller side's uniques found in
     the other side).
  2. A pair qualifies when overlap >= 50%, or >= 20% when the column NAMES
     also match (case/space-insensitive) — a matching name is strong evidence.
  3. The biggest table (most rows) is treated as the transactional base;
     the others are LEFT-joined onto it one by one via their best key, so
     no base rows are ever lost.
"""
import re

import pandas as pd

_MAX_SAMPLE = 5000  # cap uniques per column for overlap checks — keeps it fast


def _norm_name(col: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(col).lower())


def _norm_values(s: pd.Series) -> set:
    vals = s.dropna().astype(str).str.strip().str.lower()
    vals = vals[vals != ""].unique()[:_MAX_SAMPLE]
    return set(vals)


def _best_key(base: pd.DataFrame, other: pd.DataFrame) -> tuple[str, str, float] | None:
    """Best (base_col, other_col, overlap) join key between two tables, or None."""
    best = None
    other_vals = {c: _norm_values(other[c]) for c in other.columns}
    for bc in base.columns:
        bv = _norm_values(base[bc])
        if len(bv) < 2:
            continue
        for oc, ov in other_vals.items():
            if len(ov) < 2:
                continue
            overlap = len(bv & ov) / max(min(len(bv), len(ov)), 1)
            name_match = _norm_name(bc) == _norm_name(oc)
            if overlap >= 0.5 or (name_match and overlap >= 0.2):
                score = overlap + (0.25 if name_match else 0.0)
                if best is None or score > best[3]:
                    best = (str(bc), str(oc), overlap, score)
    return (best[0], best[1], best[2]) if best else None


def auto_join(dfs: dict[str, pd.DataFrame], names: dict[str, str]) -> tuple[pd.DataFrame, dict] | None:
    """Join 2+ tables into one on auto-detected keys.
    Returns (joined_df, report) or None when no confident key exists."""
    if len(dfs) < 2:
        return None
    # biggest table = transactional base; join dimensions onto it
    order = sorted(dfs, key=lambda k: len(dfs[k]), reverse=True)
    base_id, rest = order[0], order[1:]
    joined = dfs[base_id].copy()
    steps = []
    for fid in rest:
        other = dfs[fid]
        key = _best_key(joined, other)
        if not key:
            continue
        bc, oc, overlap = key
        right = other.copy()
        # normalized string key columns so "1001" joins with 1001
        joined["__jk"] = joined[bc].astype(str).str.strip().str.lower()
        right["__jk"] = right[oc].astype(str).str.strip().str.lower()
        if oc != bc and oc in joined.columns:
            right = right.rename(columns={oc: f"{oc}_2"})
        right = right.drop_duplicates("__jk")  # dimension table: one row per key
        joined = joined.merge(right, on="__jk", how="left", suffixes=("", "_2"))
        joined = joined.drop(columns="__jk")
        steps.append({"file": names.get(fid, fid), "base_key": bc, "other_key": oc,
                      "overlap_pct": round(overlap * 100)})
    if not steps:
        return None
    report = {"base_file": names.get(base_id, base_id), "joins": steps,
              "rows": int(len(joined)), "columns": int(len(joined.columns))}
    return joined, report
