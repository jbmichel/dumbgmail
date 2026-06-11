"""Phase 1 — apply Triage/* labels to live unread mail.

Classifies the current unread inbox (same pipeline as the dry run), prints the
plan, then asks for confirmation before writing. It ONLY adds labels — it never
removes INBOX or UNREAD, so nothing is archived or marked read.

    ./run.sh apply.py            # interactive: prints plan, asks y/N
    ./run.sh apply.py --yes      # skip the prompt (explicit authorization)
"""

import json
import os
import sys

import config
import corrections
from auth import build_services
from gmail_client import ensure_labels, set_triage_label
from pipeline import print_report, triage

LAST_RUN_FILE = "last_run.json"


def main() -> None:
    auto_yes = "--yes" in sys.argv
    from_last = "--from-last" in sys.argv  # apply the saved plan; skip re-classifying

    print("Authenticating...")
    gmail, people, calendar = build_services()

    print("Checking for label corrections...")
    corrections.check_and_learn(gmail)

    if from_last:
        if not os.path.exists(LAST_RUN_FILE):
            print(f"No {LAST_RUN_FILE} — run a dry run first: ./run.sh")
            return
        with open(LAST_RUN_FILE) as f:
            records = json.load(f)
        print(f"Loaded {len(records)} classified messages from {LAST_RUN_FILE}")
    else:
        print("Building known-senders set & classifying...")
        records = triage(gmail, people, calendar)
        with open(LAST_RUN_FILE, "w") as f:
            json.dump(records, f, indent=2)

    print_report(records, "PLAN — labels to apply (nothing written yet)")

    if not records:
        print("\nNothing to label.")
        return

    if not auto_yes:
        sys.stdout.write(f"\nApply these {len(records)} labels in Gmail? [y/N] ")
        sys.stdout.flush()
        try:
            answer = sys.stdin.readline().strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer != "y":
            print("Aborted — nothing was changed.")
            return

    print("\nApplying labels...")
    label_ids = ensure_labels(gmail, list(config.LABELS.values()))
    all_triage_ids = list(label_ids.values())
    applied = 0
    for r in records:
        label_name = config.LABELS[config.BUCKET_TO_LABEL[r["bucket"]]]
        set_triage_label(gmail, r["id"], label_ids[label_name], all_triage_ids)
        applied += 1
    print(f"Done — applied {applied} label(s). Nothing was archived or marked read.")

    existing = corrections.load_applied()
    corrections.save_applied(existing, records)


if __name__ == "__main__":
    main()
