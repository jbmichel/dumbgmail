"""Google OAuth (installed-app flow) and API client construction.

First run opens a browser for consent and writes token.json. Subsequent runs
reuse/refresh the token silently.
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config


def _seed_token_from_env() -> None:
    """Write token.json from GOOGLE_TOKEN_JSON env var if the file doesn't exist.

    This lets Railway pick up the token on first deploy without a browser flow.
    Once written to the volume, subsequent runs refresh it in place.
    """
    if os.path.exists(config.TOKEN_FILE):
        return
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if not token_json:
        return
    os.makedirs(os.path.dirname(config.TOKEN_FILE), exist_ok=True)
    with open(config.TOKEN_FILE, "w") as f:
        f.write(token_json)


def get_credentials() -> Credentials:
    _seed_token_from_env()

    creds = None
    if os.path.exists(config.TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, config.SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing {config.CREDENTIALS_FILE}. Download your OAuth client "
                    "credentials from the Google Cloud Console (see README) and place "
                    "the file here."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.CREDENTIALS_FILE, config.SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def build_services():
    """Return (gmail, people, calendar) API service clients."""
    creds = get_credentials()
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    people = build("people", "v1", credentials=creds, cache_discovery=False)
    calendar = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return gmail, people, calendar
