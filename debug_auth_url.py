"""Quick debug — prints the exact authorization URL we're sending to QuickBooks."""
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID    = os.getenv("QB_CLIENT_ID")
REDIRECT_URI = os.getenv("QB_REDIRECT_URI", "http://localhost:8000/callback")

params = {
    "client_id":     CLIENT_ID,
    "response_type": "code",
    "scope":         "com.intuit.quickbooks.accounting",
    "redirect_uri":  REDIRECT_URI,
    "state":         "teststate123",
}

url = "https://appcenter.intuit.com/connect/oauth2?" + urllib.parse.urlencode(params)

print("\nRedirect URI in .env:")
print(f"  '{REDIRECT_URI}'")
print(f"\nFull auth URL:")
print(f"  {url}")
