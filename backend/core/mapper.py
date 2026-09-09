"""
Column mapping — web port of modules/mapper.classify_and_extract_data.

In Streamlit this was an interactive widget flow; here it is split into:
  suggest_mapping(df)          -> auto-detected role for each canonical field
  build_transactions(df, map)  -> standardized Transactions dataframe

Canonical fields used by the rest of the app:
  date, customer_id, customer_name, order_id, product, category, subcategory, quantity, amount
"""
import pandas as pd

# keywords used to guess which uploaded column plays which role.
# For each role the list is PRIORITY-ORDERED: earlier = stronger preference,
# so "final total" wins over "price" when both exist (real POS exports carry
# both, and the line total — not the unit price — is the revenue figure).
ROLE_KEYWORDS = {
    "date": ["date", "orderdate", "invoicedate", "billdate", "time", "timestamp", "day"],
    "customer_id": ["customerid", "custid", "clientid", "memberid", "userid", "buyerid", "phone", "mobile", "contact", "customer", "cust", "client", "member", "buyer"],
    # "billingname" / "shippingname" sit ahead of the generic words because on
    # every real platform export they ARE the customer's name — and because
    # leaving them out let "bill" claim them for order_id instead.
    "customer_name": ["customername", "billingname", "shippingname", "billingfirstname",
                      "clientname", "buyername", "patronname", "membername",
                      "guestname", "fullname"],
    "order_id": ["orderid", "invoiceno", "invoicenumber", "billno", "billnumber", "receiptno", "kotno", "order", "invoice", "transaction", "bill", "receipt", "txn", "ticket"],
    "product": ["itemname", "productname", "product", "item", "dish", "menuitem", "sku", "description", "name"],
    "category": ["category", "itemcategory", "maincategory", "cat", "department", "menucategory", "group", "type"],
    "subcategory": ["subcategory", "subcat", "variation", "variant"],
    "quantity": ["quantity", "qty", "units", "count", "nos"],
    # amount: prefer the FINAL line total, then net/sub totals, then generic
    # revenue words, and only fall back to unit price if nothing better exists.
    "amount": ["finaltotal", "grandtotal", "nettotal", "linetotal", "totalamount",
               "subtotal", "netamount", "amount", "sales", "revenue", "total",
               "value", "spend", "price", "rate", "mrp"],
}

REQUIRED = ["date", "amount"]


def _norm(c) -> str:
    return (str(c).lower().replace(" ", "").replace("_", "")
            .replace("-", "").replace(".", ""))


# Known platform exports, matched on their signature columns.
#
# BUG THIS FIXES: keyword scoring is good on hand-made Indian spreadsheets and
# quietly wrong on the big platform exports, because those reuse words the
# scorer treats as strong signals. A Shopify orders CSV has a "Billing Name"
# column: it normalises to "billingname", which contains "bill", which is an
# order_id keyword -- so the CUSTOMER'S NAME was being stored as the order
# number, while customer_name was left empty and the real order column
# ("Name") went unused. Order counts and average order value were then computed
# off a name column, and every win-back message opened with "Hi there". The
# seller was shown the suggestion and could fix it, but the default was wrong
# and wrong silently, which is worse than asking.
#
# A recognised export is mapped as a whole, by people who know the format,
# rather than column by column by a scorer that cannot see the shape.
PRESETS = [
    {
        "id": "shopify",
        "name": "Shopify orders export",
        # "lineitemname" alone is enough to identify it; "name" + "createdat"
        # guard against a look-alike.
        "signature": ["lineitemname", "createdat"],
        "map": {
            "date": "createdat",
            "order_id": "name",
            "customer_name": "billingname",
            "customer_id": "email",
            "product": "lineitemname",
            "quantity": "lineitemquantity",
            "amount": "lineitemprice",
        },
        # Shopify gives a PER-UNIT price on each line row and puts the order
        # total only on the first row of a multi-line order. Taking the unit
        # price as revenue undercounts every order of more than one item, so
        # the line total is reconstructed as price x quantity.
        "amount_is_unit": True,
    },
    {
        "id": "woocommerce",
        "name": "WooCommerce order export",
        "signature": ["orderdate", "itemname"],
        "map": {
            "date": "orderdate",
            "order_id": "ordernumber",
            "customer_name": "billingfirstname",
            "customer_id": "billingemail",
            "product": "itemname",
            "quantity": "quantity",
            "amount": "itemcost",
        },
    },
    {
        "id": "amazon_mtr",
        "name": "Amazon MTR / transaction report",
        "signature": ["orderid", "asin"],
        "map": {
            "date": "orderdate",
            "order_id": "orderid",
            "product": "productname",
            "category": "productcategory",
            "quantity": "quantity",
            "amount": "invoiceamount",
        },
    },
]


def detect_preset(df: pd.DataFrame) -> dict | None:
    """Which known platform export this is, if any.

    Returns the preset with its `resolved` mapping (role -> the actual column
    name as it appears in this file), or None when nothing matches well
    enough. A preset only applies when it can fill both required roles --
    a half-matched preset is worse than the scorer."""
    have = {_norm(c): str(c) for c in df.columns}
    for preset in PRESETS:
        if not all(sig in have for sig in preset["signature"]):
            continue
        resolved = {role: have[key] for role, key in preset["map"].items()
                    if key in have}
        if all(resolved.get(r) for r in REQUIRED):
            return {**preset, "resolved": resolved}
    return None


