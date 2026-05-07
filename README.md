# Automated Financial Reporting System

A fully automated monthly reporting service for small business clients —
built with Python, QuickBooks Online API, and Claude AI.

Pulls live financial data, runs anomaly checks, generates AI-written
commentary, builds branded PDF reports, emails clients, and runs itself
every 1st of the month without any manual work.

---

## What It Does

**Every month, automatically:**
1. Connects to each client's QuickBooks Online and pulls P&L, Balance Sheet, and Cash Flow
2. Runs 20+ data quality checks — blocks the report if critical issues are found
3. Sends financial data to Claude AI, which writes plain-English insights
4. Builds a branded PDF report with charts and commentary
5. Generates an interactive HTML dashboard for each client
6. Emails each client their report and dashboard link
7. Sends you a batch summary with a full log attached

**Client portal:**
- Clients log in at `http://localhost:8080` with their ID and password
- See their latest dashboard with live charts
- Download any past PDF report from a sidebar

**Your internal dashboard:**
- One command (`python dashboard.py`) shows active clients, MRR trend, overdue reports, batch history

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Data source | QuickBooks Online API (OAuth 2.0) |
| AI insights | Anthropic Claude API (with prompt caching + few-shot learning) |
| PDF generation | fpdf2 |
| Database | SQLite (stdlib — no server needed) |
| Client portal | Flask |
| Scheduler | Windows Task Scheduler |
| Charts | Chart.js (client dashboards), matplotlib (PDFs) |

---

## Project Structure

```
financial-reports/
│
├── run_monthly_reports.py       ← Master batch runner (runs all clients)
├── manage_clients.py            ← Add / update / deactivate clients
├── dashboard.py                 ← Your internal business dashboard
├── generate_client_dashboard.py ← Per-client HTML dashboard
├── client_portal.py             ← Flask login portal for clients
├── anomaly_check.py             ← QC layer — catches bad data before reports go out
├── refine_insight.py            ← Train Claude on your voice using past edits
├── onboard_client.py            ← Guided new client setup
├── qbo_auth.py                  ← Connect a client's QuickBooks account
├── qbo_fetch.py                 ← Pull QB data manually
├── setup_scheduler.py           ← Register monthly Windows Task Scheduler job
├── run_reports.bat              ← Batch file called by the scheduler
│
├── src/
│   ├── quickbooks/              ← QB OAuth + API data pull (P&L, BS, CF)
│   ├── analysis/                ← P&L, balance sheet, cash flow analysis
│   ├── claude_insights/         ← Claude prompt + few-shot learning system
│   └── pdf_generator/           ← PDF report builder
│
├── insight_examples/            ← Your training library (draft → edited pairs)
├── reports/                     ← Generated PDFs and dashboards (gitignored)
├── data/raw/                    ← Raw QB JSON (gitignored)
├── logs/                        ← Batch run logs (gitignored)
│
├── .env                         ← API keys (gitignored — never commit)
├── .env.template                ← Blank template showing required keys
└── clients.db                   ← SQLite client database (gitignored)
```

---

## Pipeline Per Client

```
QuickBooks Online
      │
      │  OAuth 2.0 — pulls P&L (3 months), Balance Sheet, Cash Flow
      ▼
 Analysis Layer
      │  Month-over-month trends, ratios, cash runway, burn rate
      ▼
 Anomaly Check (20+ rules)
      │  CRITICAL → blocks report   WARNING → flags for review
      ▼
 Claude AI (with few-shot learning)
      │  Generates: WHAT HAPPENED / WHY IT MATTERS / WHAT TO WATCH
      ▼
 PDF Report  +  HTML Dashboard
      │
      ▼
 Email to client  +  Summary email to you
```

---

## Few-Shot Learning System

The system learns your writing style over time:
- Every report auto-saves Claude's draft to `insight_examples/`
- You edit the draft in Notepad (`python refine_insight.py`)
- After 5 examples, Claude starts using your edits as style reference
- After 20 examples, reports need almost no editing

---

## Quick Start

**1. Install dependencies**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**2. Set up your API keys**
```bash
copy .env.template .env
# Edit .env and fill in your keys
```

**3. Add your first client**
```bash
python manage_clients.py add
```

**4. Connect their QuickBooks**
```bash
python qbo_auth.py --client their_client_id
```

**5. Run your first report**
```bash
python run_monthly_reports.py --client their_client_id
```

**6. Set up monthly auto-run (run as Administrator)**
```bash
python setup_scheduler.py
```

---

## API Keys Required

| Key | Where to Get It |
|-----|----------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `QB_CLIENT_ID` + `QB_CLIENT_SECRET` | developer.intuit.com → My Apps |
| `SMTP_USER` + `SMTP_PASSWORD` | Gmail App Password (not your login password) |

---

## Security

- All client data, tokens, and API keys are gitignored — nothing sensitive is ever committed
- Client portal uses hashed passwords (SHA-256 + salt)
- QB tokens are stored locally per client, auto-refreshed before expiry
- PDF downloads in the portal are access-controlled — clients can only see their own files
