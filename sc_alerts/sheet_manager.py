"""Create and format monthly merchant spending sheets."""

import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

from googleapiclient.errors import HttpError

from sc_alerts.merchant_categories import (
    CATEGORY_ORDER,
    aggregate_by_category,
    categorize_merchant,
    display_category,
    is_paynow_merchant,
)

SHEET_HEADERS = ["Merchant", "Transactions", "Total Spend (SGD)", "Avg per Visit", "Incl", "Category"]
CATEGORY_HEADERS = ["Category", "Spend (SGD)"]
CATEGORY_TITLE = "📊  By Category"
CATEGORY_START_COL = 7  # column H
CATEGORY_CHART_COL = 10  # column K
TITLE_ROW_INDEX = 0
HEADER_ROW_INDEX = 2
DATA_START_ROW_INDEX = 3

INCLUDE_ICON = "✅"
EXCLUDE_ICON = "❌"

# Standard Chartered-inspired palette
SC_GREEN = {"red": 0.0, "green": 0.52, "blue": 0.44}
HEADER_BG = {"red": 0.12, "green": 0.16, "blue": 0.22}
HEADER_FG = {"red": 1.0, "green": 1.0, "blue": 1.0}
TITLE_FG = {"red": 1.0, "green": 1.0, "blue": 1.0}
STRIPE_A = {"red": 1.0, "green": 1.0, "blue": 1.0}
STRIPE_B = {"red": 0.94, "green": 0.98, "blue": 0.96}
TOTAL_BG = {"red": 0.86, "green": 0.95, "blue": 0.90}
TOTAL_LABEL_BG = SC_GREEN
TOTAL_FG = {"red": 0.05, "green": 0.25, "blue": 0.18}
DEFAULT_TEXT = {"red": 0.1, "green": 0.1, "blue": 0.1}

MERCHANT_COLORS = [
    {"red": 0.0, "green": 0.45, "blue": 0.85},
    {"red": 0.55, "green": 0.2, "blue": 0.75},
    {"red": 0.9, "green": 0.35, "blue": 0.1},
    {"red": 0.1, "green": 0.6, "blue": 0.55},
    {"red": 0.75, "green": 0.15, "blue": 0.45},
    {"red": 0.2, "green": 0.35, "blue": 0.8},
    {"red": 0.85, "green": 0.5, "blue": 0.0},
    {"red": 0.35, "green": 0.7, "blue": 0.3},
]

COLUMN_WIDTHS = [220, 110, 140, 130, 60, 140]
CATEGORY_COLUMN_WIDTHS = [160, 130]


def merchant_color(merchant: str) -> dict:
    normalized = merchant.strip().upper()
    index = sum(ord(char) * (idx + 1) for idx, char in enumerate(normalized)) % len(MERCHANT_COLORS)
    return MERCHANT_COLORS[index]


def month_sort_key(month_name: str) -> datetime:
    return datetime.strptime(month_name, "%b %Y")


def aggregate_by_merchant(transactions: list[dict]) -> list[dict]:
    totals: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0.0})
    for txn in transactions:
        merchant = txn["merchant"]
        totals[merchant]["count"] += 1
        totals[merchant]["total"] += txn["amount"]

    rows = [
        {
            "merchant": merchant,
            "count": data["count"],
            "total": data["total"],
            "average": data["total"] / data["count"],
            "include": True,
            "category": categorize_merchant(merchant) or "Other",
        }
        for merchant, data in totals.items()
    ]
    return sorted(rows, key=lambda row: (-row["total"], row["merchant"].upper()))


def execute_with_retry(request):
    for attempt in range(5):
        try:
            return request.execute()
        except HttpError as error:
            if error.resp.status == 429 and attempt < 4:
                time.sleep(2 ** attempt + 1)
                continue
            raise


def get_spreadsheet(sheets, spreadsheet_id: str) -> dict:
    return execute_with_retry(
        sheets.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets.properties,sheets.merges",
        )
    )


def sheet_map(spreadsheet: dict) -> dict[str, int]:
    return {
        sheet["properties"]["title"]: sheet["properties"]["sheetId"]
        for sheet in spreadsheet.get("sheets", [])
    }


def _grid_range(sheet_id: int, start_row: int, end_row: int, start_col: int, end_col: int) -> dict:
    return {
        "sheetId": sheet_id,
        "startRowIndex": start_row,
        "endRowIndex": end_row,
        "startColumnIndex": start_col,
        "endColumnIndex": end_col,
    }


