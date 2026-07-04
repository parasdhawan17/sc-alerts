"""Parse DBS Singapore transaction alert emails."""

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

from sc_alerts.email_text import message_search_text
from sc_alerts.email_utils import message_datetime, message_headers
from sc_alerts.sc_parser import MONTH_SHEET_FORMAT, _parse_amount, month_sheet_name

DBS_SENDER = "ibanking.alert@dbs.com"

DATE_TIME_PATTERN = re.compile(
    r"Date(?:\s+and\s+Time|\s*&\s*Time)\s*:\s*"
    r"(\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{4})?)\s+(\d{1,2}:\d{2})"
    r"(?:\s*(?:\(SGT\)|SGT))?",
    re.IGNORECASE,
)
INLINE_DATE_TIME_PATTERN = re.compile(
    r"on\s+(\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{4})?)\s+(\d{1,2}:\d{2})\s+SGT",
    re.IGNORECASE,
)
AMOUNT_PATTERN = re.compile(r"Amount\s*:\s*(?:SGD|S\$)\s*([\d,]+\.?\d*)", re.IGNORECASE)
INLINE_AMOUNT_PATTERN = re.compile(
    r"received\s+(?:SGD|S\$)\s*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
TO_PATTERN = re.compile(
    r"To\s*:\s*(.+?)(?:\n\s*If\b|\n\s*Thank you|\n\s*Didn)",
    re.IGNORECASE | re.DOTALL,
)
FROM_ACCOUNT_PATTERN = re.compile(
    r"From\s*:\s*.+?(?:ending|A/C ending)\s+(\d{4})",
    re.IGNORECASE,
)

SKIP_SUBJECT_MARKERS = (
    "estatement",
    "edocument",
    "consolidated statement",
    "received a transfer",
    "received sgd",
)

SPEND_SUBJECT_MARKERS = (
    "ibanking alerts",
    "nets scan",
    "bill payment",
    "card transaction",
    "pos",
    "purchase",
)

MONTH_LOOKUP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# DBS bill payments to SC cards are already tracked via SC transaction alerts.
SKIP_MERCHANT_PATTERN = re.compile(r"SCB\s+CREDIT\s+CARDS", re.IGNORECASE)


def _clean_merchant(value: str) -> str:
    merchant = re.sub(r"\s+", " ", value).strip().rstrip(".")
    return merchant


def _email_year(message: dict) -> int:
    headers = message_headers(message)
    try:
        return parsedate_to_datetime(headers["date_raw"]).year
    except (TypeError, ValueError, IndexError):
        return datetime.now().year


def _parse_dbs_datetime(date_raw: str, time_raw: str, fallback_year: int) -> Optional[datetime]:
    parts = date_raw.strip().split()
    if len(parts) == 2:
        day = int(parts[0])
        month = MONTH_LOOKUP.get(parts[1].lower()[:3])
        year = fallback_year
        if month is None:
            return None
    elif len(parts) == 3:
        day = int(parts[0])
        month = MONTH_LOOKUP.get(parts[1].lower()[:3])
        year = int(parts[2])
        if month is None:
            return None
    else:
        return None

    hour, minute = [int(part) for part in time_raw.split(":", 1)]
    return datetime(year, month, day, hour, minute)


def is_dbs_transaction_alert(subject: str, body: str) -> bool:
    subject_lower = subject.lower()
    body_lower = body.lower()

    if any(marker in subject_lower for marker in SKIP_SUBJECT_MARKERS):
        return False
    if "you have received" in body_lower or "you've received" in body_lower:
        return False
    if any(marker in subject_lower for marker in SPEND_SUBJECT_MARKERS):
        return True
    return "amount:" in body_lower and "to:" in body_lower


def _merchant_from_subject(subject: str) -> Optional[str]:
    subject_lower = subject.lower()
    if "nets scan" in subject_lower:
        return "NETS Scan & Pay"
    if "bill payment" in subject_lower:
        return "Bill Payment"
    if "paynow" in subject_lower:
        return "PayNow"
    return None


def parse_dbs_transaction(message: dict) -> Optional[dict]:
    headers = message_headers(message)
    search_text = message_search_text(message)

    if not search_text or not is_dbs_transaction_alert(headers["subject"], search_text):
        return None

    amount_match = AMOUNT_PATTERN.search(search_text)
    if not amount_match:
        amount_match = INLINE_AMOUNT_PATTERN.search(search_text)
    to_match = TO_PATTERN.search(search_text)
    date_match = DATE_TIME_PATTERN.search(search_text)
    if not date_match:
        date_match = INLINE_DATE_TIME_PATTERN.search(search_text)

    if not amount_match or not to_match or not date_match:
        return None

    fallback_year = _email_year(message)
    transaction_date = _parse_dbs_datetime(
        date_match.group(1),
        date_match.group(2),
        fallback_year,
    )
    amount = _parse_amount(amount_match.group(1))
    if amount is None or transaction_date is None:
        return None

    merchant = _clean_merchant(to_match.group(1))
    if not merchant:
        merchant = _merchant_from_subject(headers["subject"]) or "DBS Transaction"

    if SKIP_MERCHANT_PATTERN.search(merchant):
        return None

    from_match = FROM_ACCOUNT_PATTERN.search(search_text)
    card = f"****{from_match.group(1)}" if from_match else "****"

    return {
        "message_id": message["id"],
        "bank": "DBS",
        "email_date": message_datetime(headers["date_raw"]),
        "subject": headers["subject"],
        "transaction_type": "CHARGE",
        "amount": amount,
        "currency": "SGD",
        "card": card,
        "merchant": merchant,
        "transaction_date": transaction_date.strftime("%Y-%m-%d"),
        "transaction_time": date_match.group(2),
        "month": month_sheet_name(transaction_date),
    }
