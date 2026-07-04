#!/usr/bin/env python3
"""Sync 2026 SC and DBS transaction emails to a Google Sheet grouped by merchant per month."""

import _bootstrap  # noqa: F401

import argparse
from collections import defaultdict

from sc_alerts.email_utils import get_message
from sc_alerts.gmail_sync import list_messages, year_query
from sc_alerts.google_auth import get_gmail_service, get_sheets_service
from sc_alerts.transaction_parser import parse_transaction_message
from sc_alerts.sheet_manager import month_sort_key, sync_transactions_to_sheet

DEFAULT_SPREADSHEET_ID = "1fD1qL3GjtEanxnL0MvwByauKz3xe2MthMndNL3E14cg"
DEFAULT_YEAR = 2026


def fetch_transactions_for_year(gmail, year: int) -> list[dict]:
    query = year_query(year)
    print(f"Fetching emails with query: {query}")

    message_refs = list_messages(gmail, query)
    print(f"Found {len(message_refs)} email(s)")

    transactions: list[dict] = []
    skipped = 0
    for index, ref in enumerate(message_refs, start=1):
        message = get_message(gmail, ref["id"])
        transaction = parse_transaction_message(message)
        if transaction and transaction["transaction_date"].startswith(str(year)):
            transactions.append(transaction)
        else:
            skipped += 1

        if index % 50 == 0:
            print(f"  Processed {index}/{len(message_refs)} emails...")

    by_bank: dict[str, int] = defaultdict(int)
    for txn in transactions:
        by_bank[txn.get("bank", "Unknown")] += 1

    print(f"Parsed {len(transactions)} transaction(s), skipped {skipped}")
    for bank, count in sorted(by_bank.items()):
        print(f"  {bank}: {count}")
    return transactions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync SC and DBS transaction emails to Google Sheets grouped by merchant."
    )
    parser.add_argument(
        "--spreadsheet-id",
        default=DEFAULT_SPREADSHEET_ID,
        help="Target Google Spreadsheet ID",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_YEAR,
        help="Year to sync (default: 2026)",
    )
    args = parser.parse_args()

    gmail = get_gmail_service()
    sheets = get_sheets_service()

    transactions = fetch_transactions_for_year(gmail, args.year)
    if not transactions:
        print("No transactions to sync.")
        return

    by_month: dict[str, int] = defaultdict(int)
    for txn in transactions:
        by_month[txn["month"]] += 1

    print("\nTransactions by month:")
    for month_name in sorted(by_month, key=month_sort_key):
        print(f"  {month_name}: {by_month[month_name]}")

    print(f"\nWriting to spreadsheet {args.spreadsheet_id}...")
    summary = sync_transactions_to_sheet(
        sheets, args.spreadsheet_id, transactions, year=args.year
    )

    print("\nDone. Updated sheets:")
    for month_name, count in sorted(summary.items(), key=lambda item: month_sort_key(item[0])):
        print(f"  {month_name}: {count} transaction(s)")


if __name__ == "__main__":
    main()
