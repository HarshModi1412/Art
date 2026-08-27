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
    "customer_name": ["customername", "clientname", "buyername", "patronname", "membername", "guestname", "fullname"],
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


def suggest_mapping(df: pd.DataFrame) -> dict:
    """Guess a role -> column mapping from column names + dtypes.

    For each role we score every column by WHERE it matches in that role's
    priority-ordered keyword list (rank 0 = strongest). The best-ranked column
    wins the role — so 'Final Total' beats 'Price' for amount even though both
    match, and a longer/earlier keyword like 'invoiceno' beats a generic
    'order'. Roles are resolved strongest-match-first so a column isn't stolen
    by a weaker role."""
    suggestion: dict[str, str | None] = {role: None for role in ROLE_KEYWORDS}
    cols = list(df.columns)
    used = set()

    def norm(c):
        return str(c).lower().replace(" ", "").replace("_", "").replace("-", "").replace(".", "")

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
