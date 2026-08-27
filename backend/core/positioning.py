"""
Brand positioning for a small social-media product seller.

This used to compare a café against a fixed benchmark of peer cafés. That
peer-comparison has been removed — a small independent seller isn't trying to
out-score a fixed panel of shops; they want to understand THEIR OWN customers.
So everything here now reads only the seller's own reviews:

  1. Auto-detect the review-text column (and rating column if present)
  2. Theme-tag every review with the product-type keyword lexicon
     (core/product_config.py) — jewellery / clothes / perfumes each read in
     their own vocabulary
  3. Score sentiment per review with a compact lexicon (no external model,
     no API cost) and aggregate per theme
  4. Place the seller on a value<->premium x product<->brand 2x2, built from
     what their reviewers actually talk about
  5. Emit self-referential insights FIRST (each with a concrete action), then
     chart-ready data

The 2x2 quadrant it detects still feeds Position Strategy (see
position_strategy.QUADRANT_TO_ID), which is why the quadrant labels here and
the position ids there are kept in lock-step.
"""
import re

import pandas as pd

from backend.core import product_config

_POSITIVE_WORDS = {
    "good", "great", "amazing", "awesome", "excellent", "love", "loved", "lovely", "best",
    "beautiful", "gorgeous", "perfect", "wonderful", "fantastic", "stunning", "elegant",
    "friendly", "helpful", "polite", "quick", "fast", "worth", "value", "premium", "quality",
    "recommend", "recommended", "must", "favourite", "favorite", "nice", "happy", "satisfied",
    "authentic", "genuine", "durable", "comfortable", "soft", "classy", "superb", "brilliant",
    "affordable", "reasonable", "generous", "prompt", "trendy", "stylish", "flawless",
}
_NEGATIVE_WORDS = {
    "bad", "worst", "terrible", "horrible", "awful", "poor", "slow", "late", "rude", "cheap",
    "fake", "duplicate", "damaged", "broken", "defective", "faulty", "disappointed",
    "disappointing", "pathetic", "mediocre", "waited", "waiting", "delay", "delayed", "wrong",
    "missing", "avoid", "never", "overpriced", "expensive", "flimsy", "tarnished", "faded",
    "torn", "small", "tight", "loose", "useless", "waste", "misleading", "regret",
}
_NEGATORS = {"not", "no", "never", "hardly", "barely", "isnt", "isn't", "wasnt", "wasn't", "dont", "don't", "didnt", "didn't"}


def _is_texty(series: pd.Series) -> bool:
    """True for string-ish columns (not numeric/datetime/bool)."""
    return not (
        pd.api.types.is_numeric_dtype(series)
        or pd.api.types.is_datetime64_any_dtype(series)
        or pd.api.types.is_bool_dtype(series)
    )


def detect_review_column(df: pd.DataFrame) -> str | None:
    """Pick the review-text column. Priority names first (Google/Apify exports
    use 'text' / 'textTranslated'), then name hints — EXCLUDING lookalikes
    like 'responseFromOwnerText' (seller replies) and metadata columns."""
    norm = {re.sub(r"[^a-z]", "", str(c).lower()): str(c) for c in df.columns}
    for want in ("text", "texttranslated", "review", "reviewtext", "comment", "feedback", "body", "content"):
        col = norm.get(want)
        if col is not None and _is_texty(df[col]):
            return col
    bad = ("owner", "response", "context", "url", "id", "count", "distribution", "reviewer", "image")
    name_hints = ("review", "text", "comment", "feedback", "description", "body", "content")
    for col in df.columns:
        low = str(col).lower()
        if any(h in low for h in name_hints) and not any(b in low for b in bad) and _is_texty(df[col]):
            return str(col)
    text_cols = [(c, df[c].astype(str).str.len().mean()) for c in df.columns
                 if _is_texty(df[c]) and not any(b in str(c).lower() for b in bad)]
    if not text_cols:
        return None
    best = max(text_cols, key=lambda t: t[1])
    return str(best[0]) if best[1] >= 20 else None


def detect_rating_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if any(h in str(col).lower() for h in ("rating", "stars", "score")):
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals) and vals.between(0, 5).mean() > 0.9:
                return str(col)
    return None


def sentiment_score(text: str) -> float:
    """Compact lexicon sentiment in [-1, 1] with simple negation flipping."""
    tokens = re.findall(r"[a-z']+", text.lower())
    score, hits = 0.0, 0
    for i, tok in enumerate(tokens):
        val = 1.0 if tok in _POSITIVE_WORDS else (-1.0 if tok in _NEGATIVE_WORDS else 0.0)
        if val == 0.0:
            continue
        if i > 0 and tokens[i - 1] in _NEGATORS:
            val = -val
        score += val
        hits += 1
    return round(score / hits, 3) if hits else 0.0


