"""
Complaint intelligence — adapted from the user's complain2.ipynb so it takes
RAW review text directly (no pre-tokenized column needed).

Pipeline for an uploaded reviews file:
  1. Auto-detect the text / rating / date columns (reuses positioning.py's
     detectors — same conventions everywhere).
  2. Mark complaints: rating <= 3 when a rating exists, else negative
     lexicon sentiment (same compact lexicon as positioning — no external
     ML dependency, deterministic, fast).
  3. Theme-tag each complaint with a keyword lexicon (Slow Service, Rude
     Staff, Food Quality, Hygiene, ... — the notebook's theme set).
  4. Outputs, in the order the product shows them:
       actions   — prescriptive DO-THIS playbook per top theme (shown FIRST)
       trend     — monthly counts + complaint rate with 3-month rolling avg
                   (the notebook's rolling-average trend engine)
       quadrant  — frequency share x business severity, with growth
                   (the notebook's severity map -> Fix First / Contain Risk /
                    Streamline Ops / Monitor)
       deep      — per-theme stats table (count, share, avg rating, trend, example)
"""
import re
import warnings
from collections import Counter

import pandas as pd


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse messy date columns (incl. Google's tz-aware ISO timestamps)
    without pandas warnings: parse as UTC, then drop the timezone."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(series, errors="coerce", utc=True)
    try:
        return parsed.dt.tz_localize(None)
    except (TypeError, AttributeError):
        return parsed

from backend.core.positioning import (detect_rating_column, detect_review_column,
                                      sentiment_score)
from backend.core import product_config

# Complaint theme keywords are now product-type aware (see product_config).
# Severity and the fix-first playbook are type-independent, so we alias them
# straight through.
SEVERITY = product_config.COMPLAINT_SEVERITY
PLAYBOOK = product_config.COMPLAINT_PLAYBOOK


def _clean(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _detect_date_column(df: pd.DataFrame) -> str | None:
    hints = ("date", "time", "publishedat", "publishat", "created", "posted")
    for col in df.columns:
        if any(h in re.sub(r"[^a-z]", "", str(col).lower()) for h in hints):
            if _parse_dates(df[col]).notna().mean() > 0.6:
                return str(col)
    for col in df.columns:  # fallback: any column that parses as dates
        if df[col].dtype == object:
            if _parse_dates(df[col]).notna().mean() > 0.8:
                return str(col)
    return None


_NEG_CUES = ("but ", "however", "though", "not good", "not great", "could be better",
             "needs improvement", "worst", "bad ", "poor ", "disappoint", "never again",
             "wont come", "won t come", "avoid", "pathetic", "terrible", "horrible")


def _has_negative_cue(clean_sentence: str) -> bool:
    return any(c in clean_sentence for c in _NEG_CUES)


def _tag_themes(clean_text: str, lexicon: dict[str, list[str]]) -> list[str]:
    return [theme for theme, kws in lexicon.items() if any(k in clean_text for k in kws)]


def analyze_complaints(df: pd.DataFrame, product_type: str | None = None) -> dict:
    lexicon = product_config.complaint_lexicon(product_type)
    text_col = detect_review_column(df)
    if not text_col:
        raise ValueError("Could not find a review text column — the file needs a column of review text.")
    rating_col = detect_rating_column(df)
    date_col = _detect_date_column(df)

    work = df[df[text_col].notna()].copy()
    work["_clean"] = work[text_col].astype(str).map(_clean)
    work["_sent"] = work["_clean"].map(sentiment_score)
    if rating_col:
        work["_rating"] = pd.to_numeric(work[rating_col], errors="coerce")
        work["_is_complaint"] = (work["_rating"] <= 3) | (work["_sent"] <= -0.05)
    else:
        work["_rating"] = None
        work["_is_complaint"] = work["_sent"] <= -0.05
    if date_col:
        work["_date"] = _parse_dates(work[date_col])
    else:
        work["_date"] = pd.NaT

    complaints = work[work["_is_complaint"]].copy()
    n_reviews = int(len(work))

    # explode into (review, theme) rows; untagged complaints -> "Other"
    rows = []
    for _, r in complaints.iterrows():
        themes = _tag_themes(r["_clean"], lexicon) or ["Other"]
        for t in themes:
            rows.append({"theme": t, "date": r["_date"], "rating": r["_rating"],
                         "sent": r["_sent"], "text": str(r[text_col])})

    # MIXED reviews: a 5-star "food was amazing but we waited 45 minutes"
    # is positive overall yet contains a real complaint. Scan the sentences
    # of non-complaint reviews; any negative sentence that names a theme
    # counts as a complaint mention — this is where most missed complaints
    # were hiding.
    mixed_ids = set()
    positives = work[~work["_is_complaint"]]
    for idx, r in positives.iterrows():
        for sentence in re.split(r"[.!?\n;]+", str(r[text_col])):
            sc = _clean(sentence)
            if len(sc) < 4:
                continue
            themes = _tag_themes(sc, lexicon)
            if not themes:
                continue
            if sentiment_score(sc) <= -0.05 or _has_negative_cue(sc):
                for t in themes:
                    rows.append({"theme": t, "date": r["_date"], "rating": r["_rating"],
                                 "sent": sentiment_score(sc), "text": sentence.strip()})
                mixed_ids.add(idx)
    n_complaints = int(len(complaints)) + len(mixed_ids)
    tagged = pd.DataFrame(rows)

    detected = {"text_col": text_col, "rating_col": rating_col, "date_col": date_col,
                "n_reviews": n_reviews, "n_complaints": n_complaints,
                "complaint_rate": round(n_complaints / n_reviews * 100, 1) if n_reviews else 0.0}
    if tagged.empty:
        return {"detected": detected, "actions": [], "trend": None, "quadrant": None, "deep": []}

    # ---------- per-theme deep stats ----------
    total = len(tagged)
    deep = []
    for theme, grp in tagged.groupby("theme"):
        count = int(len(grp))
        # growth: last third of the date range vs previous third (needs dates)
        growth = None
        dates = grp["date"].dropna()
        all_dates = tagged["date"].dropna()
        if len(all_dates) >= 6:
            span = all_dates.max() - all_dates.min()
            if span.days >= 30:
                t1 = all_dates.max() - span / 3
                t0 = all_dates.max() - 2 * span / 3
                recent, prev = (dates >= t1).sum(), ((dates >= t0) & (dates < t1)).sum()
                growth = round((recent - prev) / max(prev, 1) * 100)
        sev_label, sev_num = SEVERITY.get(theme, SEVERITY["Other"])
        avg_rating = grp["rating"].dropna()
        # short excerpt from the most negative example (first 120 chars)
        example = grp.sort_values("sent").iloc[0]["text"][:120]
        deep.append({
            "theme": theme, "count": count, "share_pct": round(count / total * 100, 1),
            "severity": sev_label, "severity_num": sev_num,
            "avg_rating": round(float(avg_rating.mean()), 2) if len(avg_rating) else None,
            "growth_pct": growth, "example": example,
        })

    # IGNORE the long tail: a theme with only 1-3 complaints is noise, not a
    # pattern. Keep it out of the charts, the framework, and the actions so the
    # owner isn't sent chasing one-off gripes. We remember how many themes and
    # complaints we set aside, and surface that honestly.
    MIN_COUNT = 4
    kept = [d for d in deep if d["count"] >= MIN_COUNT]
    ignored = [d for d in deep if d["count"] < MIN_COUNT]
    ignored_summary = {
        "themes": len(ignored),
        "complaints": int(sum(d["count"] for d in ignored)),
        "examples": [d["theme"] for d in sorted(ignored, key=lambda x: -x["count"])[:4]],
    }
    deep = kept
    deep.sort(key=lambda d: (d["severity_num"], d["count"]), reverse=True)
    if not deep:  # everything was long-tail noise
        return {"detected": detected, "actions": [], "trend": None, "quadrant": None,
                "deep": [], "focus": None, "monthly": None, "ignored": ignored_summary}

    # ---------- monthly complaint volume (headline number owners asked for) ----------
    monthly = None
    dated_all = tagged[tagged["theme"].isin([d["theme"] for d in deep])].dropna(subset=["date"])
    if len(dated_all) >= 3:
        by_month = (dated_all.assign(m=dated_all["date"].dt.to_period("M"))
                    .groupby("m").size().sort_index())
        rev_by_month = (work.dropna(subset=["_date"])
                        .assign(m=lambda x: x["_date"].dt.to_period("M"))
                        .groupby("m").size())
        months = [str(m) for m in by_month.index]
        counts = [int(c) for c in by_month.values]
        rates = [round(int(by_month[m]) / max(int(rev_by_month.get(m, 0)), 1) * 100, 1)
                 for m in by_month.index]
        avg_per_month = round(sum(counts) / len(counts), 1)
        # recent vs earlier half — are complaints rising month over month?
        half = len(counts) // 2 or 1
        recent_avg = sum(counts[-half:]) / half
        earlier_avg = sum(counts[:half]) / half if counts[:half] else recent_avg
        mom_change = round((recent_avg - earlier_avg) / max(earlier_avg, 1) * 100)
        monthly = {"months": months, "counts": counts, "rates": rates,
                   "avg_per_month": avg_per_month, "mom_change_pct": mom_change,
                   "latest_count": counts[-1], "latest_month": months[-1]}

    # ---------- quadrant (frequency share x severity, growth as signal) ----------
    share_median = pd.Series([d["share_pct"] for d in deep]).median()
    points = []
    for d in deep:
        hi_freq = d["share_pct"] >= share_median
        hi_sev = d["severity_num"] >= 3
        quad = ("Fix First" if hi_freq and hi_sev else
                "Contain Risk" if hi_sev else
                "Streamline Ops" if hi_freq else "Monitor")
        points.append({**{k: d[k] for k in ("theme", "share_pct", "severity_num",
                                            "severity", "count", "growth_pct")},
                       "quadrant": quad})
    quadrant = {"points": points, "share_median": round(float(share_median), 1),
                "severity_line": 2.5}

    # ---------- FOCUS FRAMEWORK: where to actually concentrate ----------
    # Every theme gets a single Focus Score so the owner fixes the few things
    # that move the needle instead of spreading thin. Score blends:
    #   Volume   — how many customers hit it (share of all complaints)
    #   Severity — how much damage each one does (1-4 business impact)
    #   Momentum — is it getting worse? (recent growth)
    # Score = share% x severity x momentum-multiplier. The top items become
    # "Focus Now"; a rising critical issue jumps the queue even at lower volume.
    focus_items = []
    for d in deep:
        g = d["growth_pct"]
        momentum = 1.6 if (g is not None and g > 25) else (0.7 if (g is not None and g < -25) else 1.0)
        score = round(d["share_pct"] * d["severity_num"] * momentum, 1)
        focus_items.append({**d, "focus_score": score, "momentum": momentum})
    focus_items.sort(key=lambda x: -x["focus_score"])

    # verdict bands: the top 1-2 (that clear a real threshold) are the focus;
    # the rest are watch/ignore so effort isn't scattered
    top_score = focus_items[0]["focus_score"] if focus_items else 0
    focus_now, watch = [], []
    for i, f in enumerate(focus_items):
        is_focus = (i < 2 and f["focus_score"] >= max(15, top_score * 0.5))
        (focus_now if is_focus else watch).append(f)
    if not focus_now and focus_items:      # always give at least one thing to do
        focus_now = [focus_items[0]]
        watch = focus_items[1:]

    focus = {
        "headline": focus_now[0]["theme"] if focus_now else None,
        "focus_now": [{"theme": f["theme"], "count": f["count"], "share_pct": f["share_pct"],
                       "severity": f["severity"], "focus_score": f["focus_score"],
                       "growth_pct": f["growth_pct"],
                       "action": PLAYBOOK.get(f["theme"], PLAYBOOK["Other"])}
                      for f in focus_now],
        "watch": [{"theme": f["theme"], "count": f["count"], "share_pct": f["share_pct"],
                   "severity": f["severity"], "focus_score": f["focus_score"]}
                  for f in watch[:4]],
        "principle": ("Fix the 1-2 issues below first. They cause the most damage to the most "
                      "customers right now — everything else can wait until these move."),
    }

    # ---------- monthly trend with 3-month rolling average (notebook engine) ----------
    trend = None
    dated = tagged.dropna(subset=["date"])
    dated = dated[dated["theme"].isin([d["theme"] for d in deep])]
    if len(dated) >= 3 and work["_date"].notna().sum() >= 3:
        dated = dated.assign(month=dated["date"].dt.to_period("M").dt.to_timestamp())
        month_reviews = (work.dropna(subset=["_date"])
                         .assign(month=lambda x: x["_date"].dt.to_period("M").dt.to_timestamp())
                         .groupby("month").size())
        months_t = sorted(month_reviews.index)
        top_themes = [d["theme"] for d in deep[:6]]
        series = []
        for theme in top_themes:
            counts_t = dated[dated["theme"] == theme].groupby("month").size().reindex(months_t, fill_value=0)
            rate = (counts_t / month_reviews.reindex(months_t).clip(lower=1) * 100)
            series.append({
                "name": theme,
                "counts": counts_t.astype(int).tolist(),
                "rolling_rate": rate.rolling(3, min_periods=1).mean().round(2).tolist(),
            })
        trend = {"months": [m.strftime("%Y-%m") for m in months_t], "series": series}

    # ---------- prescriptive actions (the focus items, most actionable first) ----------
    actions = []
    for d in focus_items[:5]:
        rising = d["growth_pct"] is not None and d["growth_pct"] > 20
        why = f"{d['count']} complaints ({d['share_pct']}% of all)" \
              + (f", up {d['growth_pct']}% recently" if rising else "")
        target = max(1, d["count"] // 2)
        actions.append({
            "theme": d["theme"], "severity": d["severity"],
            "text": PLAYBOOK.get(d["theme"], PLAYBOOK["Other"])
                    + f" Target: cut {d['theme']} complaints from {d['count']} to under {target} in 60 days.",
            "why": why, "rising": bool(rising),
        })

    return {"detected": detected, "actions": actions, "trend": trend,
            "quadrant": quadrant, "deep": deep, "focus": focus,
            "monthly": monthly, "ignored": ignored_summary}
