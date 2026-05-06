"""
test_insights.py
----------------
Run this to test the full analysis + Claude insights pipeline.
It uses the sample P&L data (no QuickBooks needed).

How to run:
  python test_insights.py
"""

from src.analysis.sample_data import SAMPLE_PNL
from src.analysis.analyzer import run_analysis
from src.claude_insights.insights import generate_insights


def main():
    print("=" * 60)
    print("  FINANCIAL REPORTS — PIPELINE TEST")
    print("=" * 60)

    # Step 1: Analyze the numbers
    print("\n[1/2] Analyzing financial data...")
    analysis = run_analysis(SAMPLE_PNL)

    # Print the summary table so you can see the numbers
    print(f"\nBusiness : {analysis['business_name']}")
    print(f"Period   : {analysis['all_months'][0]} → {analysis['latest_month']}")
    print("\n--- Summary ---")
    print(analysis["summary_df"].to_string())

    # Step 2: Generate Claude insights
    print("\n[2/2] Sending data to Claude for insights...")
    print("      (This may take 10-20 seconds...)\n")

    insights = generate_insights(analysis)

    print("=" * 60)
    print(f"  MONTHLY COMMENTARY — {analysis['latest_month']}")
    print("=" * 60)
    print(insights)
    print("=" * 60)
    print("\nPipeline test complete!")


if __name__ == "__main__":
    main()
