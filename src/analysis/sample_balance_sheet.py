"""
sample_balance_sheet.py
-----------------------
Realistic sample Balance Sheet data for both test businesses.

A Balance Sheet answers three questions:
  1. What does the business OWN?  (Assets)
  2. What does the business OWE?  (Liabilities)
  3. What is left for the owner?  (Equity = Assets - Liabilities)

The fundamental rule: Assets = Liabilities + Equity (always balances)
"""

# ---------------------------------------------------------------------------
# Client 1: Riverside Home Goods — retail store
# ---------------------------------------------------------------------------
RIVERSIDE_BALANCE_SHEET = {
    "business_name": "Riverside Home Goods",
    "as_of_date":    "April 30, 2025",

    "assets": {
        "current_assets": {
            "Cash & Bank Accounts":        48_200,
            "Accounts Receivable":          9_400,   # Money owed TO the business
            "Inventory":                   62_000,   # Products on hand
            "Prepaid Expenses":             2_100,   # E.g. prepaid insurance
        },
        "fixed_assets": {
            "Furniture & Fixtures":        18_500,
            "Equipment":                   12_000,
            "Less: Accumulated Depreciation": -8_400,  # Wear & tear over time
        },
        "other_assets": {
            "Security Deposits":            6_500,
        },
    },

    "liabilities": {
        "current_liabilities": {
            "Accounts Payable":            14_300,   # Bills owed to suppliers
            "Credit Card Balances":         5_800,
            "Accrued Payroll":              6_200,   # Wages earned but not yet paid
            "Sales Tax Payable":            2_900,
        },
        "long_term_liabilities": {
            "Business Loan":               28_000,
            "Equipment Financing":          7_200,
        },
    },

    "equity": {
        "Owner's Capital":                 55_000,
        "Retained Earnings":               36_800,   # Profit kept in the business
    },
}

# ---------------------------------------------------------------------------
# Client 2: Blue Oak Consulting — professional services
# ---------------------------------------------------------------------------
BLUE_OAK_BALANCE_SHEET = {
    "business_name": "Blue Oak Consulting",
    "as_of_date":    "April 30, 2025",

    "assets": {
        "current_assets": {
            "Cash & Bank Accounts":        92_500,
            "Accounts Receivable":         38_000,   # Unpaid client invoices
            "Unbilled Work in Progress":   14_200,   # Work done, not yet invoiced
            "Prepaid Expenses":             3_800,
        },
        "fixed_assets": {
            "Office Equipment":            11_200,
            "Computer Hardware":            8_400,
            "Less: Accumulated Depreciation": -6_100,
        },
        "other_assets": {
            "Security Deposits":            4_200,
        },
    },

    "liabilities": {
        "current_liabilities": {
            "Accounts Payable":             6_400,
            "Credit Card Balances":         3_100,
            "Accrued Payroll":             12_800,
            "Income Tax Payable":           8_500,
            "Deferred Revenue":             7_000,   # Paid in advance by clients
        },
        "long_term_liabilities": {
            "Business Line of Credit":     15_000,
        },
    },

    "equity": {
        "Owner's Capital":                 80_000,
        "Retained Earnings":               33_200,
    },
}

# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------
SAMPLE_BALANCE_SHEET_MAP = {
    "riverside_home_goods": RIVERSIDE_BALANCE_SHEET,
    "blue_oak_consulting":  BLUE_OAK_BALANCE_SHEET,
}

def get_sample_balance_sheet(client_id: str) -> dict:
    return SAMPLE_BALANCE_SHEET_MAP.get(client_id, RIVERSIDE_BALANCE_SHEET)
