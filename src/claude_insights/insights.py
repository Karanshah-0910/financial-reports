"""
insights.py
-----------
Sends fully analyzed financial data to Claude and gets back a
3-section executive summary written in the voice of a sharp
fractional CFO — professional, plain-English, zero jargon.

SECTIONS RETURNED:
  What Happened   : 2-3 sentences on the month's key financial events
  Why It Matters  : 2-3 sentences on the real business implications
  What to Watch   : 2-3 specific, actionable things to monitor next month

Uses prompt caching on the system prompt — when running multiple
clients back-to-back, Anthropic only bills the system prompt once.
"""

import os
import pathlib
import anthropic
from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file: src/claude_insights/ → project root)
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)


# ---------------------------------------------------------------------------
# Internal: build the data block Claude receives
# ---------------------------------------------------------------------------

def _format_financials_for_claude(analysis: dict) -> str:
    """
    Converts all analysis DataFrames + metrics into a clean, structured
    text block that Claude can reason over accurately.
    """
    business = analysis["business_name"]
    currency = analysis["currency"]
    months   = analysis["all_months"]
    summary  = analysis["summary_df"]
    mom      = analysis["mom_df"]
    detail   = analysis["detail_df"]
    latest   = analysis["latest_month"]

    lines = []
    lines.append(f"BUSINESS: {business}")
    lines.append(f"REPORTING PERIOD: {months[0]} through {latest}")
    lines.append(f"CURRENCY: {currency}")
    lines.append("")

    # --- Summary financials ---
    lines.append("=== KEY FINANCIALS ===")
    header = f"{'Metric':<22}" + "".join(f"{m:>18}" for m in months)
    lines.append(header)
    lines.append("-" * (22 + 18 * len(months)))
    for metric in summary.index:
        row = f"{metric:<22}"
        for month in months:
            val = summary.loc[metric, month]
            row += f"{val:>17.1f}%" if "%" in metric else f"${val:>16,.0f}"
        lines.append(row)
    lines.append("")

    # --- Month-over-month % changes ---
    lines.append("=== MONTH-OVER-MONTH CHANGES (%) ===")
    header2 = f"{'Metric':<22}" + "".join(f"{m:>18}" for m in months)
    lines.append(header2)
    lines.append("-" * (22 + 18 * len(months)))
    for metric in mom.index:
        row = f"{metric:<22}"
        for month in months:
            val = mom.loc[metric, month]
            if _isnan(val):
                row += f"{'n/a':>18}"
            else:
                arrow = "UP" if val > 0 else ("DOWN" if val < 0 else "FLAT")
                row += f"{arrow} {abs(val):>12.1f}%"
        lines.append(row)
    lines.append("")

    # --- Expense detail ---
    lines.append(f"=== EXPENSE DETAIL — {latest} ===")
    expense_lines = [
        "Rent", "Rent & Office", "Payroll", "Utilities",
        "Marketing & Advertising", "Software & Subscriptions",
        "Shipping & Postage", "Professional Fees",
        "Travel & Entertainment", "Cost of Services", "Miscellaneous",
    ]
    for item in expense_lines:
        if item in detail.index:
            val = abs(detail.loc[item, latest])
            lines.append(f"  {item:<30} ${val:>10,.0f}")

    # --- Top 5 expenses ---
    top_expenses = analysis.get("top_expenses", [])
    if top_expenses:
        lines.append("")
        lines.append("=== TOP 5 EXPENSE CATEGORIES ===")
        for i, exp in enumerate(top_expenses, 1):
            lines.append(
                f"  {i}. {exp['name']:<28} ${exp['amount']:>10,.0f}"
                f"  ({exp['pct']}% of total expenses)"
            )

    # --- Expense vs revenue growth ---
    growth = analysis.get("expense_growth", {})
    if growth:
        lines.append("")
        lines.append("=== EXPENSE VS REVENUE GROWTH (first month vs latest) ===")
        lines.append(f"  Revenue growth  : {growth.get('revenue_growth_pct', 0):+.1f}%")
        lines.append(f"  Expense growth  : {growth.get('expense_growth_pct', 0):+.1f}%")
        lines.append(f"  Verdict         : {growth.get('verdict', '')}")

    # --- Attention flags ---
    flags = analysis.get("attention_flags", [])
    if flags:
        lines.append("")
        lines.append("=== LINE ITEMS THAT MOVED MORE THAN 20% MoM ===")
        for f in flags[:8]:
            direction = "UP" if f["direction"] == "up" else "DOWN"
            lines.append(
                f"  {f['item']:<30} {direction} {abs(f['change_pct']):.1f}%"
                f"  (was ${f['prev']:,.0f}, now ${f['current']:,.0f})"
            )

    return "\n".join(lines)


