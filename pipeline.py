"""Shared triage pipeline used by both the dry run (main.py) and the
label-applying step (apply.py), so they classify identically."""

import config
import known_senders
from classifier import classify
from gmail_client import fetch_unread

REPORT_ORDER = ["people", "urgent", "digest_admin", "digest_fyi", "other"]


def triage(gmail, people, calendar) -> list[dict]:
    """Fetch unread inbox mail and classify each message. Read-only."""
    known = known_senders.build_known_set(gmail, people, calendar)
    allowlist = known_senders.load_allowlist()
    print(f"  known senders: {len(known)}  |  curated allowlist (people): {len(allowlist)}")

    messages = fetch_unread(gmail)
    print(f"  unread to triage: {len(messages)}\n")

    records = []
    for msg in messages:
        sender_known = msg["from_email"] in known
        if msg["from_email"] in allowlist:
            bucket, source, new_person, reason = (
                "people", "allowlist", False, "confirmed person on your allowlist",
            )
        else:
            c = classify(msg, sender_is_known=sender_known)
            bucket, source, new_person, reason = c.bucket, "llm", c.new_person_likely, c.reason
        records.append(
            {
                "id": msg["id"],
                "from_name": msg["from_name"],
                "from_email": msg["from_email"],
                "subject": msg["subject"],
                "snippet": msg["snippet"],
                "sender_known": sender_known,
                "bucket": bucket,
                "source": source,
                "new_person": new_person,
                "reason": reason,
            }
        )
    return records


def print_report(records: list[dict], header: str) -> None:
    label_by_key = {config.LABELS[k]: k for k in config.LABELS}
    rows = sorted(
        records,
        key=lambda r: REPORT_ORDER.index(
            label_by_key[config.LABELS[config.BUCKET_TO_LABEL[r["bucket"]]]]
        ),
    )
    print("=" * 80)
    print(header)
    print("=" * 80)
    current = None
    for r in rows:
        label = config.LABELS[config.BUCKET_TO_LABEL[r["bucket"]]]
        if label != current:
            print(f"\n## {label}")
            current = label
        sender = r["from_name"] or r["from_email"]
        flag = " [NEW PERSON?]" if r["new_person"] else ""
        print(f"  - {sender}{flag}")
        print(f"      subj: {r['subject']}")
        print(f"      why : [{r['source']}] {r['reason']}")

    print("\n" + "-" * 80)
    counts: dict[str, int] = {}
    for r in records:
        lbl = config.LABELS[config.BUCKET_TO_LABEL[r["bucket"]]]
        counts[lbl] = counts.get(lbl, 0) + 1
    for k in config.LABELS:
        print(f"  {config.LABELS[k]}: {counts.get(config.LABELS[k], 0)}")
