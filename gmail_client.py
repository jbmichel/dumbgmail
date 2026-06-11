"""Thin Gmail read helpers. (No writes yet — dry-run phase.)"""

from email.utils import parseaddr

import config

_HEADERS = ["From", "To", "Cc", "Subject", "List-Unsubscribe", "List-Id", "Reply-To"]


def _header_map(msg) -> dict[str, str]:
    return {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}


def fetch_unread(gmail) -> list[dict]:
    """Return a list of lightweight message dicts for unread inbox mail.

    Each dict carries everything the classifier needs: sender, subject, snippet,
    and the mechanical signals (recipient count, marketing headers) that help
    distinguish a personal note from a bulk send.
    """
    refs = []
    page_token = None
    while len(refs) < config.UNREAD_MAX_MESSAGES:
        resp = (
            gmail.users()
            .messages()
            .list(
                userId="me",
                q=config.UNREAD_QUERY,
                maxResults=min(500, config.UNREAD_MAX_MESSAGES - len(refs)),
                pageToken=page_token,
            )
            .execute()
        )
        refs.extend(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    out = []
    for ref in refs:
        msg = (
            gmail.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=_HEADERS,
            )
            .execute()
        )
        headers = _header_map(msg)
        from_name, from_email = parseaddr(headers.get("From", ""))
        to_count = len(_split_recipients(headers.get("To", "")))
        cc_count = len(_split_recipients(headers.get("Cc", "")))
        out.append(
            {
                "id": ref["id"],
                "from_name": from_name,
                "from_email": from_email.lower(),
                "subject": headers.get("Subject", "(no subject)"),
                "snippet": msg.get("snippet", ""),
                "recipient_count": to_count + cc_count,
                "has_list_unsubscribe": "List-Unsubscribe" in headers,
                "is_list_mail": "List-Id" in headers,
            }
        )
    return out


def _split_recipients(value: str) -> list[str]:
    from email.utils import getaddresses

    return [addr for _, addr in getaddresses([value or ""]) if addr]


# --- Writes (Phase 1) -------------------------------------------------------

def ensure_labels(gmail, label_names: list[str]) -> dict[str, str]:
    """Create any missing labels (nested 'Triage/...' is created automatically)
    and return a {label_name: label_id} map."""
    existing = gmail.users().labels().list(userId="me").execute().get("labels", [])
    by_name = {lbl["name"]: lbl["id"] for lbl in existing}
    for name in label_names:
        if name not in by_name:
            created = (
                gmail.users()
                .labels()
                .create(
                    userId="me",
                    body={
                        "name": name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                )
                .execute()
            )
            by_name[name] = created["id"]
    return by_name


def add_label(gmail, msg_id: str, label_id: str) -> None:
    """Apply a label. Does NOT remove INBOX or UNREAD — no archiving."""
    gmail.users().messages().modify(
        userId="me", id=msg_id, body={"addLabelIds": [label_id]}
    ).execute()
