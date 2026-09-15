# Automations

Empty on purpose. This is where scripts that pull your real numbers live —
channel stats, revenue, ad spend, whatever your business actually runs on.

Once a script exists here, the weekly loop runs it and its output lands in
`../dashboard.md`. Until then, everything else in the brain works fine without
it — fill in `company.md` and `goals.md` first and come back to this.

## Setup (one time)

Needs Python 3.9+. Check with `python3 --version`; if that fails, install it
from [python.org](https://www.python.org/downloads/) or `brew install python`
on a Mac.

```bash
cd automations
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then put your API keys in .env
```

`.env` and `.venv/` are gitignored. Never commit real keys.

## Adding one

Just ask Claude: *"add an automation that pulls my Stripe revenue"* — it
writes the script, adds the config, and updates this README. Or do it by hand:

1. Copy `scripts/example.py` to `scripts/<name>.py`.
2. Make it print one JSON object to stdout and save a timestamped copy to
   `../Output/analytics/`. `example.py` already does both.
3. Put anything configurable in `config/` — IDs, thresholds, account names —
   and anything secret in `.env`.
4. Add a row to the table below.
5. Tell Claude it exists, so it gets run during the weekly loop.

## The rules that matter

- **Never fake a number.** If a key is missing or an API fails, print a clear
  error and exit non-zero. A script that returns plausible-looking garbage is
  worse than one that crashes.
- **Read-only by default.** Scripts that pull data can run unattended.
  Anything that *acts* on the outside world — posting, emailing, charging —
  gets confirmed by a human every time, never scheduled silently.
- **Output is scratch.** `../Output/analytics/*.json` is a cache, safe to
  delete. The durable record is `../dashboard.md` (current numbers) and the
  weekly entry in `../log.md` (what they meant).

## Scripts

| Script | Needs | Does |
|---|---|---|
| _none yet_ | | |
