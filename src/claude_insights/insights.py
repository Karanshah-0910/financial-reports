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
import json
import pathlib
import datetime
import anthropic
from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file: src/claude_insights/ → project root)
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

_EXAMPLES_DIR = _PROJECT_ROOT / "insight_examples"


# ---------------------------------------------------------------------------
# Example library — auto-capture and few-shot retrieval
# ---------------------------------------------------------------------------

def _next_example_id() -> str:
    """Return the next padded example number: '001', '002', etc."""
    _EXAMPLES_DIR.mkdir(exist_ok=True)
    existing = [
        d for d in _EXAMPLES_DIR.iterdir()
        if d.is_dir() and d.name[0].isdigit()
    ]
    return f"{len(existing) + 1:03d}"


def _save_example_draft(example_id: str, client_id: str, period: str,
                         data_block: str, draft: str,
                         industry: str = "", revenue: float = 0,
                         margin: float = 0) -> pathlib.Path:
    """
    Auto-save input + draft after every Claude call.
    Creates the folder and files silently — no user action needed.
    final.txt is only created when the user runs refine_insight.py.
    """
    safe_client = (client_id or "unknown").replace(" ", "_")
    try:
        ym = datetime.datetime.strptime(period, "%B %Y").strftime("%Y-%m")
    except Exception:
        ym = period.replace(" ", "-")

    folder_name = f"{example_id}_{safe_client}_{ym}"
    folder = _EXAMPLES_DIR / folder_name
    folder.mkdir(exist_ok=True)

    # input.json — the financial summary sent to Claude
    (folder / "input.json").write_text(
        json.dumps({
            "client_id": client_id,
            "period":    period,
            "data":      data_block,
        }, indent=2),
        encoding="utf-8"
    )

    # draft.txt — Claude's raw first response
    (folder / "draft.txt").write_text(draft, encoding="utf-8")

    # metadata.json — used for smart example selection
    (folder / "metadata.json").write_text(
        json.dumps({
            "example_id":   example_id,
            "client_id":    client_id,
            "period":       period,
            "industry":     industry,
            "revenue":      revenue,
            "net_margin":   margin,
            "has_final":    False,
            "captured_at":  datetime.datetime.now().isoformat(),
        }, indent=2),
        encoding="utf-8"
    )

    return folder


def _load_examples(current_industry: str = "",
                   current_revenue: float = 0,
                   current_margin: float = 0,
                   max_examples: int = 3) -> list[dict]:
    """
    Load the best matching complete examples (those with a final.txt).

    Scoring logic (higher = more relevant):
      +3  exact industry match
      +1  revenue within 2x
      +1  margin within 10 percentage points
      +0.5 per 10 examples of recency bias (newer = slightly preferred)

    Returns a list of dicts: [{input, draft, final, metadata}, ...]
    Sorted best-match first.
    """
    if not _EXAMPLES_DIR.exists():
        return []

    scored = []
    for folder in sorted(_EXAMPLES_DIR.iterdir()):
        if not folder.is_dir() or not folder.name[0].isdigit():
            continue

        final_path = folder / "final.txt"
        input_path = folder / "input.json"
        meta_path  = folder / "metadata.json"

        if not final_path.exists() or not input_path.exists():
            continue    # Skip examples without a final edit

        try:
            meta  = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            inp   = json.loads(input_path.read_text(encoding="utf-8"))
            final = final_path.read_text(encoding="utf-8").strip()
            draft = (folder / "draft.txt").read_text(encoding="utf-8").strip() \
                    if (folder / "draft.txt").exists() else ""

            if not final:
                continue

            # Score relevance
            score = 0.0
            ex_industry = meta.get("industry", "").lower()
            ex_revenue  = float(meta.get("revenue",    0) or 0)
            ex_margin   = float(meta.get("net_margin", 0) or 0)
            ex_id       = int(meta.get("example_id", "0") or 0)

            if current_industry and ex_industry:
                if current_industry.lower() == ex_industry.lower():
                    score += 3
                elif any(w in ex_industry for w in current_industry.lower().split()):
                    score += 1

            if current_revenue > 0 and ex_revenue > 0:
                ratio = max(current_revenue, ex_revenue) / min(current_revenue, ex_revenue)
                if ratio <= 2:
                    score += 1

            if abs(current_margin - ex_margin) <= 10:
                score += 1

            # Slight recency bonus
            score += ex_id * 0.05

            scored.append((score, {
                "input":    inp.get("data", ""),
                "period":   inp.get("period", ""),
                "draft":    draft,
                "final":    final,
                "metadata": meta,
            }))

        except Exception:
            continue

    # Sort by score descending, return top N
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in scored[:max_examples]]


