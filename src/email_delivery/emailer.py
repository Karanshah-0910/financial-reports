"""
emailer.py
----------
Sends the finished PDF report to the client via email.
Uses Gmail SMTP with an App Password (no extra libraries needed).
"""

import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()


def _build_email_body(client: dict, analysis: dict) -> str:
    owner        = client.get("owner_name", "there")
    business     = client["business_name"]
    latest_month = analysis["latest_month"]
    all_months   = analysis["all_months"]
    summary      = analysis["summary_df"]

    revenue    = summary.loc["Total Revenue",  latest_month]
    net_profit = summary.loc["Net Profit",     latest_month]
    net_margin = summary.loc["Net Margin %",   latest_month]

    profit_word = "profit" if net_profit >= 0 else "loss"
    first_name  = owner.split()[0] if owner != "there" else "there"
    author      = os.getenv("REPORT_AUTHOR", "Your Financial Advisor")

    body = (
        f"Hi {first_name},\n\n"
        f"Please find attached your Monthly Financial Report for {latest_month}.\n\n"
        f"Here's a quick snapshot for the month:\n\n"
        f"  - Total Revenue:  ${revenue:,.0f}\n"
        f"  - Net {profit_word.title()}:    ${abs(net_profit):,.0f}  ({net_margin:.1f}% net margin)\n\n"
        f"The full report includes a detailed breakdown of your financials, "
        f"month-over-month comparisons, and tailored recommendations for the month ahead.\n\n"
        f"As always, please don't hesitate to reply if you have any questions.\n\n"
        f"Best regards,\n"
        f"{author}\n\n"
        f"---\n"
        f"Report covers: {all_months[0]} to {latest_month}\n"
        f"Prepared for: {business}\n"
    )
    return body


def send_report(client: dict, analysis: dict, pdf_path: str) -> bool:
    """
    Send the PDF report to the client by email.
    Returns True if sent successfully, False otherwise.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()

    if not smtp_user or not smtp_pass:
        print("  !! Email not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
        return False

    recipient    = client["email"]
    business     = client["business_name"]
    latest_month = analysis["latest_month"]

    # Plain ASCII subject — no special characters
    subject = f"{business} - Monthly Financial Report - {latest_month}"
    body    = _build_email_body(client, analysis)

    # Build email using EmailMessage which handles encoding automatically
    msg = EmailMessage()
    msg["From"]    = smtp_user
    msg["To"]      = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach the PDF
    pdf_filename = os.path.basename(pdf_path)
    with open(pdf_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename=pdf_filename
        )

    # Send
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print(f"  Email sent to {recipient}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("  !! Email failed: Authentication error.")
        print("     Check SMTP_USER and SMTP_PASSWORD in .env")
        print("     Gmail: use an App Password, not your regular password.")
        return False

    except smtplib.SMTPException as e:
        print(f"  !! Email failed: {e}")
        return False

    except Exception as e:
        print(f"  !! Unexpected error sending email: {e}")
        return False
