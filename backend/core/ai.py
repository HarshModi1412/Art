"""
AI features — ports of BA.py (Business Analyst) and chatbot2.py.

Same models, same prompts, same caching-by-dataframe-hash idea. The only
change: instead of returning Plotly figures, chart data is computed
server-side and shipped to the frontend as JSON for Plotly.js.
"""
import hashlib
import json
import os
import re
from functools import lru_cache

import pandas as pd

try:
    from openai import OpenAI
except ImportError:  # allows the non-AI parts of the app to run without the package
    OpenAI = None

_client = None


def get_client():
    """Port of get_client(): key comes from the environment instead of st.secrets."""
    global _client
    if _client is None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY missing — set it as an environment variable.")
        if OpenAI is None:
            raise RuntimeError("openai package not installed. Run: pip install openai")
        _client = OpenAI(api_key=key)
    return _client


def df_hash(df: pd.DataFrame) -> str:
    """Port of df_hash() — lightweight dataframe fingerprint."""
    return hashlib.md5(pd.util.hash_pandas_object(df, index=True).values).hexdigest()


@lru_cache(maxsize=256)
def ask_llm_cached(prompt: str) -> str:
    """Port of ask_llm_cached() — same model, temperature, and token budget."""
    client = get_client()
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0.2,
            max_output_tokens=900,
        )
        return response.output_text
    except Exception as e:
        return f"❌ OpenAI Error: {e}"


# =========================================================
# BUSINESS ANALYST  (BA.py)
# =========================================================
def get_insights(df: pd.DataFrame) -> list[dict]:
    """Port of get_insights() — identical prompt, JSON-array extraction."""
    prompt = f"""
You are a senior business consultant.

Dataset columns:
{", ".join(df.columns)}

Column types:
{df.dtypes.to_string()}

Statistical summary:
{df.describe(include="all").to_string()}

Sample data:
{df.head(15).to_string(index=False)}

Goal: Improve profitability

Return ONLY JSON:
[
{{
"decision":"short insight",
"observation":"data-backed observation",
"why_it_matters":"business reasoning",
"action":"recommended action",
"impact":"estimated impact"
}}
]
"""
    raw = ask_llm_cached(prompt)
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        return json.loads(raw[start:end])
    except Exception:
        return []


def get_chart_spec(insight_text: str, columns: str) -> dict | None:
    """Port of get_chart_spec() — identical prompt, JSON-object extraction."""
    prompt = f"""
You are a data visualization expert.

Columns:
{columns}

Insight:
"{insight_text}"

Return ONLY JSON:
{{
"chart_type": "bar | line | scatter | pie",
"x": "column",
"y": "column OR ['col1','col2']",
"title": "title"
}}
"""
    raw = ask_llm_cached(prompt)
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return None


def generate_chart_data(df: pd.DataFrame, spec: dict) -> dict | None:
    """Port of generate_chart() — same grouping logic, but returns Plotly.js-ready JSON."""
    try:
        chart_type = spec["chart_type"].lower()
        x, y = spec["x"], spec["y"]
        title = spec.get("title", "Chart")
        if x not in df.columns:
            return None

        if isinstance(y, str):
            if y not in df.columns:
                return None
            d = df[[x, y]].dropna().groupby(x)[y].mean().reset_index()
            return {
                "chart_type": chart_type,
                "title": title,
                "series": [{"name": y, "x": d[x].astype(str).tolist(), "y": d[y].round(3).tolist()}],
            }
        else:
            valid = [c for c in y if c in df.columns]
            if not valid:
                return None
            d = df[[x] + valid].dropna()
            series = []
            for col in valid:
                g = d.groupby(x)[col].mean().reset_index()
                series.append({"name": col, "x": g[x].astype(str).tolist(), "y": g[col].round(3).tolist()})
            return {"chart_type": chart_type, "title": title, "series": series}
    except Exception:
        return None


