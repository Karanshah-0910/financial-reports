"""
balance_sheet_analyzer.py
--------------------------
Takes raw balance sheet data and calculates everything a business
owner and advisor need to understand the financial health of the business.

WHAT IS A BALANCE SHEET?
Think of it as a photograph of the business on one specific day.
It answers three questions:
  1. What does the business OWN?   → Assets
  2. What does the business OWE?   → Liabilities
  3. What belongs to the owner?    → Equity (Assets minus Liabilities)

The golden rule: Assets ALWAYS = Liabilities + Equity

METRICS CALCULATED:
------------------
Current Ratio      = Current Assets / Current Liabilities
                     (Can we pay our bills due in the next 12 months?)
                     Above 1.5 = healthy | Below 1.0 = potential cash crisis

Quick Ratio        = (Cash + Receivables) / Current Liabilities
                     (Can we pay bills WITHOUT selling inventory?)
                     Above 1.0 = safe | Below 0.7 = tight

Debt-to-Equity     = Total Liabilities / Total Equity
                     (For every $1 the owner has invested, how much is owed?)
                     Below 0.5 = conservative | Above 1.0 = highly leveraged

Working Capital    = Current Assets - Current Liabilities
                     (The day-to-day financial cushion)
                     Positive = good | Negative = danger zone

AR Days Outstanding = (Accounts Receivable / Monthly Revenue) * 30
                     (How many days on average to collect payment from customers)
                     Lower = better. Above 45 days = worth investigating.

AP Days Outstanding = (Accounts Payable / Monthly COGS) * 30
                     (How many days before we pay our suppliers)
                     Higher gives more cash flexibility, but too high strains relationships.
"""


def _sum_section(section: dict) -> float:
    """Add up all values in a balance sheet section."""
    return sum(float(v) for v in section.values())


