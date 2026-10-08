# sc-alerts

Read Standard Chartered Singapore transaction alert emails from Gmail (`alerts.sg@sc.com`) and extract transaction details.

## What it does

1. **Fetches alert emails** from Gmail — messages from `alerts.sg@sc.com` (and DBS alerts).
2. **Parses transaction details** — amount, currency, account, date/time, description, and debit/credit type when present.
3. **Prints results** — human-readable output, raw email previews, or JSON.
4. **Syncs to Google Sheets** — groups transactions by merchant per month and updates a spend-by-category breakdown.

## Prerequisites

- Python 3.10+
- A Google Cloud project with **Gmail API** and **Google Sheets API** enabled
- OAuth 2.0 desktop credentials (`credentials.json`)

## Setup

```bash
cd /Users/parasdhawan/Documents/Projects/sc-alerts
pip install -r requirements.txt
```

1. Download OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/) (Desktop app type) and save as `credentials.json` in the project root.
   - You can reuse the same `credentials.json` from `mytrader` if Gmail API is already enabled.
2. Run the script — a browser window opens for Google OAuth on first run. The token is saved to `token.json`.

## Project structure

```
sc-alerts/
├── scripts/
│   ├── read_sc_transactions.py   # Read and print transactions
│   ├── sync_month.py     # Sync a selected month (defaults to current month)
│   ├── sync_to_sheet.py          # Sync full year to Google Sheets
│   └── update_categories.py      # Update category breakdowns in sheets
├── sc_alerts/
│   ├── google_auth.py            # Gmail / Sheets OAuth
│   ├── gmail_sync.py             # Gmail search queries
│   ├── email_utils.py            # Message decoding helpers
│   ├── sc_parser.py              # Transaction email parser
│   ├── sheet_manager.py          # Google Sheet writing and formatting
│   └── paths.py
├── credentials.json              # local only (not in git)
├── token.json
└── requirements.txt
```

## Usage

```bash
# Read the latest 20 SC transaction alerts
python scripts/read_sc_transactions.py

# Fetch more emails
python scripts/read_sc_transactions.py --max-results 50

# Only current month
python scripts/read_sc_transactions.py --current-month

# A specific month
python scripts/read_sc_transactions.py --month 2026-05

# Raw email previews (useful for tuning the parser)
python scripts/read_sc_transactions.py --raw --max-results 5

# Parsed output as JSON
python scripts/read_sc_transactions.py --json
```

## Sync to Google Sheets

```bash
# Sync current month to the default spreadsheet
python scripts/sync_month.py

# Sync any month using YYYY-MM
python scripts/sync_month.py --month 2026-09
python scripts/sync_month.py --month 2026-10

# Sync to a different spreadsheet
python scripts/sync_month.py --spreadsheet-id YOUR_SHEET_ID

# Preview what would be synced without writing
python scripts/sync_month.py --dry-run

# Preview a selected month
python scripts/sync_month.py --month 2026-09 --dry-run
```

`sync_month.py` accepts `--month YYYY-MM` for any year and month, or defaults to the current month when omitted. It fetches transaction emails for that month, parses them, keeps transactions dated in the selected month, groups them by merchant, and writes them to the matching sheet tab (for example, `Sep 2026`). Rerunning the command refreshes the tab without duplicating transactions. It also refreshes the spend-by-category breakdown and chart. Existing Include/Exclude choices and category overrides are preserved for merchants that are already in the sheet. Invalid month values are rejected before connecting to Google.

## Parser notes

SC alert emails can vary by transaction type (PayNow, FAST, card, ATM, etc.). The parser looks for common field labels and falls back to inline amount/currency detection. If some emails are not parsed, run with `--raw` to inspect the body format and update patterns in `sc_alerts/sc_parser.py`.