def month_title(month_name: str) -> str:
    return f"💳  {month_name} Spending"


def parse_amount(value) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def read_merchant_rows_from_values(values: list[list]) -> list[dict]:
    rows: list[dict] = []
    for row in values[DATA_START_ROW_INDEX:]:
        if not row:
            continue
        merchant = str(row[0]).strip() if row[0] else ""
        if not merchant or merchant.startswith("📊"):
            break
        count = int(row[1]) if len(row) > 1 and row[1] != "" else 0
        total = parse_amount(row[2]) if len(row) > 2 else 0.0
        average = parse_amount(row[3]) if len(row) > 3 and row[3] != "" else (total / count if count else 0.0)
        include_text = str(row[4]).strip() if len(row) > 4 and row[4] != "" else INCLUDE_ICON
        include = include_text not in (EXCLUDE_ICON, "Exclude", "exclude", "EXCLUDE")
        category = str(row[5]).strip() if len(row) > 5 and row[5] != "" else None
        rows.append(
            {
                "merchant": merchant,
                "count": count,
                "total": total,
                "average": average,
                "include": include,
                "category": category,
            }
        )
    return rows


def build_category_values(category_rows: list[dict]) -> list[list]:
    values: list[list] = [
        [CATEGORY_TITLE, ""],
        [""],
        CATEGORY_HEADERS,
    ]

    # Merchant category and include columns are fixed at F and E.
    merchant_category_col = _column_letter(5)
    include_col = _column_letter(4)
    spend_col = _column_letter(CATEGORY_START_COL + 1)
    category_name_col = _column_letter(CATEGORY_START_COL)
    include_literal = INCLUDE_ICON

    # Category data starts at 1-indexed row 4 (DATA_START_ROW_INDEX + 1).
    for index, row in enumerate(category_rows, start=0):
        data_row = DATA_START_ROW_INDEX + 1 + index
        formula = (
            f'=SUMIFS($C$4:$C$1000,${include_col}$4:${include_col}$1000,"{include_literal}",'
            f'${merchant_category_col}$4:${merchant_category_col}$1000,{category_name_col}{data_row})'
        )
        values.append([row["category"], formula])

    if category_rows:
        total_row = DATA_START_ROW_INDEX + 1 + len(category_rows)
        total_formula = f"=SUM({spend_col}4:{spend_col}{total_row - 1})"
        values.append(["📊  CATEGORY TOTAL", total_formula])

    return values


def build_month_values(month_name: str, merchant_rows: list[dict]) -> list[list]:
    values: list[list] = [
        [month_title(month_name), "", "", "", "", ""],
        [""],
        SHEET_HEADERS,
    ]

    for row in merchant_rows:
        category = row.get("category")
        if not category:
            category = categorize_merchant(row["merchant"]) or display_category("Other")
        else:
            category = display_category(category)
        include_value = INCLUDE_ICON if row.get("include", True) else EXCLUDE_ICON
        values.append(
            [
                row["merchant"],
                row["count"],
                row["total"],
                row["average"],
                include_value,
                category,
            ]
        )

    if merchant_rows:
        # Dynamic total that recalculates whenever the Include/Exclude icons change.
        include_literal = INCLUDE_ICON
        values.append(
            [
                "📊  MONTHLY TOTAL",
                f'=COUNTIF(E4:E1000,"{include_literal}")',
                f'=SUMIF(E4:E1000,"{include_literal}",C4:C1000)',
                f'=IF(COUNTIF(E4:E1000,"{include_literal}")=0,0,SUMIF(E4:E1000,"{include_literal}",C4:C1000)/COUNTIF(E4:E1000,"{include_literal}"))',
                "",
                "",
            ]
        )

    return values


def ensure_month_sheet(
    sheets,
    spreadsheet_id: str,
    month_name: str,
    titles_to_ids: dict[str, int],
) -> int:
    if month_name in titles_to_ids:
        return titles_to_ids[month_name]

    response = execute_with_retry(
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": month_name}}}]},
        )
    )
    sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]
    titles_to_ids[month_name] = sheet_id
    return sheet_id


def reorder_month_tabs(
    sheets,
    spreadsheet_id: str,
    month_names: list[str],
    titles_to_ids: dict[str, int],
) -> None:
    sorted_months = sorted(month_names, key=month_sort_key, reverse=True)
    requests = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": titles_to_ids[name], "index": index},
                "fields": "index",
            }
        }
        for index, name in enumerate(sorted_months)
        if name in titles_to_ids
    ]
    if requests:
        execute_with_retry(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            )
        )


