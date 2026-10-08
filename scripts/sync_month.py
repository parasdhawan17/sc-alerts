#!/usr/bin/env python3
"""Sync SC and DBS transaction emails for a selected month to Google Sheets."""

import _bootstrap  # noqa: F401

import argparse
import re
from datetime import date

from sc_alerts.email_utils import get_message
from sc_alerts.gmail_sync import list_messages, month_query
from sc_alerts.google_auth import get_gmail_service, get_sheets_service
from sc_alerts.sheet_manager import get_spreadsheet, sheet_map, write_month_sheet
from sc_alerts.transaction_parser import parse_transaction_message

DEFAULT_SPREADSHEET_ID = "1fD1qL3GjtEanxnL0MvwByauKz3xe2MthMndNL3E14cg"


def parse_month(value: str) -> date:
    """Validate YYYY-MM before opening a Google connection."""
    if re.fullmatch(r"\d{4}-\d{2}", value):
        try:
            year, month = map(int, value.split("-"))
            return date(year, month, 1)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("Month must be a valid YYYY-MM value, such as 2026-09")


def fetch_month_transactions(gmail, selected_month: date) -> list[dict]:
    query = month_query(selected_month.year, selected_month.month)
    print(f"Fetching emails with query: {query}")

    message_refs = list_messages(gmail, query)
    print(f"Found {len(message_refs)} email(s)")

    transactions: list[dict] = []
    skipped = 0
    for index, ref in enumerate(message_refs, start=1):
        message = get_message(gmail, ref["id"])
        transaction = parse_transaction_message(message)
        if transaction:
            transactions.append(transaction)
        else:
            skipped += 1

        if index % 50 == 0:
            print(f"  Processed {index}/{len(message_refs)} emails...")

    print(f"Parsed {len(transactions)} transaction(s), skipped {skipped}")
    return transactions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync SC and DBS transactions for a selected month from Gmail to Google Sheets."
    )
    parser.add_argument(
        "--month",
        type=parse_month,
        metavar="YYYY-MM",
        help="Month to sync, for example 2026-09 (default: current month)",
    )
    parser.add_argument(
        "--spreadsheet-id",
        default=DEFAULT_SPREADSHEET_ID,
        help="Target Google Spreadsheet ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print transactions without writing to the sheet",
    )
    args = parser.parse_args()

    selected_month = args.month or date.today().replace(day=1)
    month_name = selected_month.strftime("%b %Y")
    year_month = f"{selected_month.year:04d}-{selected_month.month:02d}"

    gmail = get_gmail_service()
    transactions = fetch_month_transactions(gmail, selected_month)

    if not transactions:
        print("No transactions to sync.")
        return

    # Gmail searches by email date; keep only transactions dated in the selected month.
    month_transactions = [
        txn for txn in transactions if txn.get("transaction_date", "").startswith(year_month + "-")
    ]

    if not month_transactions:
        print(f"No transactions found for {month_name}.")
        return

    print(f"\nTransactions to sync for {month_name}: {len(month_transactions)}")

    if args.dry_run:
        print("Dry run enabled — not writing to the sheet.")
        for txn in month_transactions:
            print(f"  {txn['transaction_date']} | {txn.get('bank', 'Unknown')} | {txn['merchant']} | {txn['amount']:.2f} SGD")
        return

    sheets = get_sheets_service()
    spreadsheet = get_spreadsheet(sheets, args.spreadsheet_id)
    titles_to_ids = sheet_map(spreadsheet)

    write_month_sheet(sheets, args.spreadsheet_id, month_name, month_transactions, titles_to_ids)
    print(f"\nDone. Synced {len(month_transactions)} transaction(s) to '{month_name}'.")


if __name__ == "__main__":
    main()
