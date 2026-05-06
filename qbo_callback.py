"""
qbo_callback.py
---------------
A tiny Flask web server that handles the QuickBooks OAuth callback automatically.

Instead of asking clients to copy-paste codes, they click "Connect QuickBooks",
log in, and tokens are saved automatically. Much cleaner.

HOW IT WORKS:
  1. You run this script — it starts a local web server on port 5000
  2. ngrok gives it a public URL (e.g. https://abc123.ngrok-free.app)
  3. You put that URL in your Intuit Developer app as the Redirect URI
  4. When a client clicks your auth link and approves, QuickBooks sends
     the code directly to your running server — tokens saved automatically

HOW TO RUN:
  python qbo_callback.py

  On first run it will ask for your ngrok authtoken (free at ngrok.com).
  After that, just run the script and it handles everything.

STOP THE SERVER:
  Press Ctrl+C in the terminal window.

NOTE: This must be running when a client clicks the auth link.
      For real clients you'd run this on a cheap VPS ($5/mo DigitalOcean).
      For testing, your laptop + ngrok is fine.
"""

import os
import sys
import json
import time
import pathlib
import sqlite3
import threading
import webbrowser
import subprocess
import urllib.parse

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from flask import Flask, request, redirect

# ── Config ────────────────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("QB_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET", "")
ENVIRONMENT   = os.getenv("QB_ENVIRONMENT", "sandbox")
TOKEN_URL     = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
PORT          = 5000
TOKENS_DIR    = ROOT / "clients" / "tokens"

app = Flask(__name__)

# ── Token storage (same format as qbo_auth.py) ───────────────────────────────
def _save_tokens(client_id: str, tokens: dict):
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    tokens["saved_at"] = time.time()
    path = TOKENS_DIR / f"{client_id}_tokens.json"
    path.write_text(json.dumps(tokens, indent=2))

    # Also update clients.db with the company_id
    db_path = ROOT / "clients.db"
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE clients SET qbo_company_id = ?, qbo_refresh_token = ?, "
            "updated_at = date('now') WHERE client_id = ?",
            (tokens.get("company_id"), tokens.get("refresh_token"), client_id)
        )
        conn.commit()
        conn.close()

    print(f"\n  Tokens saved for {client_id}")
    print(f"  Company ID : {tokens.get('company_id')}")
    print(f"  File       : {path}")


# ── OAuth callback endpoint ───────────────────────────────────────────────────
@app.route("/callback")
def oauth_callback():
    """
    QuickBooks redirects here after the client approves access.
    URL looks like: /callback?code=AB11...&realmId=1234...&state=client_id
    """
    error     = request.args.get("error")
    code      = request.args.get("code")
    realm_id  = request.args.get("realmId")
    client_id = request.args.get("state", "unknown_client")

    # ── Handle errors ─────────────────────────────────────────────────────
    if error:
        print(f"\n  QB Auth error for {client_id}: {error}")
        return _html_page(
            title  = "Authorization Failed",
            icon   = "X",
            color  = "#e74c3c",
            body   = f"""
                <p>QuickBooks returned an error: <strong>{error}</strong></p>
                <p>Please close this window and try again, or contact
                   <a href="mailto:{os.getenv('SMTP_USER','')}">
                   {os.getenv('REPORT_AUTHOR','your advisor')}</a>.</p>
            """
        ), 400

    if not code or not realm_id:
        return _html_page(
            title = "Missing Parameters",
            icon  = "?",
            color = "#e67e22",
            body  = "<p>Missing code or realmId. Please try the authorization link again.</p>"
        ), 400

    # ── Exchange code for tokens ──────────────────────────────────────────
    import requests as req_lib

    redirect_uri = os.getenv(
        "QB_REDIRECT_URI",
        f"http://localhost:{PORT}/callback"
    )

    try:
        resp = req_lib.post(
            TOKEN_URL,
            auth=(CLIENT_ID, CLIENT_SECRET),
            data={
                "grant_type":   "authorization_code",
                "code":         code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"\n  Token exchange failed for {client_id}: {e}")
        return _html_page(
            title = "Connection Failed",
            icon  = "X",
            color = "#e74c3c",
            body  = f"<p>Could not complete QuickBooks connection: {e}</p>"
        ), 500

    tokens = resp.json()
    tokens["company_id"] = realm_id
    _save_tokens(client_id, tokens)

    # ── Trigger baseline analysis in background ───────────────────────────
    print(f"\n  Starting baseline analysis for {client_id}...")
    threading.Thread(
        target=_run_baseline,
        args=(client_id,),
        daemon=True
    ).start()

    # ── Return success page to client ─────────────────────────────────────
    author  = os.getenv("REPORT_AUTHOR", "Your Advisor")
    company = os.getenv("COMPANY_NAME", "Shah Consultant")
    return _html_page(
        title = "QuickBooks Connected!",
        icon  = "OK",
        color = "#27ae60",
        body  = f"""
            <p>Your QuickBooks account has been connected successfully.</p>
            <p>We are now pulling your financial history in the background.
               You will receive a baseline analysis report within the hour.</p>
            <br>
            <p style="color:#666;font-size:14px;">
               You can close this window.<br>
               Questions? Email <a href="mailto:{os.getenv('SMTP_USER','')}">
               {author} at {company}</a>.
            </p>
        """
    )


def _run_baseline(client_id: str):
    """Run generate_baseline.py for this client in a background thread."""
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "generate_baseline.py"), client_id],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print(f"\n  Baseline analysis complete for {client_id}")
        else:
            print(f"\n  Baseline analysis failed for {client_id}:")
            print(result.stderr[-500:] if result.stderr else "(no output)")
    except Exception as e:
        print(f"\n  Baseline error for {client_id}: {e}")


# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return _html_page(
        title = "QB Callback Server Running",
        icon  = "OK",
        color = "#2e86ab",
        body  = f"""
            <p>The QuickBooks OAuth callback server is running.</p>
            <p>Send clients to their authorization URL to connect their accounts.</p>
            <br>
            <p style="color:#666;font-size:13px;">
                Environment: <strong>{ENVIRONMENT.upper()}</strong><br>
                Server: <strong>localhost:{PORT}</strong>
            </p>
        """
    )


# ── HTML response helper ──────────────────────────────────────────────────────
def _html_page(title: str, icon: str, color: str, body: str) -> str:
    company = os.getenv("COMPANY_NAME", "Shah Consultant")
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title} — {company}</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; background: #f5f7fa;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh; margin: 0; }}
    .card {{ background: white; border-radius: 12px; padding: 48px 56px;
             max-width: 480px; text-align: center;
             box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .icon {{ font-size: 48px; color: {color}; font-weight: 900;
             border: 4px solid {color}; border-radius: 50%;
             width: 80px; height: 80px; line-height: 72px;
             margin: 0 auto 24px; }}
    h2 {{ color: #1b2a4a; margin: 0 0 20px; font-size: 22px; }}
    p  {{ color: #444; line-height: 1.6; margin: 8px 0; }}
    .brand {{ margin-top: 32px; font-size: 12px; color: #aaa; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h2>{title}</h2>
    {body}
    <div class="brand">{company} — Automated Financial Reporting</div>
  </div>
</body>
</html>"""


# ── ngrok setup ───────────────────────────────────────────────────────────────
def _start_ngrok() -> str:
    """
    Start ngrok tunnel and return the public URL.
    On first run, prompts for authtoken.
    """
    try:
        from pyngrok import ngrok, conf

        # Check if authtoken is configured
        ngrok_token = os.getenv("NGROK_AUTHTOKEN", "")
        if ngrok_token:
            conf.get_default().auth_token = ngrok_token
        else:
            # Check if already saved
            try:
                tunnel = ngrok.connect(PORT, "http")
                return tunnel.public_url
            except Exception:
                pass

            print("\n" + "=" * 60)
            print("  NGROK SETUP (one-time)")
            print("=" * 60)
            print("\n  ngrok gives your laptop a public URL so QuickBooks")
            print("  can send the authorization back to you automatically.\n")
            print("  1. Go to https://ngrok.com and create a FREE account")
            print("  2. Go to https://dashboard.ngrok.com/get-started/your-authtoken")
            print("  3. Copy your authtoken and paste it below\n")

            token = input("  Paste your ngrok authtoken here: ").strip()
            if not token:
                print("  Skipping ngrok — using manual copy-paste flow instead.")
                return ""

            # Save to .env
            env_path = ROOT / ".env"
            env_text = env_path.read_text(encoding="utf-8")
            if "NGROK_AUTHTOKEN" not in env_text:
                env_path.write_text(
                    env_text.rstrip() + f"\nNGROK_AUTHTOKEN={token}\n",
                    encoding="utf-8"
                )
            conf.get_default().auth_token = token

        tunnel = ngrok.connect(PORT, "http")
        return tunnel.public_url.replace("http://", "https://")

    except ImportError:
        print("  pyngrok not installed. Run: pip install pyngrok")
        return ""
    except Exception as e:
        print(f"  ngrok failed: {e}")
        print("  Falling back to manual copy-paste flow.")
        return ""


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print()
    print("=" * 60)
    print("  QB OAUTH CALLBACK SERVER")
    print("=" * 60)

    # Try to start ngrok
    print("\n  Starting ngrok tunnel...")
    public_url = _start_ngrok()

    if public_url:
        callback_url = f"{public_url}/callback"
        print(f"\n  Public URL  : {public_url}")
        print(f"  Callback URL: {callback_url}")
        print()
        print("  IMPORTANT — do this once:")
        print(f"  1. Go to developer.intuit.com -> your app -> Keys & OAuth")
        print(f"  2. Add this as a Redirect URI:")
        print(f"     {callback_url}")
        print(f"  3. Also update QB_REDIRECT_URI in your .env to:")
        print(f"     QB_REDIRECT_URI={callback_url}")
        print()
        print("  Then use this URL pattern to send clients to authorize:")
        print(f"  python onboard_client.py  (will include the right auth link)")
    else:
        print("\n  Running without ngrok — using manual copy-paste flow.")
        print("  Clients will need to send you the code and realmId manually.")

    print()
    print("  Server starting on http://localhost:5000")
    print("  Press Ctrl+C to stop.")
    print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=PORT, debug=False)


if __name__ == "__main__":
    main()
