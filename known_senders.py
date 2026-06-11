"""Build the deterministic "people I know" set.

Three sources, all read-only:
  1. Sent mail   — anyone you've emailed (To/Cc) is someone you know.
  2. Contacts    — anyone in your address book, even if never emailed.
  3. Calendar    — anyone you've had a meeting with.
Plus a learned allowlist of senders you (or the dry-run review) have confirmed.

A hit here means "definitely known" and skips the LLM entirely.
"""

import json
import os
from email.utils import getaddresses

import config


def _emails_from_header_value(value: str) -> list[str]:
    # getaddresses handles "Name <a@b.com>, c@d.com" robustly.
    return [addr.lower() for _, addr in getaddresses([value or ""]) if addr]


def from_sent_mail(gmail) -> set[str]:
    known: set[str] = set()
    page_token = None
    fetched = 0
    while fetched < config.SENT_MAX_MESSAGES:
        resp = (
            gmail.users()
            .messages()
            .list(
                userId="me",
                q=config.SENT_LOOKBACK_QUERY,
                maxResults=min(500, config.SENT_MAX_MESSAGES - fetched),
                pageToken=page_token,
            )
            .execute()
        )
        ids = [m["id"] for m in resp.get("messages", [])]
        for mid in ids:
            msg = (
                gmail.users()
                .messages()
                .get(
                    userId="me",
                    id=mid,
                    format="metadata",
                    metadataHeaders=["To", "Cc"],
                )
                .execute()
            )
            for h in msg.get("payload", {}).get("headers", []):
                if h["name"] in ("To", "Cc"):
                    known.update(_emails_from_header_value(h["value"]))
            fetched += 1
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    known.discard(config.PROFILE["your_email"].lower())
    return known


def from_contacts(people) -> set[str]:
    known: set[str] = set()
    page_token = None
    while True:
        resp = (
            people.people()
            .connections()
            .list(
                resourceName="people/me",
                personFields="emailAddresses",
                pageSize=1000,
                pageToken=page_token,
            )
            .execute()
        )
        for person in resp.get("connections", []):
            for e in person.get("emailAddresses", []):
                if e.get("value"):
                    known.add(e["value"].lower())
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return known


def from_calendar(calendar) -> set[str]:
    known: set[str] = set()
    page_token = None
    while True:
        resp = (
            calendar.events()
            .list(
                calendarId="primary",
                maxResults=2500,
                singleEvents=True,
                pageToken=page_token,
            )
            .execute()
        )
        for event in resp.get("items", []):
            for att in event.get("attendees", []):
                if att.get("email") and not att.get("self"):
                    known.add(att["email"].lower())
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return known


def load_allowlist() -> set[str]:
    if os.path.exists(config.ALLOWLIST_FILE):
        with open(config.ALLOWLIST_FILE) as f:
            return {e.lower() for e in json.load(f)}
    return set()


def save_allowlist(emails: set[str]) -> None:
    with open(config.ALLOWLIST_FILE, "w") as f:
        json.dump(sorted(e.lower() for e in emails), f, indent=2)


def add_to_allowlist(email: str) -> None:
    current = load_allowlist()
    current.add(email.lower())
    save_allowlist(current)


def build_known_set(gmail, people, calendar) -> set[str]:
    known: set[str] = set()
    for label, fn, svc in (
        ("sent mail", from_sent_mail, gmail),
        ("contacts", from_contacts, people),
        ("calendar", from_calendar, calendar),
        ("allowlist", lambda _: load_allowlist(), None),
    ):
        try:
            found = fn(svc)
            known |= found
            print(f"  known from {label}: {len(found)}")
        except Exception as e:  # one source failing shouldn't sink the run
            print(f"  WARNING: could not read {label}: {e}")
    return known