def formatting_requests(sheet_id: int, merchant_rows: list[dict]) -> list[dict]:
    last_col = len(SHEET_HEADERS)
    data_row_count = len(merchant_rows)
    total_row_index = DATA_START_ROW_INDEX + data_row_count
    sheet_end_row = total_row_index + 1 if merchant_rows else DATA_START_ROW_INDEX + 1

    requests: list[dict] = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": HEADER_ROW_INDEX + 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "mergeCells": {
                "range": _grid_range(sheet_id, TITLE_ROW_INDEX, TITLE_ROW_INDEX + 1, 0, last_col),
                "mergeType": "MERGE_ALL",
            }
        },
        {
            "repeatCell": {
                "range": _grid_range(sheet_id, TITLE_ROW_INDEX, TITLE_ROW_INDEX + 1, 0, last_col),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": SC_GREEN,
                        "textFormat": {
                            "foregroundColor": TITLE_FG,
                            "bold": True,
                            "fontSize": 14,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": TITLE_ROW_INDEX,
                    "endIndex": TITLE_ROW_INDEX + 1,
                },
                "properties": {"pixelSize": 42},
                "fields": "pixelSize",
            }
        },
        {
            "repeatCell": {
                "range": _grid_range(sheet_id, HEADER_ROW_INDEX, HEADER_ROW_INDEX + 1, 0, last_col),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": HEADER_BG,
                        "textFormat": {
                            "foregroundColor": HEADER_FG,
                            "bold": True,
                            "fontSize": 10,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
    ]

    for index in range(data_row_count):
        row_index = DATA_START_ROW_INDEX + index
        stripe = STRIPE_A if index % 2 == 0 else STRIPE_B
        merchant = merchant_rows[index]["merchant"]
        requests.extend(
            [
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, row_index, row_index + 1, 0, last_col),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": stripe,
                                "textFormat": {"fontSize": 10, "foregroundColor": DEFAULT_TEXT},
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, row_index, row_index + 1, 0, 1),
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {
                                    "foregroundColor": merchant_color(merchant),
                                    "bold": True,
                                    "fontSize": 10,
                                },
                                "horizontalAlignment": "LEFT",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, row_index, row_index + 1, 1, 2),
                        "cell": {
                            "userEnteredFormat": {"horizontalAlignment": "CENTER"}
                        },
                        "fields": "userEnteredFormat.horizontalAlignment",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, row_index, row_index + 1, 2, 4),
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "RIGHT",
                                "numberFormat": {
                                    "type": "CURRENCY",
                                    "pattern": "$#,##0.00",
                                },
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,numberFormat)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, row_index, row_index + 1, 4, 5),
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "CENTER",
                                "textFormat": {"bold": True, "fontSize": 10},
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,textFormat)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, row_index, row_index + 1, 5, 6),
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "LEFT",
                                "textFormat": {"fontSize": 10},
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,textFormat)",
                    }
                },
            ]
        )

    if merchant_rows:
        requests.extend(
            [
                {
                    "updateBorders": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, 0, last_col),
                        "top": {"style": "SOLID_MEDIUM", "color": {"red": 0.4, "green": 0.4, "blue": 0.4}},
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, 0, last_col),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": TOTAL_BG,
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColor": TOTAL_FG,
                                    "fontSize": 11,
                                },
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, 0, 1),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": TOTAL_LABEL_BG,
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColor": TITLE_FG,
                                    "fontSize": 11,
                                },
                                "horizontalAlignment": "LEFT",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, 1, 2),
                        "cell": {
                            "userEnteredFormat": {"horizontalAlignment": "CENTER"}
                        },
                        "fields": "userEnteredFormat.horizontalAlignment",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, 2, 4),
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "RIGHT",
                                "numberFormat": {
                                    "type": "CURRENCY",
                                    "pattern": "$#,##0.00",
                                },
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,numberFormat)",
                    }
                },
            ]
        )

    for index, width in enumerate(COLUMN_WIDTHS):
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": index,
                        "endIndex": index + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                }
            }
        )

    if data_row_count:
        requests.append(
            {
                "setDataValidation": {
                    "range": _grid_range(
                        sheet_id,
                        DATA_START_ROW_INDEX,
                        DATA_START_ROW_INDEX + data_row_count,
                        4,
                        5,
                    ),
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [
                                {"userEnteredValue": INCLUDE_ICON},
                                {"userEnteredValue": EXCLUDE_ICON},
                            ],
                        },
                        "inputMessage": f"{INCLUDE_ICON} = include in totals, {EXCLUDE_ICON} = exclude",
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            }
        )

        category_dropdown_values = [
            {"userEnteredValue": display_category(category)}
            for category in CATEGORY_ORDER
        ]
        requests.append(
            {
                "setDataValidation": {
                    "range": _grid_range(
                        sheet_id,
                        DATA_START_ROW_INDEX,
                        DATA_START_ROW_INDEX + data_row_count,
                        5,
                        6,
                    ),
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": category_dropdown_values,
                        },
                        "inputMessage": "Select a spending category",
                        "strict": True,
                        "showCustomUi": True,
                    },
                }
            }
        )

    requests.append(
        {
            "updateBorders": {
                "range": _grid_range(sheet_id, HEADER_ROW_INDEX, sheet_end_row, 0, last_col),
                "top": {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}},
                "bottom": {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}},
                "left": {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}},
                "right": {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}},
                "innerHorizontal": {"style": "SOLID", "color": {"red": 0.88, "green": 0.88, "blue": 0.88}},
                "innerVertical": {"style": "SOLID", "color": {"red": 0.88, "green": 0.88, "blue": 0.88}},
            }
        }
    )

    return requests


