"""Offline desktop protocol and shared-service regression coverage."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import app_backend
from sc_alerts import month_sync as sync
from sc_alerts import google_auth
from sc_alerts.sheet_manager import aggregate_by_merchant, apply_existing_choices


class MonthlyServiceTests(unittest.TestCase):
    def test_progress_and_pagination_parse_counts(self):
        events = []
        with patch.object(sync, "list_messages", return_value=[{"id": "1"}, {"id": "2"}]), \
             patch.object(sync, "get_message", side_effect=[{}, {}]), \
             patch.object(sync, "parse_transaction_message", side_effect=[{"amount": 1}, None]):
            result = sync.fetch_month_transactions(object(), date(2026, 10, 1), lambda **e: events.append(e))
        self.assertEqual(result, [{"amount": 1}])
        self.assertEqual(events[-1]["processed"], 2)
        self.assertEqual(events[-1]["skipped"], 1)
        self.assertEqual(events[-1]["total"], 2)

    def test_complete_only_after_write(self):
        events = []
        txn = {"transaction_date": "2026-10-01"}
        writer = Mock(side_effect=lambda *args: events.append({"stage": "written"}))
        sync.sync_month(date(2026, 10, 1), "sheet", lambda **e: events.append(e),
                        gmail_factory=Mock(), sheets_factory=Mock(), fetch=Mock(return_value=[txn]),
                        spreadsheet_reader=Mock(return_value={"sheets": []}), writer=writer)
        self.assertEqual([e["stage"] for e in events], ["authentication", "writing", "written", "complete"])
        self.assertEqual(events[-1]["count"], 1)

    def test_write_failure_never_emits_success(self):
        events = []
        with self.assertRaises(RuntimeError):
            sync.sync_month(date(2026, 10, 1), "sheet", lambda **e: events.append(e),
                            gmail_factory=Mock(), sheets_factory=Mock(),
                            fetch=Mock(return_value=[{"transaction_date": "2026-10-01"}]),
                            spreadsheet_reader=Mock(return_value={"sheets": []}),
                            writer=Mock(side_effect=RuntimeError("write failed")))
        self.assertNotIn("complete", [e["stage"] for e in events])

    def test_existing_merchant_choices_survive_reaggregation(self):
        txn = {"merchant": "Example", "amount": 12.5, "transaction_date": "2026-10-01"}
        for _ in range(2):
            rows = aggregate_by_merchant([txn])
            apply_existing_choices(rows, {"Example": {"include": False, "category": "Shopping"}})
            self.assertFalse(rows[0]["include"])
            self.assertEqual(rows[0]["category"], "Shopping")


class BackendTests(unittest.TestCase):
    def run_backend(self, arguments, operation):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(google_auth, "CREDENTIALS_FILE"), patch.object(google_auth, "TOKEN_FILE"), \
             patch.object(app_backend, "sync_month", side_effect=operation) as service, \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = app_backend.main(["--config-dir", directory, *arguments])
            calls = service.call_args_list
        return code, [json.loads(line) for line in output.getvalue().splitlines()], calls

    def test_protocol_separates_library_output_and_emits_success(self):
        def operation(month, spreadsheet, emit, **kwargs):
            print("library noise")
            emit(stage="complete", count=3, message="Done")
        code, events, calls = self.run_backend(["--month", "2026-10", "--spreadsheet-id", "sheet"], operation)
        self.assertEqual(code, 0)
        self.assertEqual(events, [{"stage": "complete", "count": 3, "message": "Done"}])
        self.assertEqual(calls[0].args[0], date(2026, 10, 1))

    def test_invalid_arguments_do_not_connect(self):
        for month, sheet in [("2026-13", "sheet"), ("9999-12", "sheet"), ("2026-10", "https://bad")]:
            code, events, calls = self.run_backend(["--month", month, "--spreadsheet-id", sheet], Mock())
            self.assertNotEqual(code, 0)
            self.assertEqual(events[-1]["stage"], "error")
            self.assertEqual(calls, [])

    def test_errors_are_actionable_and_redacted(self):
        for failure in [FileNotFoundError("secret-path"), RuntimeError("secret-token")]:
            code, events, _ = self.run_backend(["--month", "2026-10", "--spreadsheet-id", "sheet"], Mock(side_effect=failure))
            self.assertEqual(code, 1)
            self.assertEqual(events[-1]["stage"], "error")
            self.assertNotIn("secret", events[-1]["message"])

    def test_empty_result_is_terminal_without_writes(self):
        def operation(month, spreadsheet, emit, **kwargs):
            emit(stage="empty", count=0, message="No transactions; unchanged")
        code, events, _ = self.run_backend(["--month", "2026-10", "--spreadsheet-id", "sheet"], operation)
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["stage"], "empty")


if __name__ == "__main__":
    unittest.main()
