"""
analyzer.py
-----------
Takes raw P&L data and calculates every metric a small business
owner and their advisor need to understand the business:

  BASIC METRICS (calculated every month)
  - Total Revenue, COGS, Gross Profit, Total Expenses, Net Profit
  - Gross Margin % and Net Margin %
  - Operating Margin %

  TREND METRICS (comparing months to each other)
  - Month-over-month (MoM) change % for every summary metric
  - Expense growth rate (are costs rising faster than revenue?)
  - Top 5 biggest expense categories for the latest month

  FLAGS (automatic alerts)
  - Any line item that changed more than 20% vs last month
    gets flagged as "needs attention" so nothing slips through

Plain-English note on each metric is included in comments below.
"""

import pandas as pd


# ---------------------------------------------------------------------------
# Line item categories
# These tell the analyzer which rows belong to Revenue, COGS, and Expenses.
# When you connect QuickBooks, add any new account names here.
# ---------------------------------------------------------------------------

REVENUE_LINES = [
    # Retail / e-commerce
    "Sales - In Store",
    "Sales - Online",
    "Sales - Wholesale",
    # Professional services
    "Consulting Fees - Strategy",
    "Consulting Fees - Operations",
    "Retainer Income",
    # Generic fallbacks (QuickBooks often uses these)
    "Sales",
    "Revenue",
    "Income",
    "Service Revenue",
    "Product Revenue",
]

COGS_LINES = [
    # Cost of Goods Sold = what you paid for the products you sold
    "Cost of Goods Sold",
    "Cost of Sales",
    "Cost of Services",    # Used by service businesses
    "Direct Labor",
    "Direct Materials",
]

EXPENSE_LINES = [
    # Operating expenses = the cost of running the business day-to-day
    "Rent",
    "Rent & Office",
    "Payroll",
    "Salaries & Wages",
    "Utilities",
    "Marketing & Advertising",
    "Advertising",
    "Software & Subscriptions",
    "Shipping & Postage",
    "Professional Fees",
    "Travel & Entertainment",
    "Insurance",
    "Depreciation",
    "Miscellaneous",
    "Other Expenses",
]


# ---------------------------------------------------------------------------
# Step 1: Build a clean DataFrame from raw P&L data
# ---------------------------------------------------------------------------
def build_dataframe(pnl_data: dict) -> pd.DataFrame:
    """
    Turns the raw P&L dictionary (from QuickBooks or sample data)
    into a tidy pandas table.
    Rows = individual line items (e.g. "Payroll", "Sales - Online")
    Columns = months (e.g. "February 2025", "March 2025")
    Missing values are filled with 0.
    """
    months = pnl_data["months"]
    df     = pd.DataFrame(months)
    df     = df.fillna(0)
    return df


