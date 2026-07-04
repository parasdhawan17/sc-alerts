"""Parse transaction alert emails from supported banks."""

from typing import Optional

from sc_alerts.dbs_parser import DBS_SENDER, parse_dbs_transaction
from sc_alerts.email_utils import message_headers
from sc_alerts.gmail_sync import SC_ALERTS_SENDER
from sc_alerts.sc_parser import parse_sc_transaction


def parse_transaction_message(message: dict) -> Optional[dict]:
    sender = message_headers(message)["sender"].lower()
    if SC_ALERTS_SENDER in sender:
        return parse_sc_transaction(message)
    if DBS_SENDER in sender:
        return parse_dbs_transaction(message)
    return None


def format_transaction(transaction: dict) -> str:
    lines = [
        f"Bank: {transaction.get('bank', 'Unknown')}",
        f"Email date: {transaction['email_date']}",
        f"Subject: {transaction['subject']}",
        f"Date: {transaction['transaction_date']} {transaction['transaction_time']}",
        f"Merchant: {transaction['merchant']}",
        f"Amount: {transaction['currency']} {transaction['amount']:,.2f}",
        f"Card: {transaction['card']}",
    ]
    return "\n".join(lines)
