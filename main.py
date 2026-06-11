"""Dry-run inbox triage.

Reads unread inbox mail, decides where each message *would* go, prints a report,
and saves last_run.json for the review tool. Touches nothing in Gmail — no labels
applied, no archiving, no sending. Use this to tune classification.
"""

import json

from auth import build_services
from pipeline import print_report, triage

LAST_RUN_FILE = "last_run.json"


def main() -> None:
    print("Authenticating...")
    gmail, people, calendar = build_services()

    print("Building known-senders set & classifying...")
    records = triage(gmail, people, calendar)

    with open(LAST_RUN_FILE, "w") as f:
        json.dump(records, f, indent=2)

    print_report(records, "DRY RUN — proposed triage (nothing was changed in Gmail)")


if __name__ == "__main__":
    main()
