"""Interactive review of the last dry run.

Run this in a REAL terminal (Terminal.app / iTerm), not through an automation
wrapper — it reads single keypresses from /dev/tty.

For each message it shows the model's bucket. Press:
    SPACE  accept the model's call
    P      -> people    (also promotes the sender into your known allowlist)
    U      -> urgent
    D      -> digest
    O      -> other
    B      go back one
    Q      save and quit early

On exit it writes reviewed.json (your ground-truth labels) and updates
allowlist.json for anyone you marked as a person.

    ./run.sh review.py
"""

import json
import os
import sys
import termios
import tty

import config
import known_senders

LAST_RUN_FILE = "last_run.json"
REVIEWED_FILE = "reviewed.json"

KEYMAP = {  # keypress -> fine-grained bucket
    "p": "people",
    "u": "urgent_admin",
    "d": "digest_fyi",
    "o": "other",
}
COARSE = {
    "people": "PEOPLE",
    "urgent_admin": "URGENT",
    "digest_admin": "DIGEST",
    "digest_fyi": "DIGEST",
    "other": "OTHER ",
}
_NON_PERSON = ("noreply", "no-reply", "donotreply", "do-not-reply")


class Keyboard:
    """Single-keypress reader bound to the controlling terminal (/dev/tty)."""

    def __init__(self):
        self.fd = os.open("/dev/tty", os.O_RDONLY)

    def read(self) -> str:
        old = termios.tcgetattr(self.fd)
        try:
            tty.setraw(self.fd)
            ch = os.read(self.fd, 1).decode("utf-8", "ignore")
        finally:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, old)
        if ch in ("\x03", "\x04"):  # Ctrl-C / Ctrl-D
            raise KeyboardInterrupt
        return ch.lower()

    def close(self):
        os.close(self.fd)


def _require_tty() -> "Keyboard":
    try:
        return Keyboard()
    except OSError:
        print(
            "ERROR: no controlling terminal (/dev/tty). Run this directly in a\n"
            "terminal window — not through an automation/`!` wrapper.",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    if not os.path.exists(LAST_RUN_FILE):
        print(f"No {LAST_RUN_FILE} found — run a dry run first: ./run.sh")
        return
    with open(LAST_RUN_FILE) as f:
        records = json.load(f)

    kb = _require_tty()
    print(f"Reviewing {len(records)} messages.")
    print("SPACE=ok   P=people   U=urgent   D=digest   O=other   B=back   Q=save & quit\n")

    try:
        i = 0
        while 0 <= i < len(records):
            r = records[i]
            sender = r["from_name"] or r["from_email"]
            cur = r["bucket"]
            flag = "  [NEW PERSON?]" if r.get("new_person") else ""
            print(f"[{i + 1:>2}/{len(records)}]  {COARSE[cur]}  {sender}{flag}")
            print(f"          {r['subject']}")
            print(f"          why: {r['reason']}")
            sys.stdout.write("          > ")
            sys.stdout.flush()

            key = kb.read()

            if key == "q":
                print("q  (quit)\n")
                break
            if key == "b":
                print("back\n")
                i = max(0, i - 1)
                continue
            if key in KEYMAP:
                r["final_bucket"] = KEYMAP[key]
                tag = COARSE[r["final_bucket"]].strip()
                print(f"-> {tag}{' (changed)' if r['final_bucket'] != cur else ''}\n")
            else:  # SPACE or any other key = accept
                r["final_bucket"] = cur
                print("ok\n")
            i += 1
    finally:
        kb.close()

    # Anything not reached counts as accepted.
    for r in records:
        r.setdefault("final_bucket", r["bucket"])

    with open(REVIEWED_FILE, "w") as f:
        json.dump(records, f, indent=2)

    # Reconcile the allowlist with this review: confirmed people get added,
    # senders you reviewed but did NOT mark as people get removed if present.
    existing = known_senders.load_allowlist()
    reviewed_emails = {r["from_email"] for r in records if r["from_email"]}
    confirmed_people = {
        r["from_email"]
        for r in records
        if r["final_bucket"] == "people"
        and r["from_email"]
        and not any(t in r["from_email"] for t in _NON_PERSON)
    }
    demoted = (existing & reviewed_emails) - confirmed_people
    promoted = sorted(confirmed_people - existing)
    known_senders.save_allowlist((existing | confirmed_people) - demoted)

    changed = [r for r in records if r["final_bucket"] != r["bucket"]]
    print("=" * 70)
    print(f"Reviewed: {len(records)}  |  accepted: {len(records) - len(changed)}  |  changed: {len(changed)}")
    if promoted:
        print(f"Promoted to allowlist (now deterministic 'people'): {len(promoted)}")
        for e in promoted:
            print(f"  + {e}")
    if demoted:
        print(f"Removed from allowlist (no longer 'people'): {len(demoted)}")
        for e in sorted(demoted):
            print(f"  - {e}")
    if changed:
        print("\nCorrections (model -> you):")
        for r in changed:
            sender = r["from_name"] or r["from_email"]
            print(f"  {COARSE[r['bucket']].strip():>6} -> {COARSE[r['final_bucket']].strip():<6}  {sender} | {r['subject'][:48]}")
    print("\nSaved reviewed.json — paste this summary back and I'll tune the classifier.")


if __name__ == "__main__":
    main()
