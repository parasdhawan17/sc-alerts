"""Offline checks for choosing a month without writing to Google Sheets."""

import argparse
import contextlib
import io
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_month as sync


def transaction(day):
    return {
        "transaction_date": day,
        "bank": "SC",
        "merchant": "Example Merchant",
        "amount": 12.50,
    }


class SyncMonthTests(unittest.TestCase):
    def run_main(self, args, transactions):
        with (
            patch.object(sys, "argv", ["sync_month.py", *args]),
            patch.object(sync, "get_gmail_service"),
            patch.object(sync, "fetch_month_transactions", return_value=transactions) as fetch,
            patch.object(sync, "get_sheets_service") as sheets,
            patch.object(sync, "get_spreadsheet", return_value={"sheets": []}),
            patch.object(sync, "write_month_sheet") as write,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            sync.main()
        return fetch, sheets, write

    def test_selected_month_filters_other_months_and_targets_matching_tab(self):
        september = transaction("2026-09-30")
        fetch, sheets, write = self.run_main(
            ["--month", "2026-09", "--spreadsheet-id", "test-sheet"],
            [transaction("2026-08-31"), september, transaction("2026-10-01")],
        )
        self.assertEqual(fetch.call_args.args[1], date(2026, 9, 1))
        sheets.assert_called_once()
        self.assertEqual(write.call_args.args[1:4], ("test-sheet", "Sep 2026", [september]))

    def test_dry_run_does_not_open_sheets(self):
        fetch, sheets, write = self.run_main(
            ["--month", "2025-12", "--dry-run"], [transaction("2025-12-31")]
        )
        self.assertEqual(fetch.call_args.args[1], date(2025, 12, 1))
        sheets.assert_not_called()
        write.assert_not_called()

    def test_default_is_current_month(self):
        fetch, sheets, write = self.run_main([], [])
        self.assertEqual(fetch.call_args.args[1], date.today().replace(day=1))
        sheets.assert_not_called()
        write.assert_not_called()

    def test_no_matching_transactions_does_not_write(self):
        _, sheets, write = self.run_main(["--month", "2026-09"], [transaction("2026-08-31")])
        sheets.assert_not_called()
        write.assert_not_called()

    def test_invalid_months_are_rejected(self):
        for value in ("September", "2026-9", "2026-00", "2026-13", "0000-01", "2026-09-01"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                sync.parse_month(value)

    def test_december_query_rolls_over_to_next_year(self):
        with (
            patch.object(sync, "list_messages", return_value=[]) as messages,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            sync.fetch_month_transactions(object(), date(2025, 12, 1))
        self.assertIn("after:2025/11/30 before:2026/01/01", messages.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
