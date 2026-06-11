"""Detect when the user re-labels a message we triaged, and learn from it.

On each run we check messages labeled in the last 2 days. If the current
Triage/* label differs from what we applied, we record the correction and
update the allowlist when a sender is promoted to People.
"""

import json
import os
from datetime import datetime, timezone, timedelta

import config
import known_senders

LOOKBACK = timedelta(days=2)


def load_applied() -> list[dict]:
    if not os.path.exists(config.APPLIED_LABELS_FILE):
        return []
    with open(config.APPLIED_LABELS_FILE) as f:
        return json.load(f)


def save_applied(existing: list[dict], new_records: list[dict]) -> list[dict]:
    """Append newly labeled records; prune entries older than 30 days."""
    existing_ids = {r["id"] for r in existing}
    now = datetime.now(timezone.utc).isoformat()
    for r in new_records:
        if r["id"] not in existing_ids:
            existing.append({
                "id": r["id"],
                "from_email": r["from_email"],
                "from_name": r["from_name"],
                "label": config.LABELS[config.BUCKET_TO_LABEL[r["bucket"]]],
                "labeled_at": now,
            })
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    existing = [
        r for r in existing
        if datetime.fromisoformat(r["labeled_at"]).astimezone(timezone.utc) > cutoff
    ]
    with open(config.APPLIED_LABELS_FILE, "w") as f:
        json.dump(existing, f, indent=2)
    return existing


def check_and_learn(gmail) -> None:
    """Compare stored labels against current Gmail labels; learn from changes."""
    applied = load_applied()
    if not applied:
        return

    cutoff = datetime.now(timezone.utc) - LOOKBACK
    recent = [
        r for r in applied
        if datetime.fromisoformat(r["labeled_at"]).astimezone(timezone.utc) > cutoff
    ]
    if not recent:
        return

    all_labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
    triage_by_id = {l["id"]: l["name"] for l in all_labels if l["name"].startswith("Triage/")}

    corrections = []
    for record in recent:
        try:
            msg = gmail.users().messages().get(
                userId="me", id=record["id"], format="minimal"
            ).execute()
        except Exception:
            continue
        current = next(
            (triage_by_id[lid] for lid in msg.get("labelIds", []) if lid in triage_by_id),
            None,
        )
        if current and current != record["label"]:
            corrections.append((record, current))
            if current == config.LABELS["people"]:
                print(f"  [learn] {record['from_email']} promoted to People → allowlist")
                known_senders.add_to_allowlist(record["from_email"])

    if corrections:
        print(f"  corrections detected: {len(corrections)}")
        for record, current in corrections:
            sender = record["from_name"] or record["from_email"]
            print(f"    {record['label']} -> {current}  ({sender})")
