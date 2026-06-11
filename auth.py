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


def _seed_from_env(env_var: str, dest_path: str) -> None:
    """Write a file from an env var if the file doesn't exist."""
    if os.path.exists(dest_path):
        return
    value = os.environ.get(env_var)
    if not value:
        return
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "w") as f:
        f.write(value)


def get_credentials() -> Credentials:
    _seed_from_env("GOOGLE_CREDENTIALS_JSON", config.CREDENTIALS_FILE)
    _seed_from_env("GOOGLE_TOKEN_JSON", config.TOKEN_FILE)

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
