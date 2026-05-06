"""
data_pull.py
------------
Pulls financial reports from QuickBooks Online API.
Fetches the Profit & Loss report for a given month
and converts it into the same format as our sample data,
so the rest of the pipeline works without any changes.

Main function:
  get_pnl_data(client_id, year, month) -> dict
"""

import os
import pathlib
import requests
from dotenv import load_dotenv
from .auth import get_valid_access_token, get_company_id

# Resolve .env from the project root regardless of where Python is called from
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

ENVIRONMENT = os.getenv("QB_ENVIRONMENT", "sandbox")

BASE_URL = (
    "https://sandbox-quickbooks.api.intuit.com"
    if ENVIRONMENT == "sandbox"
    else "https://quickbooks.api.intuit.com"
)


# ---------------------------------------------------------------------------
# API request helper
# ---------------------------------------------------------------------------
def _qb_get(client_id: str, endpoint: str, params: dict = None) -> dict:
    """
    Make an authenticated GET request to the QuickBooks API.
    Handles token refresh automatically.
    """
    access_token = get_valid_access_token(client_id)
    company_id   = get_company_id(client_id)

    url = f"{BASE_URL}/v3/company/{company_id}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept":        "application/json",
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 401:
        # Token may have just expired — force a refresh and retry once
        from .auth import refresh_access_token
        access_token = refresh_access_token(client_id)
        headers["Authorization"] = f"Bearer {access_token}"
        response = requests.get(url, headers=headers, params=params)

    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Parse the QuickBooks P&L report into our standard format
# ---------------------------------------------------------------------------
def _parse_pnl_report(qb_report: dict, business_name: str,
                       month_label: str) -> dict:
    """
    QuickBooks returns P&L data as a nested tree of rows and columns.
    This function flattens it into a simple dict of {line_item: amount}.
    """
    line_items = {}

    def walk_rows(rows):
        """Recursively walk the report rows and extract amounts."""
        if not rows:
            return
        for row in rows:
            row_type = row.get("type", "")

            # A data row has a label and a value
            if row_type == "Data":
                cols = row.get("ColData", [])
                if len(cols) >= 2:
                    label  = cols[0].get("value", "").strip()
                    amount = cols[1].get("value", "0")
                    try:
                        val = float(amount.replace(",", ""))
                        if label:
                            line_items[label] = val
                    except (ValueError, AttributeError):
                        pass

            # A section contains nested rows
            if "Rows" in row:
                walk_rows(row["Rows"].get("Row", []))

    # The report has a top-level Rows object
    top_rows = qb_report.get("Rows", {}).get("Row", [])
    walk_rows(top_rows)

    return {
        "business_name": business_name,
        "currency":      "USD",
        "months": {
            month_label: line_items
        }
    }


# ---------------------------------------------------------------------------
# Main function — pull P&L for a specific month
# ---------------------------------------------------------------------------
def get_pnl_data(client_id: str, business_name: str,
                 year: int, month: int) -> dict:
    """
    Pull the Profit & Loss report from QuickBooks for a given month.

    Returns a dict in the same format as sample_data.py so the
    analyzer and PDF generator work without any changes.

    Example:
      data = get_pnl_data("riverside_home_goods", "Riverside Home Goods", 2025, 4)
    """
    import calendar

    # Format dates for the API (YYYY-MM-DD)
    last_day    = calendar.monthrange(year, month)[1]
    start_date  = f"{year}-{month:02d}-01"
    end_date    = f"{year}-{month:02d}-{last_day}"
    month_label = f"{calendar.month_name[month]} {year}"

    print(f"  Pulling P&L from QuickBooks: {month_label}...")

    report = _qb_get(
        client_id,
        "reports/ProfitAndLoss",
        params={
            "start_date":      start_date,
            "end_date":        end_date,
            "accounting_method": "Accrual",
        }
    )

    pnl_data = _parse_pnl_report(report, business_name, month_label)
    print(f"  Pulled {len(list(pnl_data['months'].values())[0])} line items.")

    return pnl_data


# ---------------------------------------------------------------------------
# Pull 3 months of P&L data (for trend analysis)
# ---------------------------------------------------------------------------
def get_pnl_last_3_months(client_id: str, business_name: str,
                           year: int, month: int) -> dict:
    """
    Pull 3 consecutive months of P&L and combine them into one dict
    so the analyzer can calculate month-over-month trends.

    month/year = the most recent month you want.
    """
    import calendar

    combined = {
        "business_name": business_name,
        "currency":      "USD",
        "months":        {}
    }

    for i in range(2, -1, -1):   # 2 months ago, 1 month ago, current month
        # Calculate the target month
        m = month - i
        y = year
        while m < 1:
            m += 12
            y -= 1

        month_data = get_pnl_data(client_id, business_name, y, m)
        month_label = list(month_data["months"].keys())[0]
        combined["months"][month_label] = month_data["months"][month_label]

    return combined


# ---------------------------------------------------------------------------
# Balance Sheet pull
# ---------------------------------------------------------------------------
def get_balance_sheet(client_id: str, business_name: str,
                      year: int, month: int) -> dict:
    """
    Pull the Balance Sheet from QuickBooks as of the last day of the given month.
    Returns a dict in the same format as sample_balance_sheet.py.
    """
    import calendar

    last_day = calendar.monthrange(year, month)[1]
    as_of    = f"{year}-{month:02d}-{last_day}"
    label    = f"{calendar.month_name[month]} {last_day}, {year}"

    print(f"  Pulling Balance Sheet from QuickBooks: as of {label}...")

    report = _qb_get(
        client_id,
        "reports/BalanceSheet",
        params={"date": as_of, "accounting_method": "Accrual"}
    )

    return _parse_balance_sheet(report, business_name, label)


