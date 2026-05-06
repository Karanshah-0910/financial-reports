"""
cash_flow_analyzer.py
---------------------
Calculates cash flow metrics from P&L and Balance Sheet data.

WHAT IS CASH FLOW?
Cash flow answers the most important question in business:
"Is actual money coming in faster than it's going out?"

A business can be profitable on paper but still run out of cash.
(Example: You invoice a client for $50,000 but they pay in 60 days.
 You're "profitable" but you might not have cash to pay next week's payroll.)

METRICS CALCULATED:
------------------
Operating Cash Flow  = Net Profit + Non-Cash Expenses (Depreciation)
                       +/- Changes in Working Capital
                       (How much cash the core business actually generates)
                       This is the #1 health indicator for any business.

Free Cash Flow       = Operating Cash Flow - Capital Expenditures
                       (Cash left over AFTER investing in equipment/growth)
                       Positive = business is self-funding its growth.
                       Negative = needs outside funding to grow.

Cash Runway          = Current Cash Balance / Monthly Burn Rate
                       (How many months can the business survive on current cash?)
                       Above 6 months = comfortable | Below 3 months = urgent

Burn Rate            = Average monthly cash spent vs cash earned
                       (Only relevant if the business is cash-flow negative)
                       Tells you how fast you're burning through reserves.

Cash Conversion Cycle = AR Days + Inventory Days - AP Days
                        (How many days between paying for inventory and collecting
                        payment from customers — lower is better)
"""


def analyze_cash_flow(pnl_analysis: dict, bs_analysis: dict,
                       cf_data: dict = None) -> dict:
    """
    Derives cash flow metrics from P&L analysis + Balance Sheet.

    pnl_analysis : output of run_analysis() from analyzer.py
    bs_analysis  : output of analyze_balance_sheet()
    cf_data      : optional extra cash flow items (capex, financing)
                   from sample_cash_flow.py or QuickBooks

    Returns a structured dict with all cash flow metrics.
    """
    summary      = pnl_analysis["summary_df"]
    latest_month = pnl_analysis["latest_month"]
    all_months   = pnl_analysis["all_months"]

    # Pull key numbers from P&L
    net_profit     = float(summary.loc["Net Profit",      latest_month])
    total_revenue  = float(summary.loc["Total Revenue",   latest_month])
    total_expenses = float(summary.loc["Total Expenses",  latest_month])

    # Pull balance sheet items
    cash_balance   = _find_cash(bs_analysis)
    working_cap    = bs_analysis.get("working_capital", 0)
    ar_balance     = bs_analysis.get("ar_balance", 0)
    ap_balance     = bs_analysis.get("ap_balance", 0)

    # Pull optional cash flow specific items
    capex          = float((cf_data or {}).get("capital_expenditures",  0))
    depreciation   = float((cf_data or {}).get("depreciation",          0))
    ar_change      = float((cf_data or {}).get("ar_change",             0))
    inventory_change = float((cf_data or {}).get("inventory_change",    0))
    ap_change      = float((cf_data or {}).get("ap_change",             0))
    loan_proceeds  = float((cf_data or {}).get("loan_proceeds",         0))
    loan_repayments = float((cf_data or {}).get("loan_repayments",      0))
    owner_drawings = float((cf_data or {}).get("owner_drawings",        0))

    # -----------------------------------------------------------------------
    # Operating Cash Flow
    # = Net Profit + Depreciation (add back non-cash expense)
    # + Decrease in AR (collected more cash from customers)
    # - Increase in Inventory (paid for more stock)
    # + Increase in AP (delayed paying suppliers = keeps cash longer)
    # -----------------------------------------------------------------------
    operating_cash_flow = (
        net_profit
        + depreciation          # Non-cash expense — add it back
        - ar_change             # AR going up = less cash collected (negative)
        - inventory_change      # More inventory = cash spent (negative)
        + ap_change             # AP going up = delayed payments (positive)
    )

    # If no CF data provided, use a simplified estimate
    if cf_data is None:
        # Simple estimate: OCF ≈ Net Profit + estimated depreciation
        estimated_depreciation = total_expenses * 0.03   # ~3% of expenses
        operating_cash_flow    = net_profit + estimated_depreciation

    # -----------------------------------------------------------------------
    # Free Cash Flow = Operating Cash Flow minus Capital Expenditures
    # Capital Expenditures = money spent on equipment, property, etc.
    # -----------------------------------------------------------------------
    free_cash_flow = operating_cash_flow - capex

    # -----------------------------------------------------------------------
    # Financing Cash Flow = money from loans minus repayments minus drawings
    # -----------------------------------------------------------------------
    financing_cash_flow = loan_proceeds - loan_repayments - owner_drawings

    # -----------------------------------------------------------------------
    # Net Cash Change = all three sections combined
    # -----------------------------------------------------------------------
    net_cash_change = operating_cash_flow - capex + financing_cash_flow

    # -----------------------------------------------------------------------
    # Burn Rate & Cash Runway
    # Burn Rate = monthly cash outflow (only meaningful if net negative)
    # Cash Runway = how many months of expenses current cash covers
    # -----------------------------------------------------------------------
    monthly_burn = total_expenses   # Simplified: total monthly operating costs

    cash_runway = None
    if monthly_burn > 0 and cash_balance > 0:
        cash_runway = round(cash_balance / monthly_burn, 1)

    # Is the business cash-flow positive or negative?
    is_cash_positive = operating_cash_flow > 0

    # -----------------------------------------------------------------------
    # Cash Conversion Cycle
    # How long between paying for inventory and collecting from customers?
    # Lower = better (faster cash cycle)
    # -----------------------------------------------------------------------
    ar_days        = bs_analysis.get("ar_days") or 0
    ap_days        = bs_analysis.get("ap_days") or 0
    inventory_days = _estimate_inventory_days(bs_analysis, pnl_analysis, latest_month)
    cash_conversion_cycle = ar_days + inventory_days - ap_days

    # -----------------------------------------------------------------------
    # Month-over-month OCF trend (if 3 months available)
    # -----------------------------------------------------------------------
    ocf_trend = _calculate_ocf_trend(pnl_analysis)

    # -----------------------------------------------------------------------
    # Health scores
    # -----------------------------------------------------------------------
    def score_runway(r):
        if r is None:   return "grey"
        if r >= 6:      return "green"
        if r >= 3:      return "yellow"
        return "red"

    def score_ocf(ocf):
        if ocf > 0:     return "green"
        if ocf > -5000: return "yellow"
        return "red"

    def score_fcf(fcf):
        if fcf > 0:     return "green"
        if fcf > -10000: return "yellow"
        return "red"

    def score_ccc(ccc):
        if ccc <= 30:   return "green"
        if ccc <= 60:   return "yellow"
        return "red"

    return {
        "latest_month":           latest_month,
        "business_name":          pnl_analysis.get("business_name", ""),

        # Core cash flow metrics
        "operating_cash_flow":    round(operating_cash_flow,    2),
        "free_cash_flow":         round(free_cash_flow,         2),
        "financing_cash_flow":    round(financing_cash_flow,    2),
        "net_cash_change":        round(net_cash_change,        2),

        # Cash position
        "cash_balance":           round(cash_balance,           2),
        "cash_runway_months":     cash_runway,
        "monthly_burn_rate":      round(monthly_burn,           2),
        "is_cash_positive":       is_cash_positive,

        # Efficiency
        "cash_conversion_cycle":  round(cash_conversion_cycle,  1),
        "inventory_days":         round(inventory_days,          1),

        # Components (for transparency)
        "net_profit":             round(net_profit,             2),
        "depreciation":           round(depreciation,           2),
        "capex":                  round(capex,                  2),

        # Trend
        "ocf_trend":              ocf_trend,

        # Health scores
        "health": {
            "operating_cash_flow":    score_ocf(operating_cash_flow),
            "free_cash_flow":         score_fcf(free_cash_flow),
            "cash_runway":            score_runway(cash_runway),
            "cash_conversion_cycle":  score_ccc(cash_conversion_cycle),
        },
    }


