# sc-alerts

Read Standard Chartered Singapore transaction alert emails from Gmail (`alerts.sg@sc.com`) and extract transaction details.

## What it does

1. **Fetches alert emails** from Gmail — messages from `alerts.sg@sc.com`.
2. **Parses transaction details** — amount, currency, account, date/time, description, and debit/credit type when present.
3. **Prints results** — human-readable output, raw email previews, or JSON.

## Prerequisites

- Python 3.10+
- A Google Cloud project with **Gmail API** enabled
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
│   └── read_sc_transactions.py   # Main entry point
├── sc_alerts/
│   ├── google_auth.py            # Gmail OAuth
│   ├── gmail_sync.py             # Gmail search queries
│   ├── email_utils.py            # Message decoding helpers
│   ├── sc_parser.py              # Transaction email parser
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

## Parser notes

SC alert emails can vary by transaction type (PayNow, FAST, card, ATM, etc.). The parser looks for common field labels and falls back to inline amount/currency detection. If some emails are not parsed, run with `--raw` to inspect the body format and update patterns in `sc_alerts/sc_parser.py`.