def _fallback_message(c: dict) -> str:
    """
    Deterministic, no-AI-required message. Used whenever the LLM call errors
    out or its response can't be parsed as JSON — guarantees every customer
    gets a real message, never a blank cell. Still grounded in the same
    market-basket-analysis signal the AI prompt uses.
    """
    import random
    if c["signal_strength"] == "strong":
        msg = (
            f"Hi! It's been {c['recency_days']} days since we last saw you — "
            f"your usual {c['favorite_item']} is still on the menu and waiting for you."
        )
        if c.get("cross_sell_item"):
            msg += f" This time, you might also love the {c['cross_sell_item']} — a favorite pairing with {c['favorite_item']}."
        if c.get("price_tier") == "premium":
            msg += " We'd love to have one of our regulars back!"
        msg += " Come by soon 🙂"
    else:
        creative = [
            "It's been a while! We've got a few new things on the menu we think you'd enjoy discovering.",
            "Long time no see! Swing by sometime this week — there's always something fresh brewing.",
            "We noticed you haven't stopped by in a bit. Come treat yourself to something new soon!",
            "Missed seeing you around! Next time you're nearby, drop in — we'd love to catch up.",
        ]
        msg = random.choice(creative)
    return msg[:300]


def generate_winback_messages(customers: list[dict]) -> list[dict]:
    """
    One batched prompt -> one short, personalized win-back message per at-risk
    customer, grounded in marketing-analytics signals (favorite category, price
    tier, preferred day, spend trend, and market-basket cross-sell pairing)
    rather than just a single top product. When a customer has too little
    history to personalize honestly, the model is instructed to write
    something warm and creative instead of guessing.

    Every customer is guaranteed a non-blank message: if the AI call fails or
    its JSON response can't be parsed, a deterministic fallback message (still
    grounded in the same analytics) is used instead of leaving the cell empty.

    Batches of 25 to keep prompts fast and within token limits; results merge
    back into a single list keyed by customer_id.
    """
    if not customers:
        return []

    BATCH = 25
    all_messages: dict[str, str] = {}

    for i in range(0, len(customers), BATCH):
        batch = customers[i:i + BATCH]
        lines = []
        for c in batch:
            if c["signal_strength"] == "strong":
                detail = (
                    f"favorite: {c['favorite_item']}"
                    + (f" ({c['category_affinity_pct']:.0f}% of their spend)" if c.get("category_affinity_pct") else "")
                    + f" | category: {c['favorite_category']} | spend tier: {c['price_tier']}"
                    + (f" | usually visits on {c['preferred_day']}s" if c.get("preferred_day") else "")
                    + (f" | pairs well with: {c['cross_sell_item']} (market basket analysis)" if c.get("cross_sell_item") else "")
                    + f" | {c['trend']}"
                )
            else:
                detail = "not enough purchase history to personalize — write something warm and creative instead"
            lines.append(
                f"- id: {c['customer_id']} | last visit: {c['last_purchase_date']} "
                f"({c['recency_days']} days ago) | total spend: {c['monetary']:.0f} | {detail}"
            )
        listing = "\n".join(lines)

        prompt = f"""
You are a savvy small-business marketer writing short win-back messages to customers
who used to buy regularly but haven't visited in a while. You understand customer
segmentation and market basket analysis — you use recency, spend tier, category
preference, purchase trend, and cross-sell pairings to make each message feel
personally relevant, not like a mass blast.

Customers:
{listing}

For each customer, write ONE short, warm, non-pushy WhatsApp-style message (under 300 characters):

- If real purchase signals are given (favorite item, category, spend tier, trend, cross-sell pairing),
  weave ONE or TWO of them in naturally — e.g. reference their favorite item by name, suggest the
  item that's commonly bought alongside it (from market basket analysis) as something new to try,
  or acknowledge they're a valued regular if their spend tier is premium. Don't cram in every data
  point — pick what feels natural.
- If a customer is marked "not enough purchase history to personalize", do NOT invent fake
  specifics. Instead write something genuinely creative and inviting — a bit of warmth,
  curiosity, or a light reason to try something new — that doesn't pretend to know them.
- No mass-marketing tone: no ALL CAPS, no emoji spam, no fake urgency, no generic "we miss you!"
  copy-pasted across everyone.

Return ONLY a JSON array, one object per customer, in this exact format, and nothing else —
no markdown code fences, no commentary before or after:
[
{{"customer_id": "the id exactly as given", "message": "the message text"}}
]
"""
        raw = ask_llm_cached(prompt)
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start == -1 or end <= start:
                raise ValueError("no JSON array found in the model's response")
            parsed = json.loads(raw[start:end])
            for item in parsed:
                cid = str(item.get("customer_id", "")).strip()
                msg = str(item.get("message", "")).strip()
                if cid and msg:
                    all_messages[cid] = msg
        except Exception:
            pass  # any customer still missing after this batch gets the deterministic fallback below

    return [
        {**c, "message": all_messages.get(c["customer_id"]) or _fallback_message(c)}
        for c in customers
    ]


