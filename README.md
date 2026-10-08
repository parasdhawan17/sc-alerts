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

## Native Mac app

The SwiftUI app is a small, single-window monthly sync utility. Choose a calendar
month and click **Sync [month]** (⌘Return). It refreshes the existing monthly tab,
including category summaries and charts, while preserving merchant choices.
No transactions means no sheet changes. The current month syncs alerts available
so far; the app does not schedule syncs or expose the full-year command.

### Build

Requires macOS, Xcode Command Line Tools (or Xcode), Python 3.10+, and `uv`.
The bundled app needs no separate Python installation. The checked-in dependency
versions were verified using Python 3.14.6 on Apple Silicon; builds target the
build machine's architecture. The frontend targets macOS 13+, but the bundled
Python/runtime must also support the destination OS; this build was tested on
macOS 27.2 only.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r macos/requirements-build.txt
macos/build.sh
open "dist/SC Alerts.app"
```

If `.venv` already exists, keep it and run the install/build commands. Set
`SC_ALERTS_BUILD_PYTHON` to use another build environment. The build script bundles
the backend with PyInstaller, compiles SwiftUI, then ad-hoc signs and verifies
`dist/SC Alerts.app`. You can move this app to Applications. It is a local build,
not notarized for public distribution.

### First use

1. Open **Settings** (⌘,) and import your Google **Desktop app** OAuth JSON
   credentials. Enable Gmail and Google Sheets APIs in that Google Cloud project.
2. Confirm the destination spreadsheet ID. The existing project's spreadsheet is
   prefilled. The connected Google account must have edit access to it.
3. Click **Done**, choose the month/year, and click **Sync**. Google opens in your
   browser when sign-in is required; finish sign-in within three minutes.
4. Watch progress, then click **Open Google Sheet**. Failures remain visible and
   allow retry. If a write failed, some updates may already have reached Sheets;
   rerun the full month to refresh it.

The app stores `credentials.json`, `token.json`, and `preferences.json` in
`~/Library/Application Support/SC Alerts/`, outside the application bundle.
Credentials and tokens are never bundled. Importing replacement credentials
removes the app's old token so the next sync signs in again. Existing CLI scripts
continue using the project-root credential and token files.

### Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests use mocks and do not connect to Gmail or modify Sheets. Real write testing
should use a separate test spreadsheet configured through Settings. Check a
second sync retains merchant Include/Exclude and category overrides.