def category_formatting_requests(
    sheet_id: int,
    category_rows: list[dict],
    data_start_row: int = DATA_START_ROW_INDEX,
) -> list[dict]:
    category_col_count = len(CATEGORY_HEADERS)
    data_row_count = len(category_rows)
    header_row_index = data_start_row - 1
    title_row_index = header_row_index - 2
    total_row_index = data_start_row + data_row_count
    sheet_end_row = total_row_index + 1 if category_rows else data_start_row + 1
    start_col = CATEGORY_START_COL
    end_col = start_col + category_col_count

    requests: list[dict] = [
        {
            "mergeCells": {
                "range": _grid_range(sheet_id, title_row_index, title_row_index + 1, start_col, end_col),
                "mergeType": "MERGE_ALL",
            }
        },
        {
            "repeatCell": {
                "range": _grid_range(sheet_id, title_row_index, title_row_index + 1, start_col, end_col),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": SC_GREEN,
                        "textFormat": {
                            "foregroundColor": TITLE_FG,
                            "bold": True,
                            "fontSize": 12,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        {
            "repeatCell": {
                "range": _grid_range(sheet_id, header_row_index, header_row_index + 1, start_col, end_col),
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": HEADER_BG,
                        "textFormat": {
                            "foregroundColor": HEADER_FG,
                            "bold": True,
                            "fontSize": 10,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
    ]

    for index in range(data_row_count):
        row_index = data_start_row + index
        stripe = STRIPE_A if index % 2 == 0 else STRIPE_B
        requests.extend(
            [
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, row_index, row_index + 1, start_col, end_col),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": stripe,
                                "textFormat": {"fontSize": 10, "foregroundColor": DEFAULT_TEXT},
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, row_index, row_index + 1, start_col + 1, end_col),
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "RIGHT",
                                "numberFormat": {
                                    "type": "CURRENCY",
                                    "pattern": "$#,##0.00",
                                },
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,numberFormat)",
                    }
                },
            ]
        )

    if category_rows:
        requests.extend(
            [
                {
                    "updateBorders": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, start_col, end_col),
                        "top": {"style": "SOLID_MEDIUM", "color": {"red": 0.4, "green": 0.4, "blue": 0.4}},
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, start_col, end_col),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": TOTAL_BG,
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColor": TOTAL_FG,
                                    "fontSize": 11,
                                },
                                "verticalAlignment": "MIDDLE",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, start_col, start_col + 1),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": TOTAL_LABEL_BG,
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColor": TITLE_FG,
                                    "fontSize": 11,
                                },
                                "horizontalAlignment": "LEFT",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": _grid_range(sheet_id, total_row_index, total_row_index + 1, start_col + 1, end_col),
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "RIGHT",
                                "numberFormat": {
                                    "type": "CURRENCY",
                                    "pattern": "$#,##0.00",
                                },
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,numberFormat)",
                    }
                },
            ]
        )

    for offset, width in enumerate(CATEGORY_COLUMN_WIDTHS):
        col_index = start_col + offset
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": col_index,
                        "endIndex": col_index + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                }
            }
        )

    requests.append(
        {
            "updateBorders": {
                "range": _grid_range(sheet_id, header_row_index, sheet_end_row, start_col, end_col),
                "top": {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}},
                "bottom": {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}},
                "left": {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}},
                "right": {"style": "SOLID", "color": {"red": 0.75, "green": 0.75, "blue": 0.75}},
                "innerHorizontal": {"style": "SOLID", "color": {"red": 0.88, "green": 0.88, "blue": 0.88}},
                "innerVertical": {"style": "SOLID", "color": {"red": 0.88, "green": 0.88, "blue": 0.88}},
            }
        }
    )

    return requests


