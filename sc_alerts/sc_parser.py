"""Parse Standard Chartered Singapore transaction alert emails."""

import re
from datetime import datetime
from typing import Optional

from sc_alerts.email_text import message_search_text
from sc_alerts.email_utils import message_datetime, message_headers

CHARGE_PATTERN = re.compile(
    r"Thank you for charging \+?(SGD|USD|EUR|GBP|AUD|HKD|JPY|CNY|MYR)\s*([\d,]+\.?\d*)"
    r"\s+on\s+(\d{2}-[A-Za-z]{3}-\d{2})\s+(\d{1,2}:\d{2}\s*(?:AM|PM))"
    r"\s+to\s+(?:your|yr)\s+credit card\s+(\*+\d+)"
    r"\s+at\s+(.+?)\.\s",
    re.IGNORECASE,
)

NON_TRANSACTION_SUBJECTS = (
    "statement",
    "password",
    "otp",
    "one-time password",
    "security alert",
    "service request",
    "registration",
)

MONTH_SHEET_FORMAT = "%b %Y"
TRANSACTION_DATE_FORMAT = "%d-%b-%y"


def _parse_amount(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _parse_transaction_date(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, TRANSACTION_DATE_FORMAT)
    except ValueError:
        return None


def month_sheet_name(transaction_date: datetime) -> str:
    return transaction_date.strftime(MONTH_SHEET_FORMAT)


def is_sc_transaction_alert(subject: str, body: str) -> bool:
    subject_lower = subject.lower()
    if any(marker in subject_lower for marker in NON_TRANSACTION_SUBJECTS):
        return False
    return "charging" in body.lower() or "transaction alert" in subject_lower


def parse_sc_transaction(message: dict) -> Optional[dict]:
    headers = message_headers(message)
    search_text = message_search_text(message)

    if not search_text or not is_sc_transaction_alert(headers["subject"], search_text):
        return None

    match = CHARGE_PATTERN.search(search_text)
    if not match:
        return None

    currency, amount_raw, date_raw, time_raw, card, merchant = match.groups()
    amount = _parse_amount(amount_raw)
    transaction_date = _parse_transaction_date(date_raw)
    if amount is None or transaction_date is None:
        return None

    return {
        "message_id": message["id"],
        "bank": "SC",
        "email_date": message_datetime(headers["date_raw"]),
        "subject": headers["subject"],
        "transaction_type": "CHARGE",
        "amount": amount,
        "currency": currency.upper(),
        "card": card.strip(),
        "merchant": merchant.strip().rstrip("."),
        "transaction_date": transaction_date.strftime("%Y-%m-%d"),
        "transaction_time": time_raw.strip().upper(),
        "month": month_sheet_name(transaction_date),
    }