def suggest_mapping(df: pd.DataFrame) -> dict:
    """Guess a role -> column mapping from column names + dtypes.

    For each role we score every column by WHERE it matches in that role's
    priority-ordered keyword list (rank 0 = strongest). The best-ranked column
    wins the role — so 'Final Total' beats 'Price' for amount even though both
    match, and a longer/earlier keyword like 'invoiceno' beats a generic
    'order'. Roles are resolved strongest-match-first so a column isn't stolen
    by a weaker role."""
    # A recognised platform export is mapped as a whole. The scorer never sees
    # it, because on these files the scorer is confidently wrong (see PRESETS).
    preset = detect_preset(df)
    if preset:
        out: dict = {role: None for role in ROLE_KEYWORDS}
        out.update(preset["resolved"])
        out["_preset"] = preset["id"]
        out["_preset_name"] = preset["name"]
        if preset.get("amount_is_unit"):
            out["_amount_is_unit"] = True
        return out

    suggestion: dict[str, str | None] = {role: None for role in ROLE_KEYWORDS}
    cols = list(df.columns)
    used = set()
    norm = _norm

    # collect all (role, col, rank) candidate matches
    candidates = []
    for role, keywords in ROLE_KEYWORDS.items():
        for col in cols:
            n = norm(col)
            if role == "category" and "sub" in n:
                continue  # reserve sub-columns for subcategory
            for rank, kw in enumerate(keywords):
                if norm(kw) in n:
                    candidates.append((rank, role, col))
                    break  # best rank for this (role, col)

    # assign greedily: lowest rank first, one column per role, one role per column
    for rank, role, col in sorted(candidates, key=lambda t: t[0]):
        if suggestion[role] is None and col not in used:
            suggestion[role] = col
            used.add(col)

    # fall back: first parseable-date column, best numeric column for amount
    if suggestion["date"] is None:
        for col in cols:
            try:
                if pd.to_datetime(df[col], errors="coerce").notna().mean() > 0.8:
                    suggestion["date"] = col
                    break
            except Exception:
                continue
    if suggestion["amount"] is None:
        numeric = [c for c in df.select_dtypes("number").columns if c not in used]
        if numeric:
            # prefer the numeric column with the largest sum (line totals > unit prices)
            suggestion["amount"] = str(max(numeric, key=lambda c: pd.to_numeric(df[c], errors="coerce").sum()))

    return suggestion


def classify_file(df: pd.DataFrame) -> str:
    """Rough equivalent of the original file classification: is this a Transactions file?"""
    s = suggest_mapping(df)
    if s["date"] and s["amount"]:
        return "Transactions"
    return "Other"


def build_transactions(df: pd.DataFrame, mapping: dict) -> tuple[pd.DataFrame, dict]:
    """Rename user-confirmed columns to canonical names and clean types."""
    missing = [r for r in REQUIRED if not mapping.get(r)]
    if missing:
        raise ValueError(f"Missing required mappings: {', '.join(missing)}")

    rename = {src: role for role, src in mapping.items() if src and src in df.columns}
    out = df.rename(columns=rename)
    keep = [c for c in ROLE_KEYWORDS if c in out.columns]
    out = out[keep].copy()

    rows_before = len(out)

    out["date"] = _parse_dates_robust(out["date"])
    out["amount"] = _clean_numeric(out["amount"])
    if "quantity" in out.columns:
        out["quantity"] = _clean_numeric(out["quantity"])

    # Some exports (Shopify) give a PER-UNIT price on each line rather than the
    # line total. Taking that as revenue undercounts every order of more than
    # one item, so the line total is reconstructed here. Only ever applied when
    # the mapping explicitly says so — never guessed.
    if mapping.get("_amount_is_unit") and "quantity" in out.columns:
        qty = out["quantity"].fillna(1).replace(0, 1)
        out["amount"] = out["amount"] * qty

    bad_date = out["date"].isna().sum()
    bad_amount = out["amount"].isna().sum()
    out = out.dropna(subset=["date", "amount"])

    diagnostics = {
        "rows_before": rows_before,
        "rows_after": len(out),
        "dropped_rows": rows_before - len(out),
        "dropped_bad_date": int(bad_date),
        "dropped_bad_amount": int(bad_amount),
    }
    return out, diagnostics


def _clean_numeric(series: pd.Series) -> pd.Series:
    """
    Coerce a column to numbers, tolerating the formatting real business data
    actually comes in: currency symbols (₹, $, €, £), thousand-separator
    commas, surrounding whitespace, and parentheses used for negatives
    (accounting style, e.g. "(120.00)" -> -120.00). Plain pd.to_numeric()
    turns all of these into NaN, which silently empties every chart
    downstream — this is the fix for that.
    """
    if pd.api.types.is_numeric_dtype(series):
        return series
    s = series.astype(str).str.strip()
    is_paren_negative = s.str.match(r"^\(.*\)$")
    s = s.str.replace(r"[()]", "", regex=True)
    s = s.str.replace(r"[₹$€£,]", "", regex=True)
    s = s.str.replace(r"\s+", "", regex=True)
    numeric = pd.to_numeric(s, errors="coerce")
    numeric = numeric.where(~is_paren_negative, -numeric)
    return numeric


def _parse_dates_robust(series: pd.Series) -> pd.Series:
    """
    Try both month-first (US, e.g. 07/17/2026) and day-first (India/UK,
    e.g. 17/07/2026) parsing and keep whichever produces fewer unparseable
    (NaT) values. Ambiguous dates like 03/04/2025 can't be resolved with
    certainty either way, but this avoids the common failure mode where an
    entire day-first dataset gets silently mangled or dropped because the
    parser defaulted to month-first.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    month_first = pd.to_datetime(series, errors="coerce")
    import warnings as _w
    with _w.catch_warnings():
        # we intentionally parse BOTH ways and keep whichever succeeds more —
        # pandas' dayfirst-mismatch warning is expected noise here
        _w.simplefilter("ignore", UserWarning)
        day_first = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return day_first if day_first.notna().sum() > month_first.notna().sum() else month_first