def _column_letter(col_index: int) -> str:
    letters = ""
    index = col_index + 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def delete_sheet_charts(sheets, spreadsheet_id: str, sheet_id: int) -> None:
    spreadsheet = execute_with_retry(
        sheets.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties.sheetId,charts)",
        )
    )
    requests = []
    for sheet in spreadsheet.get("sheets", []):
        if sheet["properties"]["sheetId"] != sheet_id:
            continue
        for chart in sheet.get("charts", []):
            requests.append({"deleteEmbeddedObject": {"objectId": chart["chartId"]}})

    if requests:
        execute_with_retry(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            )
        )


def category_chart_request(
    sheet_id: int,
    category_rows: list[dict],
    data_start_row: int = DATA_START_ROW_INDEX,
) -> Optional[dict]:
    if not category_rows:
        return None

    data_end_row = data_start_row + len(category_rows)
    return {
        "addChart": {
            "chart": {
                "spec": {
                    "title": "Spend by Category",
                    "pieChart": {
                        "legendPosition": "RIGHT_LEGEND",
                        "domain": {
                            "sourceRange": {
                                "sources": [
                                    {
                                        "sheetId": sheet_id,
                                        "startRowIndex": data_start_row,
                                        "endRowIndex": data_end_row,
                                        "startColumnIndex": CATEGORY_START_COL,
                                        "endColumnIndex": CATEGORY_START_COL + 1,
                                    }
                                ]
                            }
                        },
                        "series": {
                            "sourceRange": {
                                "sources": [
                                    {
                                        "sheetId": sheet_id,
                                        "startRowIndex": data_start_row,
                                        "endRowIndex": data_end_row,
                                        "startColumnIndex": CATEGORY_START_COL + 1,
                                        "endColumnIndex": CATEGORY_START_COL + 2,
                                    }
                                ]
                            }
                        },
                    },
                },
                "position": {
                    "overlayPosition": {
                        "anchorCell": {
                            "sheetId": sheet_id,
                            "rowIndex": HEADER_ROW_INDEX,
                            "columnIndex": CATEGORY_CHART_COL,
                        },
                        "widthPixels": 420,
                        "heightPixels": 320,
                    }
                },
            }
        }
    }


def write_category_section(
    sheets,
    spreadsheet_id: str,
    month_name: str,
    merchant_rows: list[dict],
    sheet_id: int,
) -> None:
    category_rows = aggregate_by_category(merchant_rows)
    values = build_category_values(category_rows)
    start_col_letter = _column_letter(CATEGORY_START_COL)
    end_col_letter = _column_letter(CATEGORY_START_COL + len(CATEGORY_HEADERS) - 1)

    execute_with_retry(
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{month_name}'!{start_col_letter}1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
    )
    time.sleep(0.3)

    clear_from_row = len(values) + 1
    execute_with_retry(
        sheets.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"'{month_name}'!{start_col_letter}{clear_from_row}:{end_col_letter}",
        )
    )

    delete_sheet_charts(sheets, spreadsheet_id, sheet_id)

    requests = category_formatting_requests(sheet_id, category_rows)
    chart_request = category_chart_request(sheet_id, category_rows)
    if chart_request:
        requests.append(chart_request)

    if requests:
        execute_with_retry(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            )
        )
    time.sleep(0.3)


def load_existing_merchant_choices(
    sheets,
    spreadsheet_id: str,
    month_name: str,
) -> dict[str, dict]:
    """Read existing merchant Include/Category choices from a sheet, if present."""
    try:
        result = execute_with_retry(
            sheets.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{month_name}'!A:F",
            )
        )
    except HttpError:
        return {}

    rows = read_merchant_rows_from_values(result.get("values", []))
    return {
        row["merchant"]: {
            "include": row.get("include", True),
            "category": row.get("category"),
        }
        for row in rows
    }


