# Inbox Triage Assistant

Sorts unread Gmail into a **primary view** (real people you know + today-urgent
household/kids admin) and a **daily digest** (non-urgent admin + everything else
worth a glance). It applies Gmail **labels only** — it never archives or deletes.

## How it decides

1. **Deterministic known-set** — anyone in your Sent mail, Google Contacts, or
   Calendar (plus a learned allowlist) is "someone you know" → primary. No LLM call.
2. **LLM + your profile** — for unknown senders, Claude reads the email's signals
   and a short profile of you (family names, your construction project, kids'
   school, etc.) to decide: a real person writing personally (incl. plausible
   first-time contact) → primary; today-urgent admin → primary; else → digest.
3. **Learned allowlist** — confirmed new people get promoted into the
   deterministic set so they're recognized instantly next time.

## Phases

- **Phase 0 (now): dry run.** Read-only. Prints what it *would* label. Tune here.
- **Phase 1:** apply labels for real.
- **Phase 2:** compose & send the daily digest email.
- **Phase 3:** deploy to Railway on a schedule.

---

## One-time setup

### 1. Google Cloud (you do this — only you can)

1. Go to <https://console.cloud.google.com/> and create a new project (e.g. `inbox-triage`).
2. **APIs & Services → Library**, and enable: **Gmail API**, **People API**, **Google Calendar API**.
3. **APIs & Services → OAuth consent screen**: choose **External**, fill in app name + your email, and **add your own email (`jb.michel@gmail.com`) as a Test user**. (Testing mode is fine — no Google review needed for personal use.)
4. **APIs & Services → Credentials → Create credentials → OAuth client ID → Desktop app**. Download the JSON.
5. Save it in this folder as **`credentials.json`**.

### 2. Anthropic API key

```sh
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Python environment

```sh
cd /Users/jb/python/emailproject
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Fill in your profile

Edit `config.py` → `PROFILE`: family first names, your construction/tax/investment
contexts, kids' school, etc. This is what lets the model recognize a first-time
"Hi, I'm your son's new teacher" as a real person rather than noise.

---

## Run the dry run

```sh
python main.py
```

First run opens a browser for Google consent and writes `token.json`. After that
it runs silently. It reads your unread inbox and prints the proposed triage —
**nothing in Gmail changes.**

Review the output. When the calls look right, we move to Phase 1 (apply labels).
