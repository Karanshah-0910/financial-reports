"""
auth.py
-------
Handles QuickBooks Online OAuth 2.0 authentication.

How it works:
  1. We open a browser tab with the QuickBooks login page
  2. You log in and click Connect
  3. QuickBooks redirects to Intuit's playground page
  4. You copy the 'code' and 'realmId' values from that page and paste them here
  5. We swap those for tokens and save them to clients/tokens/

Run this once per client to connect their QuickBooks account:
  python -m src.quickbooks.auth riverside_home_goods
"""

import os
import sys
import json
import time
import pathlib
import webbrowser
import urllib.parse
import requests
from dotenv import load_dotenv

# Resolve .env from the project root regardless of where Python is called from
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CLIENT_ID     = os.getenv("QB_CLIENT_ID")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("QB_REDIRECT_URI")
ENVIRONMENT   = os.getenv("QB_ENVIRONMENT", "sandbox")

AUTH_URL  = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SCOPES    = "com.intuit.quickbooks.accounting"

TOKENS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "clients", "tokens")


# ---------------------------------------------------------------------------
# Token storage
# ---------------------------------------------------------------------------
def _tokens_path(client_id: str) -> str:
    os.makedirs(TOKENS_DIR, exist_ok=True)
    return os.path.join(TOKENS_DIR, f"{client_id}_tokens.json")


def save_tokens(client_id: str, tokens: dict):
    tokens["saved_at"] = time.time()
    path = _tokens_path(client_id)
    with open(path, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"  Tokens saved to {path}")


def load_tokens(client_id: str) -> dict:
    path = _tokens_path(client_id)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def tokens_exist(client_id: str) -> bool:
    return os.path.exists(_tokens_path(client_id))


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------
def refresh_access_token(client_id: str) -> str:
    tokens = load_tokens(client_id)
    if not tokens.get("refresh_token"):
        raise ValueError(f"No refresh token for {client_id}. Run auth first.")

    response = requests.post(
        TOKEN_URL,
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={
            "grant_type":    "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    new_tokens = response.json()
    tokens.update(new_tokens)
    save_tokens(client_id, tokens)
    return new_tokens["access_token"]


def get_valid_access_token(client_id: str) -> str:
    tokens = load_tokens(client_id)
    if not tokens:
        raise ValueError(f"No tokens for {client_id}. Run: python -m src.quickbooks.auth {client_id}")

    saved_at   = tokens.get("saved_at", 0)
    expires_in = tokens.get("expires_in", 3600)
    age        = time.time() - saved_at

    if age > (expires_in - 300):
        print(f"  Access token expired — refreshing...")
        return refresh_access_token(client_id)

    return tokens["access_token"]


def get_company_id(client_id: str) -> str:
    tokens = load_tokens(client_id)
    company_id = tokens.get("company_id")
    if not company_id:
        raise ValueError(f"No company ID for {client_id}. Re-run auth.")
    return company_id


# ---------------------------------------------------------------------------
# OAuth flow — manual copy/paste approach
# ---------------------------------------------------------------------------
def run_auth_flow(client_id: str):
    """
    Opens QuickBooks authorization in the browser.
    After approving, you copy the code and realmId from the redirect page
    and paste them here.
    """
    params = {
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "scope":         SCOPES,
        "redirect_uri":  REDIRECT_URI,
        "state":         "financialreports",
    }
    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(params)

    print("\n" + "=" * 60)
    print("  QUICKBOOKS AUTHORIZATION")
    print("=" * 60)
    print("\nStep 1: Your browser will open the QuickBooks login page.")
    print("        Log in and click 'Connect' to approve access.\n")
    print("Step 2: After approving, you'll land on a page with a URL")
    print("        that contains 'code=' and 'realmId=' in it.")
    print("        Copy those two values and paste them below.\n")
    print("Opening browser now...")
    webbrowser.open(auth_url)

    print("\n" + "-" * 60)
    auth_code = input("Paste the 'code' value here: ").strip()
    realm_id  = input("Paste the 'realmId' value here: ").strip()
    print("-" * 60)

    if not auth_code or not realm_id:
        print("\nError: Both code and realmId are required.")
        sys.exit(1)

    # Exchange auth code for tokens
    print("\nExchanging code for tokens...")
    response = requests.post(
        TOKEN_URL,
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={
            "grant_type":   "authorization_code",
            "code":         auth_code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Accept": "application/json"},
    )

    if response.status_code != 200:
        print(f"\nError getting tokens: {response.status_code}")
        print(response.text)
        sys.exit(1)

    tokens = response.json()
    tokens["company_id"] = realm_id
    save_tokens(client_id, tokens)

    print("\n  QuickBooks connected successfully!")
    print(f"  Company ID : {realm_id}")
    print(f"  Client     : {client_id}")
    print("\nYou can now run: python generate_all_reports.py")


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.quickbooks.auth <client_id>")
        print("Example: python -m src.quickbooks.auth riverside_home_goods")
        sys.exit(1)

    run_auth_flow(sys.argv[1])
