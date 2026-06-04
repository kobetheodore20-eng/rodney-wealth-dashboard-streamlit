# Rodney Wealth Cockpit

A Streamlit deployment shell for the Rodney Wealth Cockpit. This public repository contains app code only; the wealth-data snapshot is supplied at runtime through encrypted Streamlit secrets.

## What It Does

- Imports the existing Drive-synced Excel workbook into editable CSV tables.
- Shows an executive wealth dashboard, monthly movement, properties, listed holdings, decisions, evidence, and update workflow.
- Refreshes listed share/ETF prices and USD/AUD FX from public market endpoints when requested.
- Keeps updates simple: Kobe can re-import the workbook locally, or Rodney can add a monthly tracking row inside the app.

## Run It

```bash
cd "/Users/kobetheodore/Documents/Rodney Wealth Cockpit App"
"/Users/kobetheodore/Documents/Supplier Submission Assistant/.venv/bin/python" scripts/import_workbook.py
"/Users/kobetheodore/Documents/Supplier Submission Assistant/.venv/bin/streamlit" run app.py --server.port 8520
```

Then open:

[http://localhost:8520](http://localhost:8520)

## Deploy It

Deploy as a private Streamlit app.

- Repository: private GitHub repository recommended.
- Main file path: `app.py`
- Python dependencies: `requirements.txt`
- Data model: encrypted `DATA_BUNDLE_B64` secret
- Market refresh: uses Yahoo Finance chart metadata and open.er-api.com at runtime.
- Secrets: set `APP_PASSWORD` before sharing the app URL.

Do not commit wealth CSVs or workbook exports to this repository.

## Update The Workbook Snapshot

```bash
export WEALTH_COCKPIT_WORKBOOK="/path/to/Rodney Wealth Cockpit.xlsx"
python scripts/import_workbook.py
```

Commit the refreshed `data/*.csv` files after Kobe has reviewed them.

## Important Boundary

This app is for financial tracking, evidence, and decision support only. It is not financial, tax, or legal advice. No trades, refinancing, capital movement, or third-party instructions should be taken without Rodney's explicit approval.
