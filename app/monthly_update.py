from __future__ import annotations

import pandas as pd


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
