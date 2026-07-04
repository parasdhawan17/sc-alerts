"""Gmail queries and paginated message listing for bank transaction alerts."""

from datetime import date, timedelta
from typing import Optional

from sc_alerts.dbs_parser import DBS_SENDER

SC_ALERTS_SENDER = "alerts.sg@sc.com"
TRANSACTION_QUERY = f"(from:{SC_ALERTS_SENDER} OR from:{DBS_SENDER})"
PAGE_SIZE = 500


def month_query(year: int, month: int, base_query: str = TRANSACTION_QUERY) -> str:
    first_of_month = date(year, month, 1)
    if month == 12:
        first_of_next_month = date(year + 1, 1, 1)
    else:
        first_of_next_month = date(year, month + 1, 1)

    day_before_month = first_of_month - timedelta(days=1)
    after = f"{day_before_month.year}/{day_before_month.month:02d}/{day_before_month.day:02d}"
    before = f"{first_of_next_month.year}/{first_of_next_month.month:02d}/{first_of_next_month.day:02d}"
    return f"{base_query} after:{after} before:{before}"


def current_month_query(base_query: str = TRANSACTION_QUERY, today: Optional[date] = None) -> str:
    today = today or date.today()
    return month_query(today.year, today.month, base_query)


def year_query(year: int, base_query: str = TRANSACTION_QUERY) -> str:
    after = f"{year}/01/01"
    before = f"{year + 1}/01/01"
    return f"{base_query} after:{after} before:{before}"


def list_messages(gmail, query: str, max_results: Optional[int] = None) -> list[dict]:
    messages: list[dict] = []
    page_token = None

    while True:
        request = gmail.users().messages().list(
            userId="me",
            q=query,
            maxResults=PAGE_SIZE,
            pageToken=page_token,
        )
        response = request.execute()
        messages.extend(response.get("messages", []))

        if max_results is not None and len(messages) >= max_results:
            return messages[:max_results]

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return messages