def _find_cash(bs_analysis: dict) -> float:
    """Find the cash balance from the balance sheet current assets."""
    for k, v in bs_analysis.get("current_assets", {}).items():
        if any(word in k.lower() for word in ["cash", "bank"]):
            return float(v)
    return 0.0


def _estimate_inventory_days(bs_analysis: dict, pnl_analysis: dict,
                               latest_month: str) -> float:
    """
    Estimate how many days of inventory is held.
    Formula: (Inventory Value / Monthly COGS) * 30
    Only relevant for product-based businesses.
    """
    inventory = sum(
        float(v) for k, v in bs_analysis.get("current_assets", {}).items()
        if "inventory" in k.lower() or "stock" in k.lower()
    )
    if not inventory:
        return 0.0

    try:
        monthly_cogs = float(pnl_analysis["summary_df"].loc["Cost of Goods Sold", latest_month])
        if monthly_cogs > 0:
            return round((inventory / monthly_cogs) * 30, 1)
    except Exception:
        pass
    return 0.0


def _calculate_ocf_trend(pnl_analysis: dict) -> list:
    """
    Estimate operating cash flow for each month in the dataset.
    Returns a list of (month, estimated_ocf) tuples for the trend chart.
    """
    summary    = pnl_analysis["summary_df"]
    months     = pnl_analysis["all_months"]
    trend      = []

    for month in months:
        try:
            net_profit     = float(summary.loc["Net Profit",     month])
            total_expenses = float(summary.loc["Total Expenses", month])
            est_depreciation = total_expenses * 0.03
            estimated_ocf  = net_profit + est_depreciation
            trend.append({"month": month, "ocf": round(estimated_ocf, 2)})
        except Exception:
            trend.append({"month": month, "ocf": 0})

    return trend


def format_cf_for_claude(cf: dict) -> str:
    """Format cash flow analysis as clean text for Claude."""
    runway_text = f"{cf['cash_runway_months']} months" if cf['cash_runway_months'] else "N/A"
    lines = [
        "=== CASH FLOW SUMMARY ===",
        f"Period: {cf['latest_month']}",
        "",
        f"Operating Cash Flow:   ${cf['operating_cash_flow']:>12,.0f}",
        f"  (Net Profit:         ${cf['net_profit']:>12,.0f})",
        f"  (Depreciation add-back: ${cf['depreciation']:>9,.0f})",
        f"Capital Expenditures:  ${cf['capex']:>12,.0f}",
        f"Free Cash Flow:        ${cf['free_cash_flow']:>12,.0f}",
        "",
        f"Current Cash Balance:  ${cf['cash_balance']:>12,.0f}",
        f"Monthly Burn Rate:     ${cf['monthly_burn_rate']:>12,.0f}",
        f"Cash Runway:           {runway_text:>13}",
        f"Cash Conversion Cycle: {cf['cash_conversion_cycle']:>10.1f} days",
        "",
        f"Status: {'Cash Flow POSITIVE' if cf['is_cash_positive'] else 'Cash Flow NEGATIVE'}",
    ]
    return "\n".join(lines)