def _isnan(val) -> bool:
    try:
        return val != val
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_insights(
    analysis:      dict,
    client_config: dict = None,
    bs_analysis:   dict = None,
    cf_analysis:   dict = None,
) -> str:
    """
    Send all financial data to Claude and get back a 3-section
    executive summary in the voice of a fractional CFO.

    analysis      : output of run_analysis()
    client_config : optional — adds industry context to the prompt
    bs_analysis   : optional — output of analyze_balance_sheet()
    cf_analysis   : optional — output of analyze_cash_flow()

    Returns a plain-text string with three labelled sections.
    """
    client        = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    business_name = analysis["business_name"]
    latest_month  = analysis["latest_month"]

    # Build the data block Claude will read
    data_block = _format_financials_for_claude(analysis)

    if bs_analysis:
        from src.analysis.balance_sheet_analyzer import format_bs_for_claude
        data_block += "\n\n" + format_bs_for_claude(bs_analysis)

    if cf_analysis:
        from src.analysis.cash_flow_analyzer import format_cf_for_claude
        data_block += "\n\n" + format_cf_for_claude(cf_analysis)

    # Optional industry context from client config
    industry_line = ""
    if client_config:
        ctx = client_config.get("report_preferences", {}).get("industry_context", "")
        if ctx:
            industry_line = f"\n\nContext: This business operates in the {ctx} sector."

    # ------------------------------------------------------------------
    # System prompt — cached so multiple clients in one run only pay once
    # ------------------------------------------------------------------
    system_prompt = (
        "You are a fractional CFO writing a monthly financial briefing "
        "for a small business owner. Your job is to turn raw financial "
        "numbers into clear, direct business insight.\n\n"

        "VOICE AND TONE:\n"
        "- Talk like a trusted senior advisor, not an accountant\n"
        "- Be direct and confident — no hedging, no padding\n"
        "- Use plain English only. If a financial term is unavoidable, "
        "define it immediately in plain language in parentheses\n"
        "- Reference specific dollar amounts and percentages from the data\n"
        "- Talk about the business, not the numbers — what do the numbers mean "
        "for the owner's decisions?\n"
        "- Write in second person: 'your revenue', 'your team', 'your cash'\n\n"

        "OUTPUT FORMAT — use EXACTLY these three section headers:\n\n"

        "WHAT HAPPENED\n"
        "2-3 sentences. Summarise the most important financial events of the "
        "month in plain English. Lead with the single most important fact. "
        "Do not list every metric — pick what matters most.\n\n"

        "WHY IT MATTERS\n"
        "2-3 sentences. Explain the business implication of what happened. "
        "Why should the owner care? What does this mean for the health of "
        "the business, ability to pay staff, grow, or survive?\n\n"

        "WHAT TO WATCH\n"
        "Exactly 3 bullet points, each starting with '- '. "
        "Each bullet names one specific metric or situation to monitor next "
        "month, explains in one sentence why it matters, and gives a concrete "
        "threshold or action. E.g.: '- If marketing spend stays above $X next "
        "month without a matching revenue lift, cut it by 20%.'\n\n"

        "HARD RULES:\n"
        "- Total response must be under 350 words\n"
        "- Never use section numbers — use the exact headers above\n"
        "- Never say 'it is important to note' or 'it is worth mentioning'\n"
        "- Never restate all the data — interpret it"
        f"{industry_line}"
    )

    response = client.messages.create(
        model      = "claude-sonnet-4-5",
        max_tokens = 800,

        system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},   # Billed once per run
            }
        ],

        messages = [
            {
                "role": "user",
                "content": (
                    f"Write the monthly briefing for {business_name}, {latest_month}.\n\n"
                    f"{data_block}"
                ),
            }
        ],
    )

    return response.content[0].text
