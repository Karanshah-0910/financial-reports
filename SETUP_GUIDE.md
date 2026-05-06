# Step-by-Step Setup Guide

This guide walks you through setting up the project from scratch on Windows.
You do not need any prior coding experience. Every command is shown exactly as you should type it.

---

## Before You Start

You will use a program called **Command Prompt** (or **PowerShell**) to type commands.
- Press the **Windows key**, type `cmd`, and press **Enter** to open it.
- Commands are typed after the blinking cursor (`>`).
- Press **Enter** after typing each command to run it.

---

## Step 1 — Install Python

**Do this once, ever. Skip if Python is already installed.**

1. Go to https://www.python.org/downloads/
2. Click the big yellow **"Download Python 3.12.x"** button.
3. Run the installer. **IMPORTANT:** On the first screen, check the box that says
   **"Add Python to PATH"** before clicking Install Now.
4. Click **Install Now** and wait for it to finish.

**How to verify it worked:**
Open Command Prompt and type:
```
python --version
```
You should see something like: `Python 3.12.4`
If you see that, Python is installed correctly. ✓

---

## Step 2 — Navigate to the Project Folder

In Command Prompt, type:
```
cd "C:\Users\karan\OneDrive\Desktop\Karan\financial-reports"
```
Press Enter.

**What to expect:** The prompt changes to show the folder path, like:
`C:\Users\karan\OneDrive\Desktop\Karan\financial-reports>`
This means you are now "inside" the project folder. ✓

---

## Step 3 — Create a Virtual Environment

A virtual environment is a private, isolated Python installation just for this project.
It keeps your project's libraries separate from everything else on your computer.

Type:
```
python -m venv venv
```
Press Enter and wait a few seconds.

**What to expect:** A new folder called `venv` appears inside your project folder.
You won't see any output — a blank line means it worked. ✓

---

## Step 4 — Activate the Virtual Environment

You must do this **every time** you open a new Command Prompt window to work on this project.

Type:
```
venv\Scripts\activate
```
Press Enter.

**What to expect:** The prompt now starts with `(venv)`, like:
`(venv) C:\Users\karan\OneDrive\Desktop\Karan\financial-reports>`
The `(venv)` prefix confirms the environment is active. ✓

---

## Step 5 — Install the Required Libraries

With your virtual environment active, type:
```
pip install -r requirements.txt
```
Press Enter and wait. This downloads and installs all the libraries the project needs.
It may take 2–5 minutes depending on your internet connection.

**What to expect:** You will see a scrolling list of packages being downloaded and installed,
ending with something like:
```
Successfully installed anthropic-0.49.0 pandas-2.2.2 reportlab-4.2.2 ...
```
If you see "Successfully installed", you are done. ✓

If you see any red error messages, the most common fix is to upgrade pip first:
```
python -m pip install --upgrade pip
```
Then run `pip install -r requirements.txt` again.

---

## Step 6 — Create Your .env File

Your `.env` file stores your secret API keys. It must never be shared.

**Option A — Using File Explorer:**
1. Open your project folder in File Explorer.
2. Find the file called `.env.template`.
3. Right-click it → Copy, then right-click → Paste.
4. Rename the copy from `.env.template - Copy` to `.env`
   (delete everything after `.env` in the name).
5. Open `.env` with Notepad and replace the placeholder values with your real keys.

**Option B — Using Command Prompt (while in the project folder with venv active):**
```
copy .env.template .env
```
Then open `.env` in Notepad:
```
notepad .env
```
Replace each `your_..._here` value with your real key. Save and close.

**What to expect after saving:** Your `.env` file should look like:
```
ANTHROPIC_API_KEY=sk-ant-api03-abc123...
QB_CLIENT_ID=ABcde12345...
QB_CLIENT_SECRET=xyz9876...
```
The values are your actual keys, not the placeholder text. ✓

---

## Step 7 — Get Your API Keys

### Anthropic (Claude) API Key
1. Go to https://console.anthropic.com
2. Sign up or log in.
3. Click **API Keys** in the left sidebar.
4. Click **Create Key**, give it a name like "financial-reports".
5. Copy the key (starts with `sk-ant-`) and paste it into `.env` as `ANTHROPIC_API_KEY`.

### QuickBooks Online API Keys
1. Go to https://developer.intuit.com
2. Sign in with your Intuit/QuickBooks account.
3. Click **Dashboard** → **Create an App**.
4. Choose **QuickBooks Online and Payments**.
5. Give your app a name (e.g., "Financial Reports Bot").
6. Go to your app's **Keys & OAuth** tab.
7. Copy the **Client ID** and **Client Secret** (sandbox section for now).
8. Paste them into `.env` as `QB_CLIENT_ID` and `QB_CLIENT_SECRET`.

---

## Step 8 — Verify Everything Is Working

With your virtual environment active, type:
```
python -c "import anthropic; import quickbooks; import pandas; import reportlab; print('All libraries imported successfully!')"
```

**What to expect:**
```
All libraries imported successfully!
```
If you see this message, your environment is fully set up. ✓

If you see an error like `ModuleNotFoundError: No module named 'anthropic'`, it usually means
the virtual environment is not active. Run `venv\Scripts\activate` and try again.

---

## Daily Workflow

Every time you open a new Command Prompt to work on this project:

```
cd "C:\Users\karan\OneDrive\Desktop\Karan\financial-reports"
venv\Scripts\activate
```

That's it — you're ready to work.

---

## Quick Reference

| Task | Command |
|------|---------|
| Navigate to project | `cd "C:\Users\karan\OneDrive\Desktop\Karan\financial-reports"` |
| Activate environment | `venv\Scripts\activate` |
| Install a new library | `pip install library-name` |
| Save new library to requirements | `pip freeze > requirements.txt` |
| Deactivate environment | `deactivate` |