def run_business_analyst(raw_dfs: dict[str, pd.DataFrame]) -> list[dict]:
    """Port of run_business_analyst_tab() — returns structured results per file."""
    results = []
    for filename, df in raw_dfs.items():
        if not isinstance(df, pd.DataFrame):
            continue
        insights = get_insights(df)
        entry = {"file": filename, "preview_columns": list(df.columns),
                 "preview_rows": df.head(20).astype(str).values.tolist(), "insights": []}
        columns = ", ".join(df.columns)
        for ins in insights:
            spec = get_chart_spec(ins.get("decision", ""), columns)
            chart = generate_chart_data(df, spec) if spec else None
            entry["insights"].append({**ins, "chart": chart})
        results.append(entry)
    return results


# =========================================================
# CHATBOT  (chatbot2.py)
# =========================================================
def ask_chatgpt(messages: list[dict], df_context: str | None = None, first_time: bool = False) -> str:
    """Port of ask_chatgpt() — same system prompt, first-time tips prompt, model, settings."""
    client = get_client()
    try:
        structured = [{
            "role": "system",
            "content": "You are a smart business consultant. Give short, practical, data-backed advice. Avoid long answers.",
        }]
        if first_time and df_context:
            structured.append({
                "role": "user",
                "content": f"""
Give 3 short, practical tips to improve revenue or profit.
Format:
- 📌 Tip 1: ...
- 📌 Tip 2: ...
(Chart: X vs Y) ← only if useful
Keep it simple.
{df_context}
""",
            })
        structured.extend({"role": m["role"], "content": m["content"]} for m in messages)

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=structured,
            temperature=0.3,
            max_output_tokens=800,
        )
        return response.output_text
    except Exception as e:
        return f"❌ OpenAI Error: {e}"


def try_plot_instruction(text: str, df: pd.DataFrame) -> dict | None:
    """Port of try_plot_instruction() — detect 'X vs Y' and return scatter data."""
    try:
        match = re.search(r"([A-Za-z0-9_ ]+)\s+vs\s+([A-Za-z0-9_ ]+)", text)
        if not match:
            return None
        x_col, y_col = match.group(1).strip(), match.group(2).strip()
        norm = lambda s: s.lower().replace(" ", "")
        x_match = next((c for c in df.columns if norm(x_col) in norm(str(c))), None)
        y_match = next((c for c in df.columns if norm(y_col) in norm(str(c))), None)
        if x_match and y_match:
            d = df[[x_match, y_match]].dropna().head(1000)
            return {
                "chart_type": "scatter",
                "title": f"{y_match} vs {x_match}",
                "series": [{"name": str(y_match),
                            "x": d[x_match].astype(str).tolist(),
                            "y": pd.to_numeric(d[y_match], errors="coerce").tolist()}],
            }
    except Exception:
        return None
    return None


def run_chat(raw_dfs: dict[str, pd.DataFrame], messages: list[dict], first_time: bool) -> dict:
    """Port of run_chat() request handling. `messages` = full history, last item is the new user turn."""
    valid = [df for df in raw_dfs.values() if isinstance(df, pd.DataFrame)]
    if not valid:
        return {"reply": "⚠️ No data provided. Upload files first.", "chart": None}

    df_combined = pd.concat(valid, ignore_index=True)
    df_context = f"Here is sample business data:\n{df_combined.head(30).to_json(orient='records')}"

    raw = ask_chatgpt(messages, df_context=df_context, first_time=first_time)
    reply = re.sub(r"```(json)?", "", raw, flags=re.DOTALL).strip("` \n")
    chart = try_plot_instruction(reply, df_combined)
    return {"reply": reply, "chart": chart}