# ---------------------------------------------------------
# The positioning 2x2
# ---------------------------------------------------------
QUADRANTS = {
    ("premium", "product"):  "Premium quality brand",
    ("value",   "product"):  "Everyday value brand",
    ("premium", "brand"):    "Premium lifestyle brand",
    ("value",   "brand"):    "Affordable trendy brand",
}


def _axis_score(shares: dict, pos_themes: dict, neg_themes: dict) -> tuple[float, float, float]:
    """Normalised lean between two theme groups, in [-1, 1]."""
    pos = sum(float(shares.get(t, 0)) * w for t, w in pos_themes.items())
    neg = sum(float(shares.get(t, 0)) * w for t, w in neg_themes.items())
    total = pos + neg
    lean = 0.0 if total <= 1e-9 else (pos - neg) / total
    return round(lean, 3), round(pos, 1), round(neg, 1)


def perceptual_map(your_share: dict, lang: str = "en") -> dict:
    """Place the seller alone on the value<->premium x product<->brand 2x2.

        y+  Product driven (known for the product)
             |
    x-  -----+-----  x+      (x-: value pricing, x+: premium)
             |
        y-  Brand & aesthetic driven
    """
    x, prem, val = _axis_score(your_share, product_config.PREMIUM_THEME_W, product_config.VALUE_THEME_W)
    y, prod, brand = _axis_score(your_share, product_config.PRODUCT_THEME_W, product_config.BRAND_THEME_W)
    quad = QUADRANTS[("premium" if x >= 0 else "value",
                      "product" if y >= 0 else "brand")]
    you = {"name": "YOU", "x": x, "y": y, "is_you": True, "quadrant": quad,
           "premium_pct": prem, "value_pct": val, "product_pct": prod, "brand_pct": brand}
    return {
        "points": [you],
        "axis": {
            "x_pos": "Premium", "x_neg": "Value pricing",
            "y_pos": "Product-driven", "y_neg": "Brand & aesthetic",
        },
        "quadrant_labels": {
            "tr": QUADRANTS[("premium", "product")],
            "tl": QUADRANTS[("value", "product")],
            "br": QUADRANTS[("premium", "brand")],
            "bl": QUADRANTS[("value", "brand")],
        },
        "you": {"quadrant": quad, "x": x, "y": y},
    }


def analyze_reviews(df: pd.DataFrame, lang: str = "en", product_type: str | None = None) -> dict:
    text_col = detect_review_column(df)
    if text_col is None:
        return {"available": False,
                "reason": "Couldn't find a review text column. Make sure the file has a column of review text (e.g. 'Review')."}
    rating_col = detect_rating_column(df)

    reviews = df[text_col].dropna().astype(str)
    reviews = reviews[reviews.str.len() >= 5]
    n_reviews = len(reviews)
    if n_reviews < 5:
        return {"available": False, "reason": f"Only {n_reviews} usable reviews found — need at least 5 for a meaningful read."}

    pt = product_config.normalize(product_type)
    lexicon = product_config.positioning_lexicon(pt)
    themes = product_config.POSITIONING_THEMES

    theme_hits = {t: 0 for t in themes}
    theme_sent_scores: dict[str, list[float]] = {t: [] for t in themes}
    overall_scores = []

    lowered = reviews.str.lower()
    for text in lowered:
        s = sentiment_score(text)
        overall_scores.append(s)
        for theme, kws in lexicon.items():
            if any(k in text for k in kws):
                theme_hits[theme] += 1
                theme_sent_scores[theme].append(s)

    your_share = {t: round(theme_hits[t] / n_reviews * 100, 1) for t in themes}
    your_sentiment = {t: (round(sum(v) / len(v), 3) if v else None) for t, v in theme_sent_scores.items()}
    overall_sentiment = round(sum(overall_scores) / len(overall_scores), 3)
    avg_rating = None
    if rating_col:
        r = pd.to_numeric(df[rating_col], errors="coerce").dropna()
        if len(r):
            avg_rating = round(float(r.mean()), 2)

    # signature = biggest theme customers actually talk about; weakness = worst
    # sentiment among mentioned themes (excluding the signature).
    mentioned = [t for t in themes if your_share[t] >= 3]
    signature = max(mentioned, key=lambda t: your_share[t]) if mentioned else None
    weakness_candidates = [t for t in mentioned
                           if your_sentiment[t] is not None and t != signature]
    weakness = min(weakness_candidates, key=lambda t: your_sentiment[t]) if weakness_candidates else None
    # untapped = a positioning lever nobody talks about yet
    untapped = [t for t in themes if your_share.get(t, 0) < 2]

    pmap = perceptual_map(your_share, lang)
    quadrant = pmap["you"]["quadrant"]

    insights = _positioning_insights(
        your_share, your_sentiment, signature, weakness, untapped,
        overall_sentiment, avg_rating, n_reviews, quadrant, pt,
    )

    return {
        "available": True,
        "product_type": pt,
        "methodology_note": (
            "Read only from your own reviews using a keyword + sentiment pass — no external "
            "model, no peer comparison. Directional, not lab-precise: big gaps matter, "
            "1-2 point differences are noise."
        ),
        "n_reviews": n_reviews,
        "text_column": text_col,
        "rating_column": rating_col,
        "overall_sentiment": overall_sentiment,
        "avg_rating": avg_rating,
        "insights": insights,
        "position": {
            "quadrant": quadrant,
            "x": pmap["you"]["x"], "y": pmap["you"]["y"],
            "premium_pct": pmap["points"][0]["premium_pct"],
            "value_pct": pmap["points"][0]["value_pct"],
            "product_pct": pmap["points"][0]["product_pct"],
            "brand_pct": pmap["points"][0]["brand_pct"],
        },
        "share_chart": {
            "themes": themes,
            "yours": [your_share[t] for t in themes],
        },
        "sentiment_chart": {
            "themes": [t for t in themes if your_sentiment[t] is not None],
            "yours": [your_sentiment[t] for t in themes if your_sentiment[t] is not None],
        },
        "perceptual_map": pmap,
    }


