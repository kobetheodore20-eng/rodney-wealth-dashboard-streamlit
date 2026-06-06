from __future__ import annotations

from datetime import datetime, timezone
import re

import pandas as pd
import requests

from app.data_store import read_json, read_table, write_json
try:
    from app.config import PROPERTY_REFRESH_CACHE_PATH
except ImportError:  # Streamlit Cloud can briefly run mixed module versions during rebuild.
    from app.config import DATA_DIR

    PROPERTY_REFRESH_CACHE_PATH = DATA_DIR / "property_refresh_cache.json"


PROPERTY_SOURCE_URLS = {
    "25 Keith St": "https://www.property.com.au/nsw/earlwood-2206/keith-st/25-pid-906963/",
    "29 Christine Ave": "https://www.property.com.au/qld/torquay-4655/christine-ave/29-pid-12763597/",
    "54 Christine Ave": "https://www.property.com.au/qld/torquay-4655/christine-ave/54-pid-12763622/",
}


def _parse_property_value(html: str) -> float | None:
    text = re.sub(r"\s+", " ", html)
    patterns = [
        r"estimated property value of .*? is \$([0-9,.]+)(m|k)?",
        r"Property value .*?\$([0-9,.]+)(m|k)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        number = float(match.group(1).replace(",", ""))
        suffix = (match.group(2) or "").lower()
        if suffix == "m":
            number *= 1_000_000
        elif suffix == "k":
            number *= 1_000
        return number
    return None


def fetch_property_estimate(url: str) -> dict[str, object]:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 Rodney Wealth Cockpit"},
        timeout=12,
    )
    if response.status_code == 429:
        raise RuntimeError("Source blocked server-side request with HTTP 429")
    response.raise_for_status()
    value = _parse_property_value(response.text)
    if not value:
        raise ValueError("No structured estimate found in source response")
    return {
        "value": value,
        "source": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def refresh_property_estimates() -> dict[str, object]:
    props = read_table("property_register")
    cache = read_json(PROPERTY_REFRESH_CACHE_PATH, {"properties": {}, "updated_at": None})
    rows = []
    current_cache = cache.get("properties", {}) if isinstance(cache, dict) else {}

    for _, row in props.iterrows():
        name = str(row.get("Property", "")).strip()
        if not name or name.upper() == "TOTAL":
            continue
        current_value = pd.to_numeric(pd.Series([row.get("Value")]), errors="coerce").iloc[0]
        url = PROPERTY_SOURCE_URLS.get(name)
        result = {
            "Property": name,
            "Cockpit value": current_value,
            "Refreshed value": pd.NA,
            "Status": "No configured public source",
            "Source": "",
            "Fetched at": "",
            "Action": "Retained cockpit value",
        }
        if url:
            result["Source"] = url
            try:
                fetched = fetch_property_estimate(url)
                result["Refreshed value"] = fetched["value"]
                result["Status"] = "Public estimate refreshed"
                result["Fetched at"] = fetched["fetched_at"]
                result["Action"] = "Review before applying to workbook/bundle"
                current_cache[name] = fetched
            except Exception as exc:  # noqa: BLE001 - displayed in UI.
                result["Status"] = str(exc)
                previous = current_cache.get(name, {})
                if previous:
                    result["Refreshed value"] = previous.get("value", pd.NA)
                    result["Fetched at"] = previous.get("fetched_at", "")
                    result["Action"] = "Retained last cached/source value"
                else:
                    result["Action"] = "Retained cockpit value"
        rows.append(result)

    payload = {
        "properties": current_cache,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    write_json(PROPERTY_REFRESH_CACHE_PATH, payload)
    return payload


def property_refresh_view() -> pd.DataFrame:
    cache = read_json(PROPERTY_REFRESH_CACHE_PATH, {"rows": []})
    rows = cache.get("rows", []) if isinstance(cache, dict) else []
    if rows:
        return pd.DataFrame(rows)
    props = read_table("property_register")
    if props.empty:
        return pd.DataFrame()
    rows = []
    for _, row in props.iterrows():
        name = str(row.get("Property", "")).strip()
        if not name or name.upper() == "TOTAL":
            continue
        rows.append(
            {
                "Property": name,
                "Cockpit value": row.get("Value"),
                "Refreshed value": pd.NA,
                "Status": "Not refreshed this session",
                "Source": PROPERTY_SOURCE_URLS.get(name, ""),
                "Fetched at": "",
                "Action": "Retained cockpit value",
            }
        )
    return pd.DataFrame(rows)
