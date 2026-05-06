"""
sample_data.py
--------------
Realistic fake P&L data for two sample businesses (3 months each).
Used to build and test the pipeline before connecting QuickBooks.
When QuickBooks is ready, this gets replaced by real data pulls.

get_sample_data(client_id) returns the right dataset for each client.
"""

# ---------------------------------------------------------------------------
# Client 1: Riverside Home Goods — retail store
# ---------------------------------------------------------------------------
RIVERSIDE_HOME_GOODS = {
    "business_name": "Riverside Home Goods",
    "currency": "USD",
    "months": {
        "February 2025": {
            "Sales - In Store":             38_500,
            "Sales - Online":               12_200,
            "Sales - Wholesale":             5_800,
            "Cost of Goods Sold":          -24_300,
            "Rent":                         -6_500,
            "Payroll":                     -11_200,
            "Utilities":                      -980,
            "Marketing & Advertising":      -1_400,
            "Software & Subscriptions":       -320,
            "Shipping & Postage":             -740,
            "Professional Fees":              -500,
            "Miscellaneous":                  -210,
        },
        "March 2025": {
            "Sales - In Store":             41_200,
            "Sales - Online":               15_800,
            "Sales - Wholesale":             6_100,
            "Cost of Goods Sold":          -26_800,
            "Rent":                         -6_500,
            "Payroll":                     -12_100,
            "Utilities":                      -870,
            "Marketing & Advertising":      -2_200,
            "Software & Subscriptions":       -320,
            "Shipping & Postage":             -910,
            "Professional Fees":                -0,
            "Miscellaneous":                  -340,
        },
        "April 2025": {
            "Sales - In Store":             44_800,
            "Sales - Online":               18_300,
            "Sales - Wholesale":             5_200,
            "Cost of Goods Sold":          -28_900,
            "Rent":                         -6_500,
            "Payroll":                     -12_800,
            "Utilities":                      -760,
            "Marketing & Advertising":      -3_100,
            "Software & Subscriptions":       -320,
            "Shipping & Postage":           -1_050,
            "Professional Fees":              -750,
            "Miscellaneous":                  -180,
        },
    }
}

# ---------------------------------------------------------------------------
# Client 2: Blue Oak Consulting — professional services firm
# ---------------------------------------------------------------------------
BLUE_OAK_CONSULTING = {
    "business_name": "Blue Oak Consulting",
    "currency": "USD",
    "months": {
        "February 2025": {
            "Consulting Fees - Strategy":   42_000,
            "Consulting Fees - Operations": 18_500,
            "Retainer Income":              12_000,
            "Cost of Services":            -19_800,
            "Rent & Office":                -3_200,
            "Payroll":                     -22_500,
            "Utilities":                      -310,
            "Marketing & Advertising":        -800,
            "Software & Subscriptions":       -940,
            "Travel & Entertainment":       -1_200,
            "Professional Fees":            -1_500,
            "Miscellaneous":                  -380,
        },
        "March 2025": {
            "Consulting Fees - Strategy":   38_000,
            "Consulting Fees - Operations": 22_000,
            "Retainer Income":              12_000,
            "Cost of Services":            -18_200,
            "Rent & Office":                -3_200,
            "Payroll":                     -22_500,
            "Utilities":                      -290,
            "Marketing & Advertising":      -1_200,
            "Software & Subscriptions":       -940,
            "Travel & Entertainment":       -2_800,
            "Professional Fees":                -0,
            "Miscellaneous":                  -220,
        },
        "April 2025": {
            "Consulting Fees - Strategy":   51_000,
            "Consulting Fees - Operations": 24_500,
            "Retainer Income":              14_000,
            "Cost of Services":            -23_100,
            "Rent & Office":                -3_200,
            "Payroll":                     -24_000,
            "Utilities":                      -275,
            "Marketing & Advertising":      -1_500,
            "Software & Subscriptions":       -940,
            "Travel & Entertainment":       -3_400,
            "Professional Fees":            -2_000,
            "Miscellaneous":                  -460,
        },
    }
}

# ---------------------------------------------------------------------------
# Lookup by client_id
# ---------------------------------------------------------------------------
SAMPLE_DATA_MAP = {
    "riverside_home_goods": RIVERSIDE_HOME_GOODS,
    "blue_oak_consulting":  BLUE_OAK_CONSULTING,
}

# Default (used by the original test script)
SAMPLE_PNL = RIVERSIDE_HOME_GOODS


def get_sample_data(client_id: str) -> dict:
    """
    Return sample P&L data for a given client_id.
    Falls back to Riverside Home Goods if client not found.
    """
    return SAMPLE_DATA_MAP.get(client_id, RIVERSIDE_HOME_GOODS)
