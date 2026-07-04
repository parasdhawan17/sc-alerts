"""Shared email body normalization helpers."""

import re
from html import unescape

from sc_alerts.email_utils import decode_body

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"[ \t]+")
HTML_BLOCK_PATTERN = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


def extract_body(message: dict) -> str:
    return decode_body(message.get("payload", {}))


def normalize_body(body: str) -> str:
    text = unescape(body)
    text = HTML_TAG_PATTERN.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [WHITESPACE_PATTERN.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def html_to_visible_text(body: str) -> str:
    text = unescape(body)
    text = HTML_BLOCK_PATTERN.sub("\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = HTML_TAG_PATTERN.sub("\n", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        cleaned = WHITESPACE_PATTERN.sub(" ", line).strip()
        if not cleaned or len(cleaned) <= 2:
            continue
        if cleaned.startswith("/*") or "color-scheme" in cleaned:
            continue
        if cleaned.startswith("(Optional)") or cleaned == "END -->":
            continue
        if cleaned.startswith("&zwnj;"):
            continue
        lines.append(cleaned)
    return "\n".join(lines)


def message_search_text(message: dict) -> str:
    raw_body = extract_body(message)
    visible = html_to_visible_text(raw_body)
    if "Dear Customer" in visible or "Amount:" in visible:
        return visible
    normalized = normalize_body(raw_body)
    snippet = message.get("snippet", "")
    return normalized or snippet
