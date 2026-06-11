"""LLM classification for senders not already in the deterministic known-set.

This is where the "new person I might know" case is handled: the model gets a
short profile of you plus the email's mechanical signals, and decides whether
this looks like a real person writing to you personally (-> primary view) or
admin/noise (-> urgent vs. digest).
"""

import json
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

import config

_client = anthropic.Anthropic()


class Classification(BaseModel):
    bucket: Literal["people", "urgent_admin", "digest", "other"] = Field(
        description=(
            "people = a real individual human writing to you personally; "
            "urgent_admin = household/kids admin needing action TODAY "
            "(appointment to confirm, tax/investment deadline, construction, "
            "time-sensitive school item); "
            "digest = all other mail worth a daily glance — admin, receipts, "
            "account/payment notices, security alerts, school broadcasts, "
            "informational newsletters from orgs you belong to; "
            "other = bulk promotional/marketing/sales and brand/retail/newsletter "
            "lists you don't engage with and will likely never read."
        )
    )
    new_person_likely: bool = Field(
        description=(
            "True ONLY if this is a real individual writing you a personal, 1:1 "
            "message for the first time (no prior relationship). An invitation, "
            "announcement, or outreach from an organization/institution — even if "
            "it addresses you by name — is NOT this."
        )
    )
    reason: str = Field(description="One short sentence explaining the decision.")


def _profile_block() -> str:
    p = config.PROFILE
    lines = [f"Name: {p['your_name']} <{p['your_email']}>"]
    if p["family_members"]:
        lines.append("Family members: " + ", ".join(p["family_members"]))
    if p["household_contexts"]:
        lines.append("Household admin contexts:\n  - " + "\n  - ".join(p["household_contexts"]))
    if p["kids_contexts"]:
        lines.append("Kids contexts:\n  - " + "\n  - ".join(p["kids_contexts"]))
    if p["other_notes"]:
        lines.append("Other: " + "; ".join(p["other_notes"]))
    return "\n".join(lines)


SYSTEM = f"""You triage one email at a time for a busy person. Decide which bucket it belongs in.

ABOUT THE USER (use this to recognize people and household/kids relevance):
{_profile_block()}

GUIDANCE:
- 'people' is a NARROW, high-value bucket: reserve it for a message an actual
  individual human personally wrote to you (1:1, conversational). A genuine
  first-time personal note from someone the user would plausibly know counts
  (a new teacher, a contractor's staff, a referral, a friend on a new address) —
  set new_person_likely=True for those.
- 'sender_is_known' tells you the sender is in the user's contacts/sent/calendar
  history. This means a real relationship EXISTS, but it does NOT by itself make
  the email 'people'. Decide by CONTENT. Automated, transactional, billing,
  portal, broadcast, or invitation mail is digest/other EVEN from a known sender
  or a known address. Examples the user has corrected:
    * A homework-portal notice or a billing/invoice notice from a school or
      service the family uses, even from a known address -> digest_fyi (NOT people).
    * An event invitation from a museum/institution that addresses you by name
      -> digest_fyi (NOT people, NOT new_person).
- Be skeptical of unsolicited sales pitches and marketing dressed up to look
  personal (List-Unsubscribe header, mailing list, no-reply sender, many
  recipients, promotional language) -> 'other'.
- 'urgent_admin' is RARE: only household/kids items that must be acted on TODAY —
  a real same-day deadline or a time-critical request. Routine appointment
  confirmations and "your appointment is coming up" reminders are NOT urgent ->
  digest. When unsure between urgent and non-urgent, choose digest.
- Distinguish 'digest' from 'other':
    * digest = informational/transactional mail tied to services, accounts, or
      organizations the user actually uses or belongs to. Examples: payment
      receipts, account/security notices, school broadcasts, admin mail that
      isn't urgent today.
    * other = bulk promotional, marketing, sales, and brand/retail/newsletter
      lists the user does not engage with and will likely never read. Examples:
      retail sale emails, streaming-service promos, commercial real-estate blasts,
      generic brand newsletters.
  Rule of thumb: a receipt or notice from a service the user uses -> digest;
  a marketing blast from a brand -> other.
- The user reads 'people' and 'urgent_admin' in their primary inbox; 'digest'
  goes into a once-daily digest; 'other' is filed away and not shown. Optimize
  above all for not burying real humans or genuinely time-sensitive items, and
  for keeping pure marketing out of the digest."""


def classify(msg: dict, sender_is_known: bool = False) -> Classification:
    signals = {
        "from": f"{msg['from_name']} <{msg['from_email']}>",
        "subject": msg["subject"],
        "snippet": msg["snippet"],
        "sender_is_known": sender_is_known,
        "recipient_count": msg["recipient_count"],
        "has_list_unsubscribe_header": msg["has_list_unsubscribe"],
        "is_mailing_list": msg["is_list_mail"],
    }
    resp = _client.messages.parse(
        model=config.MODEL,
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(signals, indent=2)}],
        output_format=Classification,
    )
    return resp.parsed_output