def analyze_balance_sheet(bs: dict, monthly_revenue: float = 0,
                           monthly_cogs: float = 0) -> dict:
    """
    Main function — call this with raw balance sheet data.

    bs              : raw balance sheet dict (from sample or QuickBooks)
    monthly_revenue : total revenue for the month (used to calculate AR days)
    monthly_cogs    : cost of goods sold for the month (used to calculate AP days)

    Returns a structured dict with all totals, ratios, and health scores.
    """
    assets      = bs.get("assets",      {})
    liabilities = bs.get("liabilities", {})
    equity      = bs.get("equity",      {})

    # -----------------------------------------------------------------------
    # Section totals
    # -----------------------------------------------------------------------
    current_assets_items   = assets.get("current_assets",   {})
    fixed_assets_items     = assets.get("fixed_assets",     {})
    other_assets_items     = assets.get("other_assets",     {})

    current_assets         = _sum_section(current_assets_items)
    fixed_assets           = _sum_section(fixed_assets_items)
    other_assets           = _sum_section(other_assets_items)
    total_assets           = current_assets + fixed_assets + other_assets

    current_liab_items     = liabilities.get("current_liabilities",   {})
    long_term_liab_items   = liabilities.get("long_term_liabilities",  {})

    current_liabilities    = _sum_section(current_liab_items)
    long_term_liabilities  = _sum_section(long_term_liab_items)
    total_liabilities      = current_liabilities + long_term_liabilities

    total_equity           = _sum_section(equity)
    working_capital        = current_assets - current_liabilities

    # -----------------------------------------------------------------------
    # Liquidity Ratios
    # -----------------------------------------------------------------------

    # Current Ratio: can we pay short-term bills?
    current_ratio = (
        round(current_assets / current_liabilities, 2)
        if current_liabilities else None
    )

    # Quick Ratio: can we pay bills using only cash + receivables (no inventory)?
    # We identify liquid assets by looking for "cash", "bank", or "receivable" in the name
    liquid_assets = sum(
        float(v) for k, v in current_assets_items.items()
        if any(word in k.lower() for word in ["cash", "bank", "receivable"])
    )
    quick_ratio = (
        round(liquid_assets / current_liabilities, 2)
        if current_liabilities else None
    )

    # -----------------------------------------------------------------------
    # Leverage Ratio
    # -----------------------------------------------------------------------

    # Debt-to-Equity: how much debt vs owner investment?
    debt_to_equity = (
        round(total_liabilities / total_equity, 2)
        if total_equity else None
    )

    # -----------------------------------------------------------------------
    # Efficiency Ratios (AR Days & AP Days)
    # -----------------------------------------------------------------------

    # AR Days Outstanding: how long does it take to collect customer payments?
    # Formula: (Accounts Receivable balance / Monthly Revenue) * 30 days
    ar_balance = sum(
        float(v) for k, v in current_assets_items.items()
        if "receivable" in k.lower()
    )
    ar_days = (
        round((ar_balance / monthly_revenue) * 30, 1)
        if monthly_revenue and ar_balance else None
    )

    # AP Days Outstanding: how long before we pay our suppliers?
    # Formula: (Accounts Payable balance / Monthly COGS) * 30 days
    ap_balance = sum(
        float(v) for k, v in current_liab_items.items()
        if "payable" in k.lower() and "tax" not in k.lower() and "payroll" not in k.lower()
    )
    ap_days = (
        round((ap_balance / monthly_cogs) * 30, 1)
        if monthly_cogs and ap_balance else None
    )

    # -----------------------------------------------------------------------
    # Health scores — traffic light system for each ratio
    # -----------------------------------------------------------------------
    def score_current_ratio(r):
        if r is None:    return "grey"
        if r >= 1.5:     return "green"
        if r >= 1.0:     return "yellow"
        return "red"

    def score_quick_ratio(r):
        if r is None:    return "grey"
        if r >= 1.0:     return "green"
        if r >= 0.7:     return "yellow"
        return "red"

    def score_debt_equity(r):
        if r is None:    return "grey"
        if r <= 0.5:     return "green"
        if r <= 1.0:     return "yellow"
        return "red"

    def score_working_capital(wc):
        if wc > 10_000:  return "green"
        if wc >= 0:      return "yellow"
        return "red"

    def score_ar_days(d):
        if d is None:    return "grey"
        if d <= 30:      return "green"
        if d <= 45:      return "yellow"
        return "red"

    def score_ap_days(d):
        if d is None:    return "grey"
        if d >= 30:      return "green"   # Longer AP days = using supplier credit well
        if d >= 15:      return "yellow"
        return "red"

    return {
        "business_name":   bs.get("business_name", ""),
        "as_of_date":      bs.get("as_of_date", ""),

        # Raw sections (for the detail table in the PDF)
        "current_assets":           current_assets_items,
        "fixed_assets":             fixed_assets_items,
        "other_assets":             other_assets_items,
        "current_liabilities":      current_liab_items,
        "long_term_liabilities":    long_term_liab_items,
        "equity":                   equity,

        # Totals
        "total_current_assets":        round(current_assets,        2),
        "total_fixed_assets":          round(fixed_assets,          2),
        "total_other_assets":          round(other_assets,          2),
        "total_assets":                round(total_assets,          2),
        "total_current_liabilities":   round(current_liabilities,   2),
        "total_long_term_liabilities": round(long_term_liabilities, 2),
        "total_liabilities":           round(total_liabilities,     2),
        "total_equity":                round(total_equity,          2),
        "working_capital":             round(working_capital,       2),

        # Ratios
        "current_ratio":    current_ratio,
        "quick_ratio":      quick_ratio,
        "debt_to_equity":   debt_to_equity,
        "ar_days":          ar_days,
        "ap_days":          ap_days,
        "ar_balance":       round(ar_balance, 2),
        "ap_balance":       round(ap_balance, 2),

        # Health scores (green / yellow / red / grey)
        "health": {
            "current_ratio":    score_current_ratio(current_ratio),
            "quick_ratio":      score_quick_ratio(quick_ratio),
            "debt_to_equity":   score_debt_equity(debt_to_equity),
            "working_capital":  score_working_capital(working_capital),
            "ar_days":          score_ar_days(ar_days),
            "ap_days":          score_ap_days(ap_days),
        },
    }


def format_bs_for_claude(bs: dict) -> str:
    """Format balance sheet analysis as clean text for Claude to read."""
    lines = [
        "=== BALANCE SHEET SUMMARY ===",
        f"As of: {bs['as_of_date']}",
        "",
        f"Total Assets:              ${bs['total_assets']:>12,.0f}",
        f"  Current Assets:          ${bs['total_current_assets']:>12,.0f}",
        f"  Fixed Assets:            ${bs['total_fixed_assets']:>12,.0f}",
        "",
        f"Total Liabilities:         ${bs['total_liabilities']:>12,.0f}",
        f"  Current Liabilities:     ${bs['total_current_liabilities']:>12,.0f}",
        f"  Long-term Liabilities:   ${bs['total_long_term_liabilities']:>12,.0f}",
        "",
        f"Total Equity:              ${bs['total_equity']:>12,.0f}",
        f"Working Capital:           ${bs['working_capital']:>12,.0f}",
        "",
        "=== KEY RATIOS ===",
        f"Current Ratio:     {bs['current_ratio']}   (healthy = above 1.5)",
        f"Quick Ratio:       {bs['quick_ratio']}   (healthy = above 1.0)",
        f"Debt-to-Equity:    {bs['debt_to_equity']}   (healthy = below 1.0)",
        f"AR Days:           {bs['ar_days']} days   (healthy = below 30 days)",
        f"AP Days:           {bs['ap_days']} days   (healthy = above 30 days)",
    ]
    return "\n".join(lines)