def _positioning_insights(your_share, your_sentiment, signature, weakness, untapped,
                          overall_sentiment, avg_rating, n_reviews, quadrant, product_type) -> list[dict]:
    """Self-referential insights (key + params + concrete EN action)."""
    insights = []
    nouns = product_config.meta(product_type)["nouns"]

    if signature:
        share = your_share.get(signature, 0)
        insights.append({
            "type": "positive", "key": "pos_signature",
            "text": f"“{signature}” is what your customers talk about most — {share:.0f}% of reviews mention it.",
            "action": (f"Own “{signature}”: put it in your bio, pin your next 3 posts on it, and lead every "
                       f"product caption with it. It's already your strongest word — make it your brand hook."),
            "highlight": signature,
        })

    if weakness and your_sentiment.get(weakness) is not None and your_sentiment[weakness] < 0.15:
        s = your_sentiment[weakness]
        insights.append({
            "type": "negative", "key": "pos_weakness",
            "text": f"“{weakness}” is your softest spot — customers mention it but the sentiment is low ({s:+.2f}).",
            "action": (f"Fix “{weakness}” before spending on ads. Pick the single most common complaint under it "
                       f"and ship a fix this week, then reply to those reviewers so they see it changed."),
            "highlight": weakness,
        })

    if avg_rating is not None:
        if avg_rating >= 4.3:
            insights.append({
                "type": "positive", "key": "pos_rating_high",
                "text": f"Your average rating is {avg_rating}★ — that's strong social proof.",
                "action": f"Say it out loud: add “Rated {avg_rating}★” to your bio, product pages and packaging inserts. Reviews are free conversion.",
                "highlight": str(avg_rating),
            })
        elif avg_rating < 4.0:
            insights.append({
                "type": "warning", "key": "pos_rating_low",
                "text": f"Your average rating is {avg_rating}★ — below the trust line where new buyers hesitate.",
                "action": "Reply to every negative review (apologise + fix), then ask your happiest recent buyers for an honest review. Most small brands move +0.2–0.3★ in a month doing just this.",
                "highlight": str(avg_rating),
            })

    if untapped:
        t = untapped[0]
        insights.append({
            "type": "neutral", "key": "pos_untapped",
            "text": f"Almost nobody mentions “{t}” yet — an angle you haven't claimed.",
            "action": f"Test “{t}” as a positioning lever: one campaign or content series this month, then re-check reviews in 30 days to see if it lands.",
            "highlight": t,
        })

    mood = "happy" if overall_sentiment >= 0.4 else ("okay" if overall_sentiment >= 0.2 else "unhappy")
    insights.append({
        "type": "positive" if overall_sentiment >= 0.4 else ("neutral" if overall_sentiment >= 0.2 else "warning"),
        "key": "pos_sentiment",
        "text": f"Across {n_reviews} reviews your customers sound {mood} overall (sentiment {overall_sentiment:+.2f}).",
        "action": "Keep a monthly pulse: re-upload reviews each month and watch whether this trends up or down — it's your cheapest early-warning signal.",
        "highlight": f"{overall_sentiment:+.2f}",
    })

    return insights
