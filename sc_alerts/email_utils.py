"""Shared helpers for reading Gmail message content."""

import base64
from email.utils import parsedate_to_datetime


def header_value(headers: list[dict], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def decode_body(payload: dict) -> str:
    if not payload:
        return ""

    body_data = payload.get("body", {}).get("data")
    if body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain":
            text = decode_body(part)
            if text:
                return text
        if mime_type == "text/html":
            text = decode_body(part)
            if text:
                return text

    for part in payload.get("parts", []):
        text = decode_body(part)
        if text:
            return text

    return ""


def get_message(gmail, message_id: str) -> dict:
    return (
        gmail.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )


def message_headers(message: dict) -> dict[str, str]:
    headers = message.get("payload", {}).get("headers", [])
    return {
        "subject": header_value(headers, "Subject") or "(no subject)",
        "sender": header_value(headers, "From") or "(unknown sender)",
        "date_raw": header_value(headers, "Date"),
    }


def message_datetime(date_raw: str) -> str:
    try:
        return parsedate_to_datetime(date_raw).isoformat(sep=" ", timespec="seconds")
    except (TypeError, ValueError, IndexError):
        return date_raw or "(unknown date)"
