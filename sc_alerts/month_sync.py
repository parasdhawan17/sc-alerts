"""Shared monthly sync flow, independent of its CLI or desktop presentation."""
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
    if re.fullmatch(r"\d{4}-\d{2}", value):
        try:
            year, month = map(int, value.split("-"))
            # Query construction needs the following month to be representable.
            if (year, month) != (9999, 12):
                return date(year, month, 1)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("Month must be a valid YYYY-MM value, such as 2026-09")


def fetch_month_transactions(gmail, selected_month: date, emit=lambda **event: None) -> list[dict]:
    emit(stage="fetching", message="Finding SC and DBS alerts…")
    refs = list_messages(gmail, month_query(selected_month.year, selected_month.month))
    transactions = []
    skipped = 0
    emit(stage="parsing", processed=0, total=len(refs), message=f"Reading {len(refs)} emails…")
    for index, ref in enumerate(refs, 1):
        txn = parse_transaction_message(get_message(gmail, ref["id"]))
        if txn:
            transactions.append(txn)
        else:
            skipped += 1
        emit(stage="parsing", processed=index, total=len(refs), skipped=skipped,
             message=f"Read {index} of {len(refs)} emails")
    return transactions


def sync_month(selected_month, spreadsheet_id, emit=lambda **event: None, *,
               gmail_factory=get_gmail_service, sheets_factory=get_sheets_service,
               fetch=fetch_month_transactions, spreadsheet_reader=get_spreadsheet,
               writer=write_month_sheet, dry_run=False):
    emit(stage="authentication", message="Connecting to Google… Sign in in your browser if prompted.")
    gmail = gmail_factory()
    transactions = fetch(gmail, selected_month)
    prefix = selected_month.strftime("%Y-%m") + "-"
    transactions = [t for t in transactions if t.get("transaction_date", "").startswith(prefix)]
    title = selected_month.strftime("%b %Y")
    if not transactions:
        emit(stage="empty", count=0, message=f"No transactions found for {title}. Your sheet was left unchanged.")
        return transactions
    if dry_run:
        return transactions
    sheets = sheets_factory()
    emit(stage="writing", message="Refreshing transactions and category chart…")
    spreadsheet = spreadsheet_reader(sheets, spreadsheet_id)
    writer(sheets, spreadsheet_id, title, transactions, sheet_map(spreadsheet))
    emit(stage="complete", count=len(transactions), message=f"Synced {len(transactions)} transactions to {title}.")
    return transactions
