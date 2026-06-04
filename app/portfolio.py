from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.data_store import read_price_cache, read_table
from app.market_prices import is_trackable_ticker

PRICE_TOLERANCE_LOW = 0.5
PRICE_TOLERANCE_HIGH = 1.5


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def current_balance_sheet() -> pd.DataFrame:
    frame = read_table("balance_sheet")
    if frame.empty:
        return frame
    frame["Current value"] = numeric(frame.get("Current value", pd.Series(dtype=float)))
    return frame


def summary_metrics() -> dict[str, float]:
    balance = current_balance_sheet()
    monthly = read_table("monthly_tracking")
    metrics = {"assets": 0.0, "debt": 0.0, "net_worth": 0.0, "net_debt": 0.0}
    if not monthly.empty and "Net worth" in monthly:
        for col in ["Total assets", "Total debt", "Net debt", "Net worth"]:
            if col in monthly:
                monthly[col] = numeric(monthly[col])
        latest = monthly.iloc[-1]
        previous = monthly.iloc[-2] if len(monthly) > 1 else latest
        metrics["assets"] = float(latest.get("Total assets", 0) or 0)
        metrics["debt"] = float(latest.get("Total debt", 0) or 0)
        metrics["net_debt"] = float(latest.get("Net debt", 0) or 0)
        metrics["net_worth"] = float(latest.get("Net worth", 0) or 0)
        metrics["last_month_net_worth"] = float(previous.get("Net worth", 0) or 0)
        metrics["current_month_net_worth"] = metrics["net_worth"]
        metrics["monthly_delta"] = metrics["current_month_net_worth"] - metrics["last_month_net_worth"]
        metrics["as_of"] = str(latest.get("Date", ""))
    return metrics


def monthly_change_view() -> pd.DataFrame:
    monthly = read_table("monthly_tracking")
    if monthly.empty:
        return monthly
    frame = monthly.copy()
    numeric_cols = [
        "Cash / offsets",
        "Property value",
        "Property equity",
        "Crypto",
        "Shares",
        "Super",
        "Total assets",
        "Total debt",
        "Net debt",
        "Net worth",
    ]
    for col in numeric_cols:
        if col in frame:
            frame[col] = numeric(frame[col])

    for col in numeric_cols:
        if col in frame:
            frame[f"{col} MoM"] = frame[col].diff()

    if "Net worth" in frame:
        frame["Net worth MoM %"] = frame["Net worth"].pct_change().fillna(0)
    if "Total debt" in frame:
        frame["Debt reduction"] = -frame["Total debt MoM"]
    return frame


def latest_month_bridge() -> pd.DataFrame:
    changes = monthly_change_view()
    if changes.empty or len(changes) < 2:
        return pd.DataFrame()
    latest = changes.iloc[-1]
    bridge = [
        ("Cash / offsets", latest.get("Cash / offsets MoM", 0), "Liquidity movement"),
        ("Property equity", latest.get("Property equity MoM", 0), "Property equity after debt movement"),
        ("Crypto", latest.get("Crypto MoM", 0), "Crypto mark-to-market"),
        ("Shares", latest.get("Shares MoM", 0), "Listed portfolio movement"),
        ("Super", latest.get("Super MoM", 0), "Retirement bucket movement"),
        ("Debt reduction", latest.get("Debt reduction", 0), "Positive means debt reduced"),
        ("Net worth", latest.get("Net worth MoM", 0), "Total month-on-month change"),
    ]
    return pd.DataFrame(bridge, columns=["Driver", "Monthly change", "Comment"])


def monthly_component_changes() -> pd.DataFrame:
    changes = monthly_change_view()
    if changes.empty:
        return changes
    cols = [
        "Date",
        "Cash / offsets MoM",
        "Property equity MoM",
        "Crypto MoM",
        "Shares MoM",
        "Super MoM",
        "Debt reduction",
        "Net worth MoM",
    ]
    cols = [col for col in cols if col in changes.columns]
    frame = changes[cols].copy()
    frame = frame.iloc[1:].reset_index(drop=True)
    return frame


