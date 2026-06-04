from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_SOURCE_WORKBOOK = PROJECT_ROOT / "Rodney Wealth Cockpit.xlsx"
SOURCE_WORKBOOK = Path(os.environ.get("WEALTH_COCKPIT_WORKBOOK", DEFAULT_SOURCE_WORKBOOK))
SOURCE_WORKBOOK_LABEL = os.environ.get(
    "WEALTH_COCKPIT_SOURCE_LABEL",
    "Rodney Wealth Cockpit workbook snapshot",
)

PRICE_CACHE_PATH = DATA_DIR / "prices_cache.json"

AUTHORITY_BOUNDARY = (
    "Tracking and decision support only. Not financial, tax, or legal advice. "
    "No trades, refinancing, capital movement, broker/adviser contact, or third-party "
    "instructions without Rodney's explicit approval."
)