# ---------------------------------------------------------------------------
# Step 2: Calculate summary totals for each month
# ---------------------------------------------------------------------------
def calculate_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rolls up every line item into 8 key summary metrics per month.

    GROSS PROFIT   = Revenue minus the direct cost of products/services
                     (what's left before paying overhead)
    GROSS MARGIN % = Gross Profit as a % of Revenue
                     (e.g. 45% means you keep 45 cents of every sales dollar)
    OPERATING MARGIN = Net Profit / Revenue after all operating costs
                     (the true measure of how efficiently the business runs)
    NET PROFIT     = What the business actually keeps after ALL costs
    NET MARGIN %   = Net Profit as a % of Revenue
    """
    summary = {}

    for month in df.columns:
        col = df[month]

        # Revenue: all income-generating line items (positive values)
        total_revenue = col[col.index.isin(REVENUE_LINES)].sum()

        # Also pick up any QB line items not in our list but with positive values
        # that aren't in COGS or EXPENSE lists (catches unknown revenue accounts)
        known_items = set(REVENUE_LINES + COGS_LINES + EXPENSE_LINES)
        unknown_positive = col[
            (~col.index.isin(known_items)) & (col > 0)
        ].sum()
        total_revenue += unknown_positive

        # COGS: direct cost of delivering the product/service (make positive)
        total_cogs = abs(col[col.index.isin(COGS_LINES)].sum())

        # Gross Profit: Revenue minus COGS
        # (This is what's left BEFORE paying for rent, staff, marketing etc.)
        gross_profit = total_revenue - total_cogs

        # Gross Margin: How much of every sales dollar remains after product costs
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue else 0

        # Operating Expenses: the cost of running the business
        total_expenses = abs(col[col.index.isin(EXPENSE_LINES)].sum())

        # Also pick up unknown negative values (expense accounts not in our list)
        unknown_negative = abs(col[
            (~col.index.isin(known_items)) & (col < 0)
        ].sum())
        total_expenses += unknown_negative

        # Operating Margin: Net Profit / Revenue
        # (Measures how efficiently the business converts sales to profit)
        net_profit      = gross_profit - total_expenses
        operating_margin = (net_profit / total_revenue * 100) if total_revenue else 0
        net_margin       = operating_margin   # Same thing here (no interest/tax)

        summary[month] = {
            "Total Revenue":        round(total_revenue,   2),
            "Cost of Goods Sold":   round(total_cogs,      2),
            "Gross Profit":         round(gross_profit,    2),
            "Gross Margin %":       round(gross_margin,    1),
            "Total Expenses":       round(total_expenses,  2),
            "Operating Margin %":   round(operating_margin, 1),
            "Net Profit":           round(net_profit,      2),
            "Net Margin %":         round(net_margin,      1),
        }

    return pd.DataFrame(summary)


# ---------------------------------------------------------------------------
# Step 3: Month-over-month % changes
# ---------------------------------------------------------------------------
def calculate_mom_changes(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each summary metric, calculates how much it changed vs the
    previous month as a percentage.

    Example: Revenue was $40,000 in Feb and $44,000 in March
             → MoM change = +10%

    First month always shows NaN (no previous month to compare to).
    """
    mom = summary_df.T.pct_change() * 100   # Transpose so months are rows
    mom = mom.T.round(1)                     # Transpose back, round to 1dp
    return mom


# ---------------------------------------------------------------------------
# Step 4: Top 5 expense categories for the latest month
# ---------------------------------------------------------------------------
def get_top_expenses(detail_df: pd.DataFrame, latest_month: str,
                     top_n: int = 5) -> list:
    """
    Returns the top N expense categories by dollar amount for the latest month.
    Helps identify where most of the money is going.

    Returns a list of dicts: [{"name": "Payroll", "amount": 12800, "pct": 52.1}, ...]
    """
    all_expense_names = EXPENSE_LINES + COGS_LINES
    expenses = {}

    for item in all_expense_names:
        if item in detail_df.index:
            val = abs(float(detail_df.loc[item, latest_month]))
            if val > 0:
                expenses[item] = val

    # Also catch any unknown negative items (QB accounts not in our list)
    known = set(REVENUE_LINES + COGS_LINES + EXPENSE_LINES)
    for idx in detail_df.index:
        if idx not in known:
            val = float(detail_df.loc[idx, latest_month])
            if val < 0:
                expenses[idx] = abs(val)

    if not expenses:
        return []

    total = sum(expenses.values())
    sorted_expenses = sorted(expenses.items(), key=lambda x: x[1], reverse=True)

    return [
        {
            "name":   name,
            "amount": round(amount, 2),
            "pct":    round(amount / total * 100, 1) if total else 0,
        }
        for name, amount in sorted_expenses[:top_n]
    ]


# ---------------------------------------------------------------------------
# Step 5: Expense growth rate
# ---------------------------------------------------------------------------
def get_expense_growth_rate(summary_df: pd.DataFrame) -> dict:
    """
    Compares total expenses in the latest month vs the first month.
    Also compares expense growth to revenue growth.

    WHY THIS MATTERS: If expenses are growing faster than revenue,
    profit margins will shrink over time — even if revenue is rising.

    Returns a dict with:
      - expense_growth_pct : % change in total expenses (first vs latest month)
      - revenue_growth_pct : % change in total revenue
      - verdict            : "Expenses growing faster than revenue" or "Healthy"
    """
    months = list(summary_df.columns)
    if len(months) < 2:
        return {"expense_growth_pct": None, "revenue_growth_pct": None,
                "verdict": "Not enough data"}

    first  = months[0]
    latest = months[-1]

    rev_first  = float(summary_df.loc["Total Revenue",   first])
    rev_latest = float(summary_df.loc["Total Revenue",   latest])
    exp_first  = float(summary_df.loc["Total Expenses",  first])
    exp_latest = float(summary_df.loc["Total Expenses",  latest])

    rev_growth = ((rev_latest - rev_first) / rev_first * 100) if rev_first else 0
    exp_growth = ((exp_latest - exp_first) / exp_first * 100) if exp_first else 0

    if exp_growth > rev_growth + 5:
        verdict = "Warning: Expenses growing faster than revenue"
    elif exp_growth > rev_growth:
        verdict = "Watch: Expenses keeping pace with revenue"
    else:
        verdict = "Healthy: Revenue growing faster than expenses"

    return {
        "expense_growth_pct": round(exp_growth, 1),
        "revenue_growth_pct": round(rev_growth, 1),
        "verdict":            verdict,
    }


# ---------------------------------------------------------------------------
# Step 6: Flag line items that changed more than 20% MoM
# ---------------------------------------------------------------------------
def get_attention_flags(detail_df: pd.DataFrame,
                        threshold_pct: float = 20.0) -> list:
    """
    Scans every line item and flags any that changed by more than
    the threshold % compared to the previous month.

    WHY THIS MATTERS: A 25% jump in utilities or a 30% drop in
    online sales could indicate a problem — or an opportunity.
    These flags make sure nothing slips through unnoticed.

    Returns a list of dicts: [
      {"item": "Marketing", "prev": 1400, "current": 3100,
       "change_pct": 121.4, "direction": "up"}, ...
    ]
    """
    months = list(detail_df.columns)
    if len(months) < 2:
        return []

    prev_month    = months[-2]
    latest_month  = months[-1]
    flags         = []

    for item in detail_df.index:
        prev    = float(detail_df.loc[item, prev_month])
        current = float(detail_df.loc[item, latest_month])

        # Skip items with zero in both months
        if prev == 0 and current == 0:
            continue

        # Calculate % change (handle division by zero)
        if prev == 0:
            change_pct = 100.0
        else:
            change_pct = ((current - prev) / abs(prev)) * 100

        if abs(change_pct) >= threshold_pct:
            flags.append({
                "item":       item,
                "prev":       round(abs(prev),    2),
                "current":    round(abs(current), 2),
                "change_pct": round(change_pct,   1),
                "direction":  "up" if change_pct > 0 else "down",
            })

    # Sort by absolute change size — biggest surprises first
    flags.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return flags


# ---------------------------------------------------------------------------
# Main function — runs everything and returns one clean dict
# ---------------------------------------------------------------------------
def run_analysis(pnl_data: dict) -> dict:
    """
    Call this with raw P&L data and get back everything:

    Returns a dict with:
      detail_df        : every line item, every month (pandas DataFrame)
      summary_df       : 8 key summary metrics per month (pandas DataFrame)
      mom_df           : month-over-month % changes (pandas DataFrame)
      top_expenses     : top 5 expenses for the latest month (list)
      expense_growth   : expense vs revenue growth trend (dict)
      attention_flags  : line items that changed >20% MoM (list)
      latest_month     : name of the most recent month (string)
      all_months       : list of all month names (list)
      business_name    : name of the business (string)
      currency         : currency code, e.g. "USD" (string)
    """
    detail_df  = build_dataframe(pnl_data)
    summary_df = calculate_summary(detail_df)
    mom_df     = calculate_mom_changes(summary_df)

    latest_month   = list(pnl_data["months"].keys())[-1]
    top_expenses   = get_top_expenses(detail_df, latest_month)
    expense_growth = get_expense_growth_rate(summary_df)
    flags          = get_attention_flags(detail_df)

    return {
        "business_name":   pnl_data.get("business_name", "Client"),
        "currency":        pnl_data.get("currency", "USD"),
        "latest_month":    latest_month,
        "all_months":      list(pnl_data["months"].keys()),
        "detail_df":       detail_df,
        "summary_df":      summary_df,
        "mom_df":          mom_df,
        "top_expenses":    top_expenses,
        "expense_growth":  expense_growth,
        "attention_flags": flags,
    }
