"""
sample_cash_flow.py
-------------------
Realistic sample cash flow supplement data for both demo clients.

This fills in the items that DON'T appear directly on the P&L or Balance Sheet
but are needed to calculate a proper cash flow statement:

  capital_expenditures : Money spent on equipment, furniture, computers, etc.
                         This is NOT an expense on the P&L — it's an investment.
                         (The P&L only sees the depreciation each month.)

  depreciation         : The monthly "wear and tear" charge on assets already owned.
                         It's an expense on the P&L but NOT a real cash outflow.
                         We ADD it back to get the true cash picture.

  ar_change            : Did Accounts Receivable (money customers owe us) go UP or DOWN?
                         UP = customers are paying slower = LESS cash collected this month.
                         DOWN = customers paid off old invoices = MORE cash collected.

  inventory_change     : Did inventory go UP or DOWN?
                         UP = we bought more stock = cash SPENT.
                         DOWN = we sold from existing stock = cash SAVED.

  ap_change            : Did Accounts Payable (bills we owe suppliers) go UP or DOWN?
                         UP = we're delaying payments to suppliers = KEEPING more cash.
                         DOWN = we paid suppliers = cash SPENT.

  loan_proceeds        : New loans or credit line draws this month.
  loan_repayments      : Regular loan principal payments.
  owner_drawings       : Cash the owner took out of the business for personal use.
"""


# ---------------------------------------------------------------------------
# Riverside Home Goods — Retail store (product-based business)
# Has inventory, slower AR (wholesale accounts), active CapEx
# ---------------------------------------------------------------------------
RIVERSIDE_CF = {
    # Investing Activities
    "capital_expenditures":  3500,    # New store display fixtures purchased
    "depreciation":          820,     # Monthly depreciation on shelving, POS system, van

    # Working Capital changes (vs previous month)
    "ar_change":             1200,    # AR went UP $1,200 — wholesale customers paying slower
    "inventory_change":      2800,    # Bought $2,800 more stock to prepare for season
    "ap_change":             1500,    # AP went UP $1,500 — delayed some supplier payments

    # Financing Activities
    "loan_proceeds":         0,       # No new borrowing this month
    "loan_repayments":       1250,    # Monthly equipment loan payment
    "owner_drawings":        2000,    # Owner took $2,000 salary draw
}


# ---------------------------------------------------------------------------
# Blue Oak Consulting — Professional services firm (no physical inventory)
# Higher AR (clients on net-30/60 terms), minimal CapEx
# ---------------------------------------------------------------------------
BLUE_OAK_CF = {
    # Investing Activities
    "capital_expenditures":  1800,    # New laptop for new team member
    "depreciation":          350,     # Monthly depreciation on computers and office furniture

    # Working Capital changes (vs previous month)
    "ar_change":             4500,    # AR went UP $4,500 — two large clients on 45-day terms
    "inventory_change":      0,       # Service business — no physical inventory
    "ap_change":             600,     # AP went UP $600 — delayed one software vendor payment

    # Financing Activities
    "loan_proceeds":         0,       # No new borrowing
    "loan_repayments":       500,     # Small business credit line monthly payment
    "owner_drawings":        3500,    # Owner took $3,500 this month
}


# ---------------------------------------------------------------------------
# Lookup function — same pattern as sample_data.py and sample_balance_sheet.py
# ---------------------------------------------------------------------------
CASH_FLOW_LOOKUP = {
    "riverside_home_goods": RIVERSIDE_CF,
    "blue_oak_consulting":  BLUE_OAK_CF,
}


def get_sample_cash_flow(client_id: str) -> dict:
    """
    Returns the cash flow supplement data for a given client.

    client_id : "riverside_home_goods" or "blue_oak_consulting"

    Returns a dict with capex, depreciation, AR/AP/inventory changes,
    and financing items — ready to pass into analyze_cash_flow().
    """
    data = CASH_FLOW_LOOKUP.get(client_id)
    if data is None:
        # Return empty dict for unknown clients — analyze_cash_flow() handles this gracefully
        return {}
    return data
