from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any
import zipfile

import pandas as pd
from pandas.errors import EmptyDataError
import streamlit as st

from app.config import DATA_DIR, ENCRYPTED_DATA_BUNDLE_PATH, PRICE_CACHE_PATH


def secret_data_bundle() -> zipfile.ZipFile | None:
    try:
        encoded = st.secrets.get("DATA_BUNDLE_B64")
    except Exception:  # noqa: BLE001 - secrets may be absent in local development.
        encoded = None
    encoded = os.environ.get("WEALTH_COCKPIT_DATA_BUNDLE_B64") or encoded
    if not encoded:
        return None
    payload = base64.b64decode(str(encoded))
    return zipfile.ZipFile(io.BytesIO(payload))


def encrypted_data_bundle() -> zipfile.ZipFile | None:
    if not ENCRYPTED_DATA_BUNDLE_PATH.exists():
        return None
    try:
        key = st.secrets.get("DATA_BUNDLE_KEY")
    except Exception:  # noqa: BLE001 - secrets may be absent in local development.
        key = None
    key = os.environ.get("WEALTH_COCKPIT_DATA_BUNDLE_KEY") or key
    if not key:
        return None

    from cryptography.fernet import Fernet

    payload = Fernet(str(key).encode("utf-8")).decrypt(ENCRYPTED_DATA_BUNDLE_PATH.read_bytes())
    return zipfile.ZipFile(io.BytesIO(payload))


def read_table(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if path.exists():
        try:
            return pd.read_csv(path)
        except EmptyDataError:
            return pd.DataFrame()

    bundle = secret_data_bundle() or encrypted_data_bundle()
    member = f"{name}.csv"
    if not bundle or member not in bundle.namelist():
        return pd.DataFrame()
    try:
        with bundle.open(member) as handle:
            return pd.read_csv(handle)
    except EmptyDataError:
        return pd.DataFrame()


def write_table(name: str, frame: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(DATA_DIR / f"{name}.csv", index=False)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def read_price_cache() -> dict[str, Any]:
    return read_json(PRICE_CACHE_PATH, {"prices": {}, "fx": {}, "updated_at": None})


def save_price_cache(cache: dict[str, Any]) -> None:
    write_json(PRICE_CACHE_PATH, cache)


def money(value: Any, currency: str = "A$") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if abs(number) >= 1_000_000:
        return f"{currency}{number / 1_000_000:,.2f}m"
    return f"{currency}{number:,.0f}"


def pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"
