#!/usr/bin/env python3
"""Read SC and DBS transaction alert emails from Gmail."""

import _bootstrap  # noqa: F401

import argparse
import json
from datetime import datetime

from sc_alerts.email_utils import decode_body, get_message, message_datetime, message_headers
from sc_alerts.gmail_sync import TRANSACTION_QUERY, current_month_query, list_messages, month_query
from sc_alerts.google_auth import get_gmail_service
from sc_alerts.transaction_parser import format_transaction, parse_transaction_message


def format_raw_message(message: dict) -> str:
    headers = message_headers(message)
    body = decode_body(message.get("payload", {})).strip()
    snippet = message.get("snippet", "").strip()

    lines = [
        f"Date: {message_datetime(headers['date_raw'])}",
        f"From: {headers['sender']}",
        f"Subject: {headers['subject']}",
        f"Snippet: {snippet}",
    ]
    if body:
        preview = body[:500] + ("..." if len(body) > 500 else "")
        lines.append(f"Body preview:\n{preview}")

    return "\n".join(lines)


def resolve_query(args: argparse.Namespace) -> str:
    if args.month:
        try:
            parsed = datetime.strptime(args.month, "%Y-%m")
        except ValueError as exc:
            raise SystemExit("Invalid --month value. Use YYYY-MM, e.g. 2026-06.") from exc
        return month_query(parsed.year, parsed.month)

    if args.current_month:
        return current_month_query()

    return TRANSACTION_QUERY


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read transaction alert emails from SC and DBS in Gmail."
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="Maximum number of emails to fetch (default: 20)",
    )
    parser.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Only fetch emails from a specific month",
    )
    parser.add_argument(
        "--current-month",
        action="store_true",
        help="Only fetch emails from the current month",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw email previews instead of parsed transaction details",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print parsed transactions as JSON",
    )
    args = parser.parse_args()

    gmail_query = resolve_query(args)
    gmail = get_gmail_service()
    message_refs = list_messages(gmail, gmail_query, max_results=args.max_results)

    if not message_refs:
        print(f"No emails found for query: {gmail_query}")
        return

    print(f"Found {len(message_refs)} email(s) for query: {gmail_query}\n")

    parsed_transactions: list[dict] = []
    for index, item in enumerate(message_refs, start=1):
        message = get_message(gmail, item["id"])

        if args.raw:
            print(f"--- Email {index} ---")
            print(format_raw_message(message))
            print()
            continue

        transaction = parse_transaction_message(message)
        if not transaction:
            print(f"--- Email {index} (unparsed) ---")
            print(format_raw_message(message))
            print()
            continue

        parsed_transactions.append(transaction)
        print(f"--- Transaction {index} ---")
        print(format_transaction(transaction))
        print()

    if args.json and parsed_transactions:
        print(json.dumps(parsed_transactions, indent=2))


if __name__ == "__main__":
    main()
