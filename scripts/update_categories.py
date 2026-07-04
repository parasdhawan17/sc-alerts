#!/usr/bin/env python3
"""Add category breakdown and chart to existing month tabs without re-syncing emails."""

import _bootstrap  # noqa: F401

import argparse

from sc_alerts.google_auth import get_sheets_service
from sc_alerts.sheet_manager import (
    get_spreadsheet,
    month_sort_key,
    sheet_map,
    update_merchant_table,
    write_category_section,
)

DEFAULT_SPREADSHEET_ID = "1fD1qL3GjtEanxnL0MvwByauKz3xe2MthMndNL3E14cg"
DEFAULT_YEAR = 2026


def month_tabs_for_year(sheets, spreadsheet_id: str, year: int) -> list[str]:
    spreadsheet = get_spreadsheet(sheets, spreadsheet_id)
    tabs = [sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])]
    month_tabs = []
    for title in tabs:
        try:
            if month_sort_key(title).year == year:
                month_tabs.append(title)
        except ValueError:
            continue
    return sorted(month_tabs, key=month_sort_key)


def update_categories_for_year(
    sheets,
    spreadsheet_id: str,
    year: int,
) -> dict[str, int]:
    spreadsheet = get_spreadsheet(sheets, spreadsheet_id)
    titles_to_ids = sheet_map(spreadsheet)
    summary: dict[str, int] = {}

    for month_name in month_tabs_for_year(sheets, spreadsheet_id, year):
        sheet_id = titles_to_ids[month_name]
        merchant_rows = update_merchant_table(
            sheets,
            spreadsheet_id,
            month_name,
            sheet_id,
        )
        write_category_section(
            sheets,
            spreadsheet_id,
            month_name,
            merchant_rows,
            sheet_id,
        )
        summary[month_name] = len(merchant_rows)
        print(f"  {month_name}: {len(merchant_rows)} merchant(s) categorized")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add category spend breakdown and chart to existing month tabs."
    )
    parser.add_argument(
        "--spreadsheet-id",
        default=DEFAULT_SPREADSHEET_ID,
        help="Target Google Spreadsheet ID",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_YEAR,
        help="Year to update (default: 2026)",
    )
    args = parser.parse_args()

    sheets = get_sheets_service()
    print(f"Updating category breakdown for {args.year} in spreadsheet {args.spreadsheet_id}...")
    summary = update_categories_for_year(sheets, args.spreadsheet_id, args.year)

    print("\nDone. Updated tabs:")
    for month_name, count in sorted(summary.items(), key=lambda item: month_sort_key(item[0])):
        print(f"  {month_name}: {count} merchant(s)")


if __name__ == "__main__":
    main()
