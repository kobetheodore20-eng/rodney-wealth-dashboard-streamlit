from __future__ import annotations

import pandas as pd


BALANCE_SHEET_MONTHLY_MAP = {
    "Cash / offsets": "Cash / offsets",
    "Property equity": "Property equity",
    "Crypto": "Crypto",
    "Shares": "Shares",
    "Super": "Super",
    "TOTAL DEBT": "Total debt",
    "TOTAL ASSETS": "Total assets",
    "NET DEBT": "Net debt",
    "NET WORTH": "Net worth",
}


def build_monthly_update_frame(monthly: pd.DataFrame, new_row: dict[str, object]) -> pd.DataFrame:
    frame = monthly[monthly["Date"].astype(str) != str(new_row["Date"])].copy()
    frame = pd.concat([frame, pd.DataFrame([new_row])], ignore_index=True)
    frame["Date"] = frame["Date"].astype(str)
    try:
        frame = frame.sort_values("Date", kind="stable").reset_index(drop=True)
    except TypeError:
        frame = frame.reset_index(drop=True)

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
            frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

    for col in numeric_cols:
        delta_col = f"{col} MoM"
        if col in frame and (delta_col in frame.columns or delta_col in monthly.columns):
            frame[delta_col] = frame[col].diff()

    legacy_delta_map = {
        "Cash Δ": "Cash / offsets",
        "Equity Δ": "Property equity",
        "Crypto Δ": "Crypto",
        "Shares Δ": "Shares",
        "Super Δ": "Super",
        "Debt Δ": "Total debt",
        "Net worth Δ": "Net worth",
    }
    for delta_col, source_col in legacy_delta_map.items():
        if source_col in frame and (delta_col in frame.columns or delta_col in monthly.columns):
            delta = frame[source_col].diff()
            frame[delta_col] = -delta if delta_col == "Debt Δ" else delta

    if "Net worth" in frame and ("Net worth MoM %" in frame.columns or "Net worth MoM %" in monthly.columns):
        frame["Net worth MoM %"] = frame["Net worth"].pct_change().fillna(0)
    if "Total debt MoM" in frame and ("Debt reduction" in frame.columns or "Debt reduction" in monthly.columns):
        frame["Debt reduction"] = -frame["Total debt MoM"]
    return frame


def normalize_monthly_property_base(monthly: pd.DataFrame, property_register: pd.DataFrame) -> pd.DataFrame:
    """Restate monthly history to the current property value base.

    When management property values are refreshed, that valuation change should
    not appear as a one-month wealth movement unless the monthly history is
    deliberately a point-in-time valuation ledger. Rodney's cockpit uses the
    current management property base as a consistent baseline, then tracks
    month-on-month movement from cash, listed marks, crypto, debt and super.
    """
    if monthly.empty or property_register.empty:
        return monthly.copy()
    if "Property value" not in monthly.columns or "Value" not in property_register.columns:
        return monthly.copy()

    frame = monthly.copy()
    property_values = pd.to_numeric(property_register["Value"], errors="coerce")
    property_base = float(property_values.dropna().sum())
    if not property_base:
        return frame

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
            frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)

    frame["Property value"] = property_base
    if "Total debt" in frame:
        frame["Property equity"] = frame["Property value"] - frame["Total debt"]
    component_cols = [col for col in ["Cash / offsets", "Property value", "Crypto", "Shares", "Super"] if col in frame]
    if component_cols:
        frame["Total assets"] = frame[component_cols].sum(axis=1)
    if {"Total assets", "Total debt"}.issubset(frame.columns):
        frame["Net worth"] = frame["Total assets"] - frame["Total debt"]
    if {"Total debt", "Cash / offsets"}.issubset(frame.columns):
        frame["Net debt"] = frame["Total debt"] - frame["Cash / offsets"]

    return _recalculate_monthly_deltas(frame)


def _recalculate_monthly_deltas(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if "Date" in frame:
        frame["Date"] = frame["Date"].astype(str)
        frame = frame.sort_values("Date", kind="stable").reset_index(drop=True)

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
            frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)
            frame[f"{col} MoM"] = frame[col].diff()

    legacy_delta_map = {
        "Cash Δ": "Cash / offsets",
        "Equity Δ": "Property equity",
        "Crypto Δ": "Crypto",
        "Shares Δ": "Shares",
        "Super Δ": "Super",
        "Debt Δ": "Total debt",
        "Net worth Δ": "Net worth",
    }
    for delta_col, source_col in legacy_delta_map.items():
        if source_col in frame:
            delta = frame[source_col].diff()
            frame[delta_col] = -delta if delta_col == "Debt Δ" else delta

    if "Net worth" in frame:
        frame["Net worth MoM %"] = frame["Net worth"].pct_change().fillna(0)
    if "Total debt MoM" in frame:
        frame["Debt reduction"] = -frame["Total debt MoM"]
    return frame


def apply_monthly_row_to_balance_sheet(balance: pd.DataFrame, monthly_row: dict[str, object]) -> pd.DataFrame:
    """Update balance-sheet headline rows from the same row written to monthly tracking.

    Local monthly updates must not create a split-brain cockpit where the topline
    net worth changes but allocation/risk still read stale balance-sheet rows.
    """
    if balance.empty:
        return balance.copy()
    if "Asset class" not in balance.columns:
        raise ValueError("balance_sheet needs an Asset class column for atomic monthly updates")
    frame = balance.copy()
    if "Current value" not in frame.columns:
        frame["Current value"] = pd.NA
    if "Notes" not in frame.columns:
        frame["Notes"] = ""

    for asset_class, monthly_key in BALANCE_SHEET_MONTHLY_MAP.items():
        if monthly_key not in monthly_row:
            continue
        mask = frame["Asset class"].astype(str).eq(asset_class)
        if not mask.any():
            frame = pd.concat(
                [
                    frame,
                    pd.DataFrame(
                        [
                            {
                                "Asset class": asset_class,
                                "Current value": monthly_row[monthly_key],
                                "Notes": "Updated atomically from monthly update row",
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )
            continue
        frame.loc[mask, "Current value"] = monthly_row[monthly_key]
        frame.loc[mask, "Notes"] = "Updated atomically from monthly update row"
    return frame
