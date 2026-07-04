#!/usr/bin/env python3
"""Read current-month SC and DBS transaction emails and sync them to Google Sheets."""

import _bootstrap  # noqa: F401

import argparse
from datetime import date

from sc_alerts.email_utils import get_message
from sc_alerts.gmail_sync import current_month_query, list_messages
from sc_alerts.google_auth import get_gmail_service, get_sheets_service
from sc_alerts.sheet_manager import get_spreadsheet, sheet_map, write_month_sheet
from sc_alerts.transaction_parser import parse_transaction_message

DEFAULT_SPREADSHEET_ID = "1fD1qL3GjtEanxnL0MvwByauKz3xe2MthMndNL3E14cg"


def fetch_current_month_transactions(gmail) -> list[dict]:
    query = current_month_query()
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
        description="Sync current-month SC and DBS transactions from Gmail to Google Sheets."
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

    today = date.today()
    current_month_name = today.strftime("%b %Y")
    current_year_month = today.strftime("%Y-%m")

    gmail = get_gmail_service()
    transactions = fetch_current_month_transactions(gmail)

    if not transactions:
        print("No transactions to sync.")
        return

    # Keep only transactions whose transaction_date falls in the current month.
    month_transactions = [
        txn for txn in transactions if txn.get("transaction_date", "").startswith(current_year_month)
    ]

    if not month_transactions:
        print(f"No transactions found for {current_month_name}.")
        return

    print(f"\nTransactions to sync for {current_month_name}: {len(month_transactions)}")

    if args.dry_run:
        print("Dry run enabled — not writing to the sheet.")
        for txn in month_transactions:
            print(f"  {txn['transaction_date']} | {txn.get('bank', 'Unknown')} | {txn['merchant']} | {txn['amount']:.2f} SGD")
        return

    sheets = get_sheets_service()
    spreadsheet = get_spreadsheet(sheets, args.spreadsheet_id)
    titles_to_ids = sheet_map(spreadsheet)

    write_month_sheet(sheets, args.spreadsheet_id, current_month_name, month_transactions, titles_to_ids)
    print(f"\nDone. Synced {len(month_transactions)} transaction(s) to '{current_month_name}'.")


if __name__ == "__main__":
    main()