def _parse_balance_sheet(qb_report: dict, business_name: str,
                          as_of_date: str) -> dict:
    """
    Parse QuickBooks BalanceSheet report into our standard format.
    QB returns a nested tree — we walk it and bucket items into
    assets, liabilities, and equity sections.
    """
    current_assets      = {}
    fixed_assets        = {}
    other_assets        = {}
    current_liabilities = {}
    long_term_liabilities = {}
    equity              = {}

    # Track which top-level section we're in
    current_section = None

    def walk(rows, depth=0):
        nonlocal current_section
        if not rows:
            return
        for row in rows:
            row_type = row.get("type", "")
            cols     = row.get("ColData", [])

            # Section headers tell us which bucket to use
            if row_type == "Section":
                header = row.get("Header", {})
                title  = header.get("ColData", [{}])[0].get("value", "").lower()
                if "current asset"  in title:  current_section = "current_assets"
                elif "fixed asset"  in title or "property" in title: current_section = "fixed_assets"
                elif "other asset"  in title:  current_section = "other_assets"
                elif "current liab" in title:  current_section = "current_liabilities"
                elif "long" in title and "liab" in title: current_section = "long_term_liabilities"
                elif "equity"       in title:  current_section = "equity"
                elif "asset"        in title:  current_section = "current_assets"
                elif "liabilit"     in title:  current_section = "current_liabilities"

            # Data rows have the actual values
            if row_type == "Data" and len(cols) >= 2:
                label  = cols[0].get("value", "").strip()
                amount = cols[1].get("value", "0").replace(",", "")
                try:
                    val = float(amount)
                    if label and current_section:
                        bucket = {
                            "current_assets":       current_assets,
                            "fixed_assets":         fixed_assets,
                            "other_assets":         other_assets,
                            "current_liabilities":  current_liabilities,
                            "long_term_liabilities": long_term_liabilities,
                            "equity":               equity,
                        }.get(current_section, current_assets)
                        bucket[label] = val
                except (ValueError, AttributeError):
                    pass

            # Recurse into nested rows
            if "Rows" in row:
                walk(row["Rows"].get("Row", []), depth + 1)

    top_rows = qb_report.get("Rows", {}).get("Row", [])
    walk(top_rows)

    return {
        "business_name": business_name,
        "as_of_date":    as_of_date,
        "assets": {
            "current_assets": current_assets or {"Cash": 0},
            "fixed_assets":   fixed_assets,
            "other_assets":   other_assets,
        },
        "liabilities": {
            "current_liabilities":    current_liabilities or {"Accounts Payable": 0},
            "long_term_liabilities":  long_term_liabilities,
        },
        "equity": equity or {"Owner Equity": 0},
    }


# ---------------------------------------------------------------------------
# Cash Flow Statement pull
# ---------------------------------------------------------------------------
def get_cash_flow(client_id: str, business_name: str,
                  year: int, month: int) -> dict:
    """
    Pull the Cash Flow Statement from QuickBooks for a given month.

    QuickBooks returns cash flow as a Statement of Cash Flows report,
    organized into three sections:
      - Operating Activities  (cash from running the business)
      - Investing Activities  (cash from buying/selling assets)
      - Financing Activities  (cash from loans, owner draws, etc.)

    Returns a dict in the same format as sample_cash_flow.py so the
    cash_flow_analyzer works without any changes.

    Example:
      cf = get_cash_flow("riverside_home_goods", "Riverside Home Goods", 2025, 4)
    """
    import calendar

    last_day   = calendar.monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date   = f"{year}-{month:02d}-{last_day}"
    label      = f"{calendar.month_name[month]} {year}"

    print(f"  Pulling Cash Flow Statement from QuickBooks: {label}...")

    report = _qb_get(
        client_id,
        "reports/CashFlow",
        params={
            "start_date": start_date,
            "end_date":   end_date,
        }
    )

    return _parse_cash_flow(report, business_name, label)


def _parse_cash_flow(qb_report: dict, business_name: str,
                     period_label: str) -> dict:
    """
    Parse QuickBooks CashFlow report into our standard format.

    QB returns three top-level sections:
      Operating, Investing, Financing.
    We walk the rows and bucket amounts accordingly.
    """
    operating   = {}
    investing   = {}
    financing   = {}
    current_sec = None

    _SEC_MAP = {
        "operating": "operating",
        "investing":  "investing",
        "financing":  "financing",
    }

    def walk(rows):
        nonlocal current_sec
        if not rows:
            return
        for row in rows:
            row_type = row.get("type", "")
            cols     = row.get("ColData", [])

            # Section headers — detect which activity section we're in
            if row_type == "Section":
                header = row.get("Header", {})
                title  = header.get("ColData", [{}])[0].get("value", "").lower()
                for key in _SEC_MAP:
                    if key in title:
                        current_sec = _SEC_MAP[key]
                        break

            # Data rows — extract label + amount
            if row_type == "Data" and len(cols) >= 2:
                label  = cols[0].get("value", "").strip()
                amount = cols[1].get("value", "0").replace(",", "")
                try:
                    val = float(amount)
                    if label and current_sec:
                        bucket = {
                            "operating": operating,
                            "investing":  investing,
                            "financing":  financing,
                        }.get(current_sec, operating)
                        bucket[label] = val
                except (ValueError, AttributeError):
                    pass

            # Recurse into nested rows
            if "Rows" in row:
                walk(row["Rows"].get("Row", []))

    top_rows = qb_report.get("Rows", {}).get("Row", [])
    walk(top_rows)

    return {
        "business_name":       business_name,
        "period":              period_label,
        "operating_activities": operating  or {"Net Income": 0},
        "investing_activities": investing,
        "financing_activities": financing,
    }
