#!/usr/bin/env python3
"""Desktop worker. stdout contains only newline-delimited JSON events."""
import _bootstrap  # noqa: F401
import argparse
import contextlib
import json
import sys
from pathlib import Path
from sc_alerts import google_auth
from sc_alerts.month_sync import parse_month, sync_month, fetch_month_transactions


def emit(**event):
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, type=parse_month)
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--config-dir", required=True, type=Path)
    try:
        args = parser.parse_args(argv)
        if not args.spreadsheet_id or not all(c.isalnum() or c in "_-" for c in args.spreadsheet_id):
            raise ValueError("Enter a valid Google spreadsheet ID in Settings.")
        args.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        google_auth.CREDENTIALS_FILE = args.config_dir / "credentials.json"
        google_auth.TOKEN_FILE = args.config_dir / "token.json"
        # Libraries and legacy formatting code may print; never mix those into the protocol.
        def event(**value):
            with contextlib.redirect_stdout(protocol):
                emit(**value)
        protocol = sys.stdout
        with contextlib.redirect_stdout(sys.stderr):
            sync_month(args.month, args.spreadsheet_id, emit=event,
                       fetch=lambda gmail, month: fetch_month_transactions(gmail, month, emit=event))
        return 0
    except SystemExit as exc:
        if exc.code:
            emit(stage="error", message="Invalid sync arguments.")
        return int(exc.code or 0)
    except Exception as exc:
        # Do not expose HTTP responses, token values, or email content through the UI.
        if isinstance(exc, FileNotFoundError):
            message = "Import Google Desktop OAuth credentials in Settings."
        else:
            message = "Google sync failed. Check your connection, Google access, and spreadsheet ID. If writing had started, the sheet may be partially updated; retry the full month."
        emit(stage="error", message=message)
        return 1


if __name__ == "__main__":
    sys.exit(main())
