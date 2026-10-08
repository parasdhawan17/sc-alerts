#!/usr/bin/env python3
"""Sync SC and DBS transaction emails for a selected month to Google Sheets."""
import _bootstrap  # noqa: F401
import argparse
from datetime import date
from sc_alerts.month_sync import DEFAULT_SPREADSHEET_ID, parse_month, sync_month
from sc_alerts.month_sync import fetch_month_transactions as _fetch
from sc_alerts.google_auth import get_gmail_service, get_sheets_service
from sc_alerts.sheet_manager import get_spreadsheet, write_month_sheet


def fetch_month_transactions(gmail, selected_month):
    return _fetch(gmail, selected_month, emit=lambda **event: print(event["message"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", type=parse_month, metavar="YYYY-MM")
    parser.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    transactions = sync_month(
        args.month or date.today().replace(day=1), args.spreadsheet_id,
        emit=lambda **event: print(event["message"]),
        gmail_factory=get_gmail_service, sheets_factory=get_sheets_service,
        fetch=fetch_month_transactions, spreadsheet_reader=get_spreadsheet,
        writer=write_month_sheet, dry_run=args.dry_run)
    if args.dry_run:
        print("Dry run enabled — not writing to the sheet.")
        for txn in transactions:
            print(f"  {txn['transaction_date']} | {txn.get('bank', 'Unknown')} | {txn['merchant']} | {txn['amount']:.2f} SGD")


if __name__ == "__main__":
    main()