def price_source_view() -> pd.DataFrame:
    holdings = holdings_with_live_prices()
    if holdings.empty:
        return holdings
    rows = []
    cache = read_price_cache()
    prices = cache.get("prices", {})
    provenance = cache.get("provenance", {})
    for _, row in holdings.iterrows():
        ticker = str(row.get("Ticker", "")).strip().upper()
        cached = prices.get(ticker, {})
        market_time = cached.get("market_time")
        row_status = row.get("Provenance status") or provenance.get(ticker, {}).get("status") or "workbook_fallback"
        price_basis = str(row.get("Price basis", ""))
        as_of = "Workbook fallback"
        public_as_of = ""
        source = cached.get("source") or "Workbook screenshot / imported value"
        if market_time:
            try:
                public_as_of = datetime.fromtimestamp(int(market_time), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            except (TypeError, ValueError, OSError):
                public_as_of = "Unknown"
        elif price_basis in {"Live public feed", "Stale cached public feed"}:
            public_as_of = cache.get("updated_at") or "Public feed timestamp unavailable"

        if price_basis.startswith("Workbook fallback"):
            source = "Workbook screenshot/imported value"
            if row_status == "workbook_fallback_public_outside_tolerance":
                as_of = "Workbook fallback; public price outside tolerance"
            else:
                as_of = "Workbook fallback"
        else:
            as_of = public_as_of or "Public feed timestamp unavailable"
        rows.append(
            {
                "Ticker": ticker,
                "Symbol": cached.get("symbol") or ticker,
                "Currency": row.get("Currency"),
                "Price used": row.get("Live price"),
                "Workbook price": row.get("Workbook price"),
                "% vs workbook": row.get("Public price vs workbook"),
                "Price as of": as_of,
                "Provenance status": row_status,
                "Tolerance check": row.get("Tolerance check"),
                "Source": source,
            }
        )
    fx = cache.get("fx", {}).get("USD_AUD", {})
    if fx:
        rows.append(
            {
                "Ticker": "USD/AUD",
                "Symbol": "USD/AUD",
                "Currency": "FX",
                "Price used": fx.get("rate"),
                "Price as of": fx.get("source_time") or cache.get("updated_at"),
                "Provenance status": cache.get("refresh", {}).get("fx_status") or "fx_cached",
                "Tolerance check": "Not applicable",
                "Source": fx.get("source", "FX source"),
            }
        )
    return pd.DataFrame(rows)


def allocation_view() -> pd.DataFrame:
    balance = current_balance_sheet()
    metrics = summary_metrics()
    required = {"Asset class", "Current value"}
    if balance.empty or not required.issubset(balance.columns):
        return pd.DataFrame(
            columns=[
                "Asset class",
                "Current value",
                "Current allocation",
                "Target min",
                "Target base",
                "Target max",
                "Drift vs target",
                "Owner/lens",
                "Notes",
            ]
        )
    rows = balance[balance["Asset class"].isin(["Cash / offsets", "Property equity", "Crypto", "Shares", "Super"])].copy()
    rows["Current value"] = numeric(rows["Current value"])
    net_worth = metrics.get("net_worth") or rows["Current value"].sum()
    rows["Current allocation"] = rows["Current value"] / net_worth if net_worth else 0
    rows["Target base"] = numeric(rows.get("Target base", pd.Series(0, index=rows.index)))
    rows["Drift vs target"] = rows["Current allocation"] - rows["Target base"]
    return rows


def risk_summary() -> pd.DataFrame:
    metrics = summary_metrics()
    allocation = allocation_view()
    values = {
        "Debt / assets": metrics["debt"] / metrics["assets"] if metrics["assets"] else 0,
        "Net debt / net worth": metrics["net_debt"] / metrics["net_worth"] if metrics["net_worth"] else 0,
    }
    for _, row in allocation.iterrows():
        values[f"{row['Asset class']} / net worth"] = float(row["Current allocation"])

    rows = []
    for name, value in values.items():
        status = "Watch"
        if "Property" in name and value > 0.55:
            status = "Concentrated"
        elif "Cash" in name and value >= 0.20:
            status = "Strong"
        elif "Shares" in name and value < 0.05:
            status = "Underweight"
        elif "Debt / assets" in name and value < 0.35:
            status = "Controlled"
        elif "Net debt" in name and value < 0.20:
            status = "Controlled"
        rows.append({"Metric": name, "Current": value, "Status": status})
    return pd.DataFrame(rows)


def executive_brief() -> list[dict[str, str]]:
    metrics = summary_metrics()
    allocation = allocation_view()
    risks = risk_summary()
    decisions = read_table("decision_log")
    evidence = read_table("evidence_register")

    property_row = allocation[allocation["Asset class"].eq("Property equity")]
    cash_row = allocation[allocation["Asset class"].eq("Cash / offsets")]
    shares_row = allocation[allocation["Asset class"].eq("Shares")]
    crypto_row = allocation[allocation["Asset class"].eq("Crypto")]

    property_alloc = float(property_row["Current allocation"].iloc[0]) if len(property_row) else 0
    cash_alloc = float(cash_row["Current allocation"].iloc[0]) if len(cash_row) else 0
    shares_alloc = float(shares_row["Current allocation"].iloc[0]) if len(shares_row) else 0
    crypto_alloc = float(crypto_row["Current allocation"].iloc[0]) if len(crypto_row) else 0
    open_decisions = 0
    if not decisions.empty and "Approval status" in decisions:
        closed = decisions["Approval status"].astype(str).str.lower().isin(["closed", "clarified by rodney", "implemented", "executed"])
        open_decisions = int((~closed).sum())
    missing_evidence = 0
    if not evidence.empty and "Status" in evidence:
        missing_evidence = int(evidence["Status"].astype(str).str.lower().str.contains("missing|open|partial|ongoing").sum())

    brief = [
        {
            "title": "Chief Read",
            "status": "Constructive, controlled",
            "body": (
                f"Net worth is {metrics['net_worth']:,.0f} AUD, up {metrics.get('monthly_delta', 0):,.0f} AUD for the month. "
                "The operating question is not solvency; it is governance, concentration, and disciplined deployment."
            ),
        },
        {
            "title": "Allocation",
            "status": "Property-led",
            "body": (
                f"Property equity is {property_alloc:.1%} of net worth versus a 50.0% base policy. "
                f"Shares are {shares_alloc:.1%}, still far below the 15.0% base policy."
            ),
        },
        {
            "title": "Liquidity",
            "status": "Protected first",
            "body": (
                f"Cash and offsets are {cash_alloc:.1%} of net worth. Current policy treats this as PPOR/Earlwood "
                "protected liquidity, with new deployment coming from monthly surplus rather than existing cash."
            ),
        },
        {
            "title": "Risk Control",
            "status": "Review, no action",
            "body": (
                f"Crypto is {crypto_alloc:.1%} of net worth and property remains the dominant exposure. "
                f"{open_decisions} decision items and {missing_evidence} evidence/control items need governance attention before major moves."
            ),
        },
    ]
    return brief


def stress_view() -> pd.DataFrame:
    metrics = summary_metrics()
    balance = current_balance_sheet()
    crypto = float(balance.loc[balance["Asset class"].eq("Crypto"), "Current value"].iloc[0]) if not balance.empty and len(balance.loc[balance["Asset class"].eq("Crypto")]) else 0
    property_value = 0.0
    monthly = read_table("monthly_tracking")
    if not monthly.empty and "Property value" in monthly:
        property_value = float(numeric(monthly["Property value"]).iloc[-1])

    scenarios = [
        ("Property -10%", -0.10 * property_value, "Property concentration pressure test"),
        ("Property -20%", -0.20 * property_value, "Severe property value drawdown"),
        ("Crypto -50%", -0.50 * crypto, "Crypto volatility contribution"),
        ("Rates +1%", -0.01 * metrics["net_debt"], "Annualized pressure on net debt"),
        ("Rates +2%", -0.02 * metrics["net_debt"], "Higher rate shock on net debt"),
        ("Combined bear case", -0.10 * property_value - 0.50 * crypto - 0.01 * metrics["net_debt"], "Property, crypto, and rates together"),
    ]
    return pd.DataFrame(scenarios, columns=["Scenario", "Estimated impact AUD", "Interpretation"])


def holdings_with_live_prices() -> pd.DataFrame:
    holdings = read_table("listed_share_snapshot")
    if holdings.empty:
        return holdings
    holdings = holdings[holdings["Ticker"].astype(str).map(is_trackable_ticker)].copy()

    cache = read_price_cache()
    price_map = cache.get("prices", {})
    usd_aud = cache.get("fx", {}).get("USD_AUD", {}).get("rate") or 1
    holdings["Shares"] = numeric(holdings.get("Shares", pd.Series(dtype=float)))
    value_col = "Equity / value native" if "Equity / value native" in holdings else "Equity"
    pl_col = "Profit / loss native" if "Profit / loss native" in holdings else "Profit / loss"
    holdings["Native value"] = numeric(holdings.get(value_col, pd.Series(dtype=float)))
    holdings["Native P/L"] = numeric(holdings.get(pl_col, pd.Series(dtype=float)))
    holdings["Implied cost base native"] = holdings["Native value"] - holdings["Native P/L"]

    live_prices = []
    live_values_aud = []
    price_basis = []
    workbook_prices = []
    price_ratios = []
    tolerance_checks = []
    provenance_statuses = []
    cache_provenance = cache.get("provenance", {})
    for _, row in holdings.iterrows():
        ticker = str(row.get("Ticker", "")).strip().upper()
        currency = str(row.get("Currency", "AUD")).strip().upper()
        price = price_map.get(ticker, {}).get("price")
        cache_status = cache_provenance.get(ticker, {}).get("status")
        workbook_price = float(row["Native value"]) / float(row["Shares"]) if row["Shares"] else 0
        workbook_prices.append(workbook_price)
        ratio = float(price) / workbook_price if price and workbook_price else None
        price_ratios.append(ratio)
        if price and workbook_price and (ratio < PRICE_TOLERANCE_LOW or ratio > PRICE_TOLERANCE_HIGH):
            price = workbook_price if row["Shares"] else None
            basis = "Workbook fallback - public outside tolerance"
            tolerance_check = "Outside 50% tolerance"
            provenance_status = "workbook_fallback_public_outside_tolerance"
        elif price:
            basis = "Stale cached public feed" if cache_status == "stale_cache_after_refresh_error" else "Live public feed"
            tolerance_check = "Within 50% tolerance" if workbook_price else "No workbook comparison"
            provenance_status = "stale_cache_price_used" if cache_status == "stale_cache_after_refresh_error" else "public_price_used"
        elif row["Shares"]:
            price = workbook_price
            basis = "Workbook fallback"
            tolerance_check = "No public price"
            provenance_status = "workbook_fallback_no_public_price"
        else:
            basis = "Workbook fallback"
            tolerance_check = "No shares"
            provenance_status = "workbook_fallback_no_shares"
        live_prices.append(price)
        price_basis.append(basis)
        tolerance_checks.append(tolerance_check)
        provenance_statuses.append(provenance_status)
        if price:
            value = float(row["Shares"]) * float(price)
            if currency == "USD":
                value *= float(usd_aud)
            live_values_aud.append(value)
        else:
            value = float(row["Native value"])
            if currency == "USD":
                value *= float(usd_aud)
            live_values_aud.append(value)

    holdings["Live price"] = live_prices
    holdings["Workbook price"] = workbook_prices
    holdings["Public price vs workbook"] = price_ratios
    holdings["Price basis"] = price_basis
    holdings["Tolerance check"] = tolerance_checks
    holdings["Provenance status"] = provenance_statuses
    holdings["Live value AUD"] = live_values_aud
    holdings["Cost base AUD"] = holdings["Implied cost base native"]
    holdings.loc[holdings["Currency"].astype(str).str.upper().eq("USD"), "Cost base AUD"] *= float(usd_aud)
    holdings["Live P/L AUD"] = holdings["Live value AUD"] - holdings["Cost base AUD"]
    return holdings