def apply_existing_choices(
    merchant_rows: list[dict],
    choices: dict[str, dict],
) -> None:
    """Preserve Include/Category selections from a previous sheet version."""
    for row in merchant_rows:
        choice = choices.get(row["merchant"])
        if choice is None:
            continue
        row["include"] = choice.get("include", True)
        if choice.get("category"):
            row["category"] = display_category(choice["category"])


def update_merchant_table(
    sheets,
    spreadsheet_id: str,
    month_name: str,
    sheet_id: int,
) -> list[dict]:
    """Migrate an existing merchant table to the new A-F layout with Include/Category."""
    result = execute_with_retry(
        sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{month_name}'!A:F",
        )
    )
    merchant_rows = read_merchant_rows_from_values(result.get("values", []))

    for row in merchant_rows:
        if is_paynow_merchant(row["merchant"]):
            row["category"] = display_category("PayNow")
        elif not row.get("category"):
            row["category"] = categorize_merchant(row["merchant"]) or display_category("Other")
        else:
            row["category"] = display_category(row["category"])

    # Clear old merchant and category content so nothing from the old F:G layout remains.
    execute_with_retry(
        sheets.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"'{month_name}'!A1:I",
        )
    )

    # Unmerge existing cells so the new A1:F1 title merge can be applied cleanly.
    spreadsheet = get_spreadsheet(sheets, spreadsheet_id)
    unmerge_requests = [
        {"unmergeCells": {"range": merge}}
        for sheet in spreadsheet.get("sheets", [])
        if sheet["properties"]["sheetId"] == sheet_id
        for merge in sheet.get("merges", [])
    ]

    values = build_month_values(month_name, merchant_rows)
    execute_with_retry(
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{month_name}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
    )
    time.sleep(0.3)

    formatting = formatting_requests(sheet_id, merchant_rows)
    if unmerge_requests:
        formatting = unmerge_requests + formatting

    execute_with_retry(
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": formatting},
        )
    )
    time.sleep(0.3)

    return merchant_rows


def write_month_sheet(
    sheets,
    spreadsheet_id: str,
    month_name: str,
    transactions: list[dict],
    titles_to_ids: dict[str, int],
) -> None:
    merchant_rows = aggregate_by_merchant(transactions)
    sheet_id = ensure_month_sheet(sheets, spreadsheet_id, month_name, titles_to_ids)

    existing_choices = load_existing_merchant_choices(sheets, spreadsheet_id, month_name)
    apply_existing_choices(merchant_rows, existing_choices)

    values = build_month_values(month_name, merchant_rows)

    execute_with_retry(
        sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{month_name}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
    )
    time.sleep(0.5)

    clear_from_row = len(values) + 1
    execute_with_retry(
        sheets.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"'{month_name}'!A{clear_from_row}:F",
        )
    )

    execute_with_retry(
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": formatting_requests(sheet_id, merchant_rows)},
        )
    )
    time.sleep(0.5)

    write_category_section(sheets, spreadsheet_id, month_name, merchant_rows, sheet_id)


def delete_month_sheets_outside_year(
    sheets,
    spreadsheet_id: str,
    year: int,
    titles_to_ids: dict[str, int],
) -> list[str]:
    deleted: list[str] = []
    requests = []
    for title, sheet_id in list(titles_to_ids.items()):
        try:
            sheet_year = month_sort_key(title).year
        except ValueError:
            continue
        if sheet_year != year:
            requests.append({"deleteSheet": {"sheetId": sheet_id}})
            deleted.append(title)

    if requests:
        execute_with_retry(
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            )
        )
        for title in deleted:
            del titles_to_ids[title]

    return deleted


def sync_transactions_to_sheet(
    sheets,
    spreadsheet_id: str,
    transactions: list[dict],
    year: Optional[int] = None,
) -> dict[str, int]:
    by_month: dict[str, list[dict]] = defaultdict(list)
    for txn in transactions:
        by_month[txn["month"]].append(txn)

    spreadsheet = get_spreadsheet(sheets, spreadsheet_id)
    titles_to_ids = sheet_map(spreadsheet)

    if year is not None:
        delete_month_sheets_outside_year(sheets, spreadsheet_id, year, titles_to_ids)

    summary: dict[str, int] = {}
    for month_name in sorted(by_month, key=month_sort_key):
        month_transactions = by_month[month_name]
        write_month_sheet(sheets, spreadsheet_id, month_name, month_transactions, titles_to_ids)
        summary[month_name] = len(month_transactions)

    reorder_month_tabs(sheets, spreadsheet_id, list(by_month.keys()), titles_to_ids)
    return summary
