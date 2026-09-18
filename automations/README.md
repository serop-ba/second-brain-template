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

## Layout

Scripts are filed by the department that owns the numbers they pull, matching
`../departments/`:

```
scripts/
  example.py              → Output/analytics/company/
  marketing/
    meta_ads.py           → Output/analytics/marketing/
  sales/
    stripe.py             → Output/analytics/sales/
```

`example.py` finds the repo root by walking up to `CLAUDE.md` and reads its own
department from its parent folder, so nesting routes output on its own — there
is nothing to configure. A script sitting directly in `scripts/` is treated as
company-wide.

## Adding one

Just ask Claude: *"add an automation that pulls my Meta ad spend"* — it
writes the script, files it under the right department, adds the config, and
updates this README. Or do it by hand:

1. Copy `scripts/example.py` to `scripts/<department>/<name>.py`.
2. Replace `fetch()`. Return the metrics under the **same names used in
   `../company.md`'s metrics table** — that's what lets the dashboard place
   them with no translation layer in between.
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
- **Output is scratch.** `../Output/analytics/**/*.json` is a cache, safe to
  delete. The durable record is `../dashboard.md` (current numbers), the unit's
  `direction.md` and `experiments.md` (what they meant), and the weekly entry
  in `../log.md`.

## Scripts

| Script | Department | Needs | Does |
|---|---|---|---|
| _none yet_ | | | |
