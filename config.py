"""Configuration for the inbox triage assistant.

Everything that is *about you* lives here. The classifier reads PROFILE so it
can recognize a real person reaching out for the first time (e.g. "Hi, this is
Sarah, your son's new piano teacher") even when that sender has no history.

Fill in the placeholders below before running.
"""

# --- Who you are, so the LLM can spot personal / household-relevant mail ------
PROFILE = {
    "your_name": "JB Michel (Jean-Baptiste Michel)",
    "your_email": "jb.michel@gmail.com",
    # First names the model should treat as "people in my life" if mentioned.
    "family_members": [
        "Ina Popova (spouse)",
        "Leo Michel-Popov",
        "Jules Michel-Popov",
        "Anais Michel-Popova",
    ],
    # Ongoing household admin contexts. Be concrete — these are the things that
    # make an admin email "urgent today" vs. "digest".
    "household_contexts": [
        "Building a house upstate (construction project)",
        "End-of-school-year logistics",
        "Summer camps for the kids",
        "Taxes",
        "Passports / travel documents",
    ],
    # Kid-related contexts.
    "kids_contexts": [
        "School: UNIS (United Nations International School)",
        "School: Smith Street Maternelle",
        "School: Riverdale",
    ],
    # Anything else worth knowing — neighborhood, city, profession, etc.
    "other_notes": [
        "Lives in Brooklyn, NY",
        "Profession: investor and biotech/scientist. Legitimately receives "
        "first-time/cold email from founders, researchers, and people he has "
        "just met. Treat a substantive, personally-written professional message "
        "from a real individual as 'people' (new_person_likely=True) — but mass "
        "fundraising blasts, generic sales pitches, and marketing still go to digest.",
    ],
}

# --- Model -------------------------------------------------------------------
# Per-email classification. Haiku is plenty for sorting mail and ~5x cheaper;
# bump to "claude-opus-4-8" only if daily accuracy on people/urgent needs it.
MODEL = "claude-haiku-4-5"

# --- Gmail labels we propose (label-only; we never archive) ------------------
LABELS = {
    "people": "Triage/People",    # real people you know -> primary view
    "urgent": "Triage/Urgent",    # today-urgent admin -> primary view
    "digest": "Triage/Digest",    # everything else worth a daily glance
    "other": "Triage/Other",      # bulk lists you'll never read -> not shown
}

# Map a classifier bucket to a Gmail label key above.
BUCKET_TO_LABEL = {
    "people": "people",
    "urgent_admin": "urgent",
    "digest": "digest",
    "other": "other",
}

# --- Scopes ------------------------------------------------------------------
# Requested up front so we don't have to re-consent when we move from dry-run
# (read) to applying labels (modify) to sending the digest (send).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",        # read + label
    "https://www.googleapis.com/auth/gmail.send",          # daily digest email
    "https://www.googleapis.com/auth/contacts.readonly",   # widen "known" set
    "https://www.googleapis.com/auth/calendar.readonly",   # widen "known" set
]

# --- Local state files -------------------------------------------------------
import os as _os

# On Railway, mount a volume at /data and set DATA_DIR=/data.
# Locally, files live next to the source.
_DATA_DIR = _os.environ.get("DATA_DIR", _os.path.dirname(_os.path.abspath(__file__)))

CREDENTIALS_FILE = _os.path.join(_DATA_DIR, "credentials.json")
TOKEN_FILE = _os.path.join(_DATA_DIR, "token.json")
ALLOWLIST_FILE = _os.path.join(_DATA_DIR, "allowlist.json")

# How far back to look when building the known-senders set from Sent mail.
SENT_LOOKBACK_QUERY = "in:sent newer_than:2y"
SENT_MAX_MESSAGES = 2000

# Everything in Primary inbox not yet labeled by us — catches read and unread.
TRIAGE_QUERY = (
    "in:inbox category:primary"
    " -label:Triage/People"
    " -label:Triage/Urgent"
    " -label:Triage/Digest"
    " -label:Triage/Other"
)
TRIAGE_MAX_MESSAGES = 250  # safety cap

# Known-senders cache
KNOWN_SENDERS_CACHE_FILE = _os.path.join(_DATA_DIR, "known_senders_cache.json")
KNOWN_SENDERS_CACHE_TTL_HOURS = 6

# Applied-labels log (for learning from user corrections)
APPLIED_LABELS_FILE = _os.path.join(_DATA_DIR, "applied_labels.json")
