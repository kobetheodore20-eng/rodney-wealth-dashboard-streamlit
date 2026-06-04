from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.data_store import read_price_cache, read_table
from app.portfolio import (
    allocation_view,
    holdings_with_live_prices,
    monthly_change_view,
    numeric,
    price_source_view,
    risk_summary,
    summary_metrics,
)


@dataclass(frozen=True)
class Signal:
    name: str
    status: str
    detail: str
    priority: str = "Review"


def _money(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"A${value / 1_000_000:,.2f}m"
    return f"A${value:,.0f}"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def wealth_scorecard() -> pd.DataFrame:
    metrics = summary_metrics()
    monthly = monthly_change_view()
    allocation = allocation_view()
    risks = risk_summary()
    sources = price_source_view()
    evidence = read_table("evidence_register")
    decisions = read_table("decision_log")

    mom_pct = 0.0
    if not monthly.empty and "Net worth MoM %" in monthly:
        mom_pct = float(monthly["Net worth MoM %"].iloc[-1] or 0)

    property_alloc = 0.0
    cash_alloc = 0.0
    shares_alloc = 0.0
    if not allocation.empty:
        lookup = allocation.set_index("Asset class")
        property_alloc = float(lookup["Current allocation"].get("Property equity", 0) or 0)
        cash_alloc = float(lookup["Current allocation"].get("Cash / offsets", 0) or 0)
        shares_alloc = float(lookup["Current allocation"].get("Shares", 0) or 0)

    open_items = 0
    if not decisions.empty and "Approval status" in decisions:
        closed = decisions["Approval status"].astype(str).str.lower().isin(["closed", "clarified by rodney", "implemented", "executed"])
        open_items = int((~closed).sum())

    evidence_gaps = 0
    if not evidence.empty and "Status" in evidence:
        evidence_gaps = int(evidence["Status"].astype(str).str.lower().str.contains("missing|partial|open|ongoing", na=False).sum())

    price_status = "Strong"
    if not sources.empty and "Provenance status" in sources:
        statuses = sources["Provenance status"].astype(str)
        fallback_count = int(statuses.str.contains("fallback", na=False).sum())
        stale_count = int(statuses.str.contains("stale", na=False).sum())
        if fallback_count or stale_count:
            price_status = f"{fallback_count} fallback / {stale_count} stale"

    return pd.DataFrame(
        [
            {
                "Mandate": "Grow net worth",
                "Read": f"{_money(metrics.get('monthly_delta', 0))} MoM",
                "Quality": _pct(mom_pct),
                "Action": "Review drivers before deploying capital",
            },
            {
                "Mandate": "Protect liquidity",
                "Read": _pct(cash_alloc),
                "Quality": "Protected offset-equivalent cash",
                "Action": "Do not treat current cash as freely deployable",
            },
            {
                "Mandate": "Control concentration",
                "Read": _pct(property_alloc),
                "Quality": "Property-led balance sheet",
                "Action": "Deploy new surplus with concentration discipline",
            },
            {
                "Mandate": "Build listed exposure",
                "Read": _pct(shares_alloc),
                "Quality": "Below policy base",
                "Action": "Use monthly surplus rule, not ad hoc trades",
            },
            {
                "Mandate": "Trust the data",
                "Read": price_status,
                "Quality": f"{evidence_gaps} evidence gaps",
                "Action": f"Clear {open_items} governance items before major moves",
            },
        ]
    )


def monthly_attribution() -> pd.DataFrame:
    changes = monthly_change_view()
    if changes.empty or len(changes) < 2:
        return pd.DataFrame()

    latest = changes.iloc[-1]
    prior = changes.iloc[-2]
    rows = []
    drivers = [
        ("Cash / offsets", "Cash / offsets MoM", "Liquidity and offset movement"),
        ("Property equity", "Property equity MoM", "Debt amortisation and property equity movement"),
        ("Crypto", "Crypto MoM", "BTC / crypto mark-to-market"),
        ("Shares", "Shares MoM", "Listed portfolio movement"),
        ("Super", "Super MoM", "Retirement bucket"),
        ("Debt reduction", "Debt reduction", "Positive means total debt fell"),
    ]
    for name, col, note in drivers:
        if col not in changes:
            continue
        value = float(latest.get(col, 0) or 0)
        prior_value = float(prior.get(col, 0) or 0)
        rows.append(
            {
                "Driver": name,
                "This month": value,
                "Prior month": prior_value,
                "Swing": value - prior_value,
                "Direction": "Positive" if value > 0 else "Negative" if value < 0 else "Flat",
                "Read": note,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["Absolute impact"] = frame["This month"].abs()
    return frame.sort_values("Absolute impact", ascending=False).drop(columns=["Absolute impact"]).reset_index(drop=True)


def banker_signals() -> list[Signal]:
    metrics = summary_metrics()
    allocation = allocation_view()
    attribution = monthly_attribution()
    risks = risk_summary()
    sources = price_source_view()
    evidence = read_table("evidence_register")
    decisions = read_table("decision_log")

    signals: list[Signal] = []

    if not attribution.empty:
        top = attribution.iloc[0]
        signals.append(
            Signal(
                "Dominant monthly driver",
                str(top["Direction"]),
                f"{top['Driver']} contributed {_money(float(top['This month']))}; swing versus prior month was {_money(float(top['Swing']))}.",
                "Review",
            )
        )

    if not allocation.empty:
        alloc = allocation.set_index("Asset class")
        property_alloc = float(alloc["Current allocation"].get("Property equity", 0) or 0)
        shares_alloc = float(alloc["Current allocation"].get("Shares", 0) or 0)
        cash_alloc = float(alloc["Current allocation"].get("Cash / offsets", 0) or 0)
        if property_alloc > 0.50:
            signals.append(
                Signal(
                    "Concentration control",
                    "Property-led",
                    f"Property equity is {_pct(property_alloc)} of net worth. New deployment should reduce dependence on property rather than add correlated risk.",
                    "High",
                )
            )
        if shares_alloc < 0.15:
            signals.append(
                Signal(
                    "Listed exposure gap",
                    "Under policy",
                    f"Listed shares are {_pct(shares_alloc)} versus a 15.0% base policy. The workbook points to staged monthly surplus deployment.",
                    "Medium",
                )
            )
        if cash_alloc > 0.20:
            signals.append(
                Signal(
                    "Liquidity posture",
                    "Protected",
                    f"Cash and offsets are {_pct(cash_alloc)} of net worth. The cockpit should keep this treated as protected liquidity unless Rodney approves otherwise.",
                    "Guardrail",
                )
            )

    if not risks.empty:
        watch = risks[risks["Status"].astype(str).str.lower().isin(["watch", "concentrated", "underweight"])]
        if not watch.empty:
            signals.append(
                Signal(
                    "Risk dashboard",
                    "Watchlist",
                    f"{len(watch)} workbook risk metrics need watch status review: {', '.join(watch['Metric'].astype(str).head(3).tolist())}.",
                    "Review",
                )
            )

    if not sources.empty and "Provenance status" in sources:
        statuses = sources["Provenance status"].astype(str)
        fallback = int(statuses.str.contains("fallback", na=False).sum())
        stale = int(statuses.str.contains("stale", na=False).sum())
        if fallback or stale:
            signals.append(
                Signal(
                    "Market data confidence",
                    "Mixed",
                    f"{fallback} price rows use workbook fallback and {stale} use stale cache. Keep source timestamps visible before relying on live marks.",
                    "Data",
                )
            )

    open_decisions = 0
    if not decisions.empty and "Approval status" in decisions:
        closed = decisions["Approval status"].astype(str).str.lower().isin(["closed", "clarified by rodney", "implemented", "executed"])
        open_decisions = int((~closed).sum())
    missing_evidence = 0
    if not evidence.empty and "Status" in evidence:
        missing_evidence = int(evidence["Status"].astype(str).str.lower().str.contains("missing|partial|open|ongoing", na=False).sum())
    if open_decisions or missing_evidence:
        signals.append(
            Signal(
                "Governance queue",
                "Open",
                f"{open_decisions} decision items and {missing_evidence} evidence/control items remain open before this becomes an institutional-grade operating file.",
                "High",
            )
        )

    if not signals:
        signals.append(Signal("Control read", "Clean", f"Net worth is {_money(metrics.get('net_worth', 0))}. No urgent control exceptions detected.", "Review"))
    return signals[:6]


def portfolio_watchlist() -> pd.DataFrame:
    holdings = holdings_with_live_prices()
    if holdings.empty:
        return pd.DataFrame()
    frame = holdings.copy()
    frame["Live value AUD"] = numeric(frame["Live value AUD"])
    frame["Live P/L AUD"] = numeric(frame["Live P/L AUD"])
    total = float(frame["Live value AUD"].sum() or 0)
    frame["Weight"] = frame["Live value AUD"] / total if total else 0
    frame["P/L %"] = frame["Live P/L AUD"] / frame["Cost base AUD"].replace(0, pd.NA)
    frame["Confidence"] = frame["Provenance status"].map(
        {
            "public_price_used": "Public timestamped",
            "stale_cache_price_used": "Stale cache",
            "workbook_fallback_public_outside_tolerance": "Workbook fallback",
            "workbook_fallback_no_public_price": "Workbook fallback",
            "workbook_fallback_no_shares": "Workbook fallback",
        }
    ).fillna("Review")
    cols = [
        "Ticker",
        "Instrument",
        "Currency",
        "Weight",
        "Live value AUD",
        "Live P/L AUD",
        "P/L %",
        "Price basis",
        "Tolerance check",
        "Confidence",
    ]
    return frame[cols].sort_values("Live value AUD", ascending=False).reset_index(drop=True)


def workbook_coverage() -> pd.DataFrame:
    index = read_table("workbook_sheet_index")
    if index.empty:
        return pd.DataFrame()
    frame = index.copy()
    for col in ["Rows", "Columns", "Formula cells", "Populated cells"]:
        if col in frame:
            frame[col] = numeric(frame[col])
    frame["Coverage"] = frame.apply(lambda row: f"{int(row.get('Rows', 0))} x {int(row.get('Columns', 0))}", axis=1)
    if "Formula cells" in frame:
        frame["Model depth"] = frame["Formula cells"].map(lambda value: "Formula model" if float(value or 0) else "Static table")
    else:
        frame["Model depth"] = "Imported"
    return frame[["Sheet", "Coverage", "Model depth", "Table"]]


def property_debt_snapshot() -> pd.DataFrame:
    props = read_table("property_register")
    if props.empty:
        return pd.DataFrame()
    frame = props.copy()
    for col in ["Value", "Loan", "Offset", "Annual rent"]:
        if col in frame:
            frame[col] = numeric(frame[col])
    frame["Net debt after offset"] = frame["Loan"] - frame["Offset"]
    frame["Gross LVR"] = frame["Loan"] / frame["Value"].replace(0, pd.NA)
    frame["Net LVR"] = frame["Net debt after offset"] / frame["Value"].replace(0, pd.NA)
    frame["Gross yield"] = frame["Annual rent"] / frame["Value"].replace(0, pd.NA)
    cols = ["Property", "Value", "Loan", "Offset", "Net debt after offset", "Gross LVR", "Net LVR", "Annual rent", "Gross yield", "Owner/entity"]
    return frame[[col for col in cols if col in frame.columns]]


def update_checklist() -> pd.DataFrame:
    evidence = read_table("evidence_register")
    decisions = read_table("decision_log")
    rows = [
        {"Step": "Monthly balance", "Owner": "Kobe", "Status": "Ready", "Why it matters": "Updates net worth, debt, liquidity and driver attribution"},
        {"Step": "Market tape", "Owner": "Kobe", "Status": "Ready", "Why it matters": "Refreshes listed holdings and source timestamps"},
        {"Step": "Workbook import", "Owner": "Kobe", "Status": "Ready", "Why it matters": "Keeps all 25 workbook sheets available in the vault"},
    ]
    if not evidence.empty and "Status" in evidence:
        gaps = int(evidence["Status"].astype(str).str.lower().str.contains("missing|partial|open|ongoing", na=False).sum())
        rows.append({"Step": "Evidence gaps", "Owner": "Kobe / Dan", "Status": f"{gaps} open", "Why it matters": "Stops the app overstating confidence"})
    if not decisions.empty and "Approval status" in decisions:
        closed = decisions["Approval status"].astype(str).str.lower().isin(["closed", "clarified by rodney", "implemented", "executed"])
        rows.append({"Step": "Decision queue", "Owner": "Rodney", "Status": f"{int((~closed).sum())} open", "Why it matters": "No moves without explicit approval"})
    cache = read_price_cache()
    rows.append({"Step": "Last market refresh", "Owner": "System", "Status": str(cache.get("updated_at") or "Not refreshed"), "Why it matters": "Shows whether prices are current or cached"})
    return pd.DataFrame(rows)
