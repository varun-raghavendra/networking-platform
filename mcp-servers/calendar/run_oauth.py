"""Run OAuth flow - use console flow if browser can't open."""

import os

creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "secrets/credentials.json")
token_path = os.environ.get("GOOGLE_TOKEN_PATH", "secrets/token.json")

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

if os.path.exists(token_path):
    print("token.json already exists. Delete it to re-auth.")
    exit(0)

flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)

# Opens browser for auth. Run in your system Terminal (not Cursor) if browser doesn't auto-open.
print("Starting OAuth - a browser window should open. Sign in with varunraghavendra99@gmail.com\n")
creds = flow.run_local_server(port=0)

with open(token_path, "w") as f:
    f.write(creds.to_json())

print(f"\nSuccess! token.json saved to {token_path}")