def _build_fewshot_block(examples: list[dict]) -> str:
    """
    Format examples as a few-shot block to inject into the prompt.
    Each example shows: what the data looked like → what good output looks like.
    """
    if not examples:
        return ""

    lines = [
        "EXAMPLES OF THE EXACT VOICE AND STYLE EXPECTED",
        "=" * 56,
        "Study these carefully. Your output should match this "
        "analytical style, level of directness, and phrasing.",
        "",
    ]

    for i, ex in enumerate(examples, 1):
        meta   = ex.get("metadata", {})
        period = ex.get("period", "")
        ind    = meta.get("industry", "")
        rev    = meta.get("revenue", 0)
        margin = meta.get("net_margin", 0)

        context_parts = []
        if period:   context_parts.append(period)
        if ind:      context_parts.append(ind)
        if rev:      context_parts.append(f"~${float(rev):,.0f} revenue")
        if margin:   context_parts.append(f"{float(margin):.1f}% margin")
        context_str = "  |  ".join(context_parts)

        lines += [
            f"--- EXAMPLE {i} ---",
            f"Context: {context_str}" if context_str else f"--- EXAMPLE {i} ---",
            "",
            "OUTPUT (this is the style, voice, and quality to match):",
            ex["final"],
            "",
        ]

    lines += ["=" * 56, ""]
    return "\n".join(lines)


def _count_complete_examples() -> int:
    """Return number of examples that have both draft and final."""
    if not _EXAMPLES_DIR.exists():
        return 0
    count = 0
    for folder in _EXAMPLES_DIR.iterdir():
        if folder.is_dir() and (folder / "final.txt").exists():
            count += 1
    return count


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

    When completed examples exist in insight_examples/, the most
    relevant ones are injected as few-shot examples so Claude
    matches your voice and analytical style progressively over time.

    analysis      : output of run_analysis()
    client_config : optional — adds industry context to the prompt
    bs_analysis   : optional — output of analyze_balance_sheet()
    cf_analysis   : optional — output of analyze_cash_flow()

    Returns a plain-text string with three labelled sections.
    """
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    business_name    = analysis["business_name"]
    latest_month     = analysis["latest_month"]
    client_id        = analysis.get("client_id", business_name.lower().replace(" ", "_"))

    # ── Build the financial data block ────────────────────────────────────
    data_block = _format_financials_for_claude(analysis)

    if bs_analysis:
        from src.analysis.balance_sheet_analyzer import format_bs_for_claude
        data_block += "\n\n" + format_bs_for_claude(bs_analysis)

    if cf_analysis:
        from src.analysis.cash_flow_analyzer import format_cf_for_claude
        data_block += "\n\n" + format_cf_for_claude(cf_analysis)

    # ── Industry and financial profile for example matching ───────────────
    industry = ""
    if client_config:
        industry = (
            client_config.get("industry", "") or
            client_config.get("report_preferences", {}).get("industry_context", "")
        )

    latest     = analysis["latest_month"]
    summary_df = analysis["summary_df"]
    try:
        current_revenue = float(summary_df.loc["Total Revenue", latest])
        current_margin  = float(summary_df.loc["Net Margin %",  latest])
    except Exception:
        current_revenue = 0
        current_margin  = 0

    # ── Load few-shot examples (requires final.txt to exist) ──────────────
    n_complete = _count_complete_examples()
    examples   = []
    if n_complete >= 1:
        examples = _load_examples(
            current_industry = industry,
            current_revenue  = current_revenue,
            current_margin   = current_margin,
            max_examples     = 3,
        )

    fewshot_block = _build_fewshot_block(examples)

    # ── Industry context line ─────────────────────────────────────────────
    industry_line = ""
    if industry:
        industry_line = f"\n\nContext: This business operates in the {industry} sector."

    # ── System prompt — cached across the full batch run ─────────────────
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

    # ── User message — few-shot examples prepended when available ─────────
    user_content_parts = []

    if fewshot_block:
        # Cache the examples block — it's stable and reused across clients
        user_content_parts.append({
            "type": "text",
            "text": fewshot_block,
            "cache_control": {"type": "ephemeral"},
        })

    user_content_parts.append({
        "type": "text",
        "text": (
            f"Write the monthly briefing for {business_name}, {latest_month}."
            + (f"\n\nMatch the voice and style of the examples above."
               if fewshot_block else "")
            + f"\n\n{data_block}"
        ),
    })

    # ── API call ──────────────────────────────────────────────────────────
    response = anthropic_client.messages.create(
        model      = "claude-sonnet-4-5",
        max_tokens = 800,

        system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],

        messages = [{"role": "user", "content": user_content_parts}],
    )

    draft = response.content[0].text

    # ── Auto-save input + draft for future refinement ─────────────────────
    try:
        example_id = _next_example_id()
        folder = _save_example_draft(
            example_id = example_id,
            client_id  = client_id,
            period     = latest_month,
            data_block = data_block,
            draft      = draft,
            industry   = industry,
            revenue    = current_revenue,
            margin     = current_margin,
        )
        # Only print this if there are still uncompleted examples to review
        pending = sum(
            1 for f in _EXAMPLES_DIR.iterdir()
            if f.is_dir() and (f / "draft.txt").exists()
            and not (f / "final.txt").exists()
        )
        if pending <= 3:   # Don't spam the console once the library is large
            print(f"      Example saved: {folder.name}  "
                  f"({n_complete} complete, {pending} pending review)")
    except Exception:
        pass   # Never let example saving crash the report pipeline

    return draft
