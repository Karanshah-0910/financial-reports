# Financial Reports Automation

Automated monthly financial reporting service for small business clients.
Pulls data from QuickBooks Online, analyzes it with Claude AI, and generates polished PDF reports.

---

## What Each Folder Does

```
financial-reports/
│
├── src/                        # All the Python code lives here
│   ├── quickbooks/             # Code that talks to the QuickBooks Online API
│   │                           #   (authentication, pulling P&L, balance sheet, etc.)
│   ├── analysis/               # Code that crunches the numbers
│   │                           #   (month-over-month changes, ratios, trends)
│   ├── claude_insights/        # Code that sends data to Claude and gets back
│   │                           #   plain-English insights and commentary
│   └── pdf_generator/          # Code that assembles the final PDF report
│
├── data/
│   ├── raw/                    # Raw JSON/CSV data exactly as QuickBooks returns it
│   │                           #   (never edit these — they're your source of truth)
│   └── processed/              # Cleaned, structured data ready for analysis
│
├── reports/
│   ├── output/                 # Finished PDF reports go here, organized by client
│   └── templates/              # Visual templates and branding assets for reports
│
├── clients/                    # One config file per client
│                               #   (their QB company ID, report preferences, email, etc.)
│
├── logs/                       # Automatic logs of every run — useful for troubleshooting
│
├── .env                        # YOUR SECRET API KEYS — never share or commit this file
├── .env.template               # A blank copy of .env showing what keys are needed
├── .gitignore                  # Tells Git which files to keep private
├── requirements.txt            # List of all Python libraries this project needs
└── README.md                   # This file
```

---

## How the Pipeline Works

```
QuickBooks Online
      │
      │  (1) Pull financial data via API
      ▼
 data/raw/           ← JSON files saved here
      │
      │  (2) Clean and structure the data
      ▼
 data/processed/     ← Tidy tables saved here
      │
      │  (3) Send to Claude API for analysis
      ▼
 Claude AI           ← Returns plain-English insights
      │
      │  (4) Combine numbers + insights into a PDF
      ▼
 reports/output/     ← Finished PDF delivered to client
```

---

## First-Time Setup

See the step-by-step guide in `SETUP_GUIDE.md`.

Short version:
1. Install Python 3.12
2. Create and activate a virtual environment
3. `pip install -r requirements.txt`
4. Copy `.env.template` to `.env` and fill in your API keys
5. Run `python src/quickbooks/auth.py` to connect your first QuickBooks company

---

## API Keys You Will Need

| Key | Where to Get It |
|-----|----------------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys |
| `QB_CLIENT_ID` + `QB_CLIENT_SECRET` | https://developer.intuit.com → My Apps |

---

## Important Rules

- **Never put real API keys in any file except `.env`**
- **Never share or upload `.env`** — it gives anyone full access to your accounts
- The `reports/output/` folder contains client financial data — treat it like paper files
- Always test with the QuickBooks **sandbox** environment before going live
