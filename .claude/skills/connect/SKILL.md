---
name: connect
description: Connect a tool so a number reaches the dashboard automatically. Installs a use-case pack from the catalog (Stripe, YouTube, Meta Ads CSV, CSV import) or builds a new automation for any API or export, then verifies the number. Triggers on "connect", "pull my X automatically", "add an automation", "wire up Stripe".
---

# Connect

Goal: a metric on the dashboard that fills itself, and that you have checked against the source.

## 1. Decide what and from where

Ask: which number, and where does it live? Check what already exists:
`python3 brain.py automation list` (installed + catalog) and `python3 brain.py metric list`.

- A catalog pack fits (Stripe revenue, YouTube channel, Meta Ads CSV)? Use it: `python3 brain.py automation install NAME`. It copies the folder to `automations/NAME/`, creates its metrics, and prints which keys go in `automations/.env`.
- The tool can export a CSV? Use `csv-import` (already installed): rows `metric,date,value` into `automations/csv-import/inbox/`.
- Otherwise build one (step 3).

## 2. Keys

Tell the user exactly where to get the key and to prefer a **read-only / restricted** one. **Never read, print or write `automations/.env`.** The user pastes it themselves (`cp automations/.env.example automations/.env`, then edit). `automation list` shows which variables are still missing without revealing values.

## 3. Build a new one

1. Copy `automations/_template/` to `automations/<name>/` (Write the files; the folder name has no leading underscore).
2. `automation.json`: label, description, `department` slug, `env` (variable names), `metrics` it feeds (key, name, unit, definition), `pull`.
3. `pull.py`: **standard library only** (`urllib.request`), secrets from `os.environ`, a hard timeout, no writes to the outside world. It prints `{"points": [{"metric": "key", "value": 123, "date": "YYYY-MM-DD"}]}` to stdout, logs to stderr, and exits non-zero with a clear message on failure. See `automations/README.md` for the contract.
4. Add the metrics: `python3 brain.py metric add KEY --name ... --dept ... --definition ...` (install does this for packs). Bands only if the user knows them.

## 4. Verify, don't trust

`python3 brain.py refresh NAME`, then `metric show KEY`. Ask the user to compare the value with what the source's own dashboard shows today. If they differ, the script is wrong: fix it before reporting success. Log it: `log add --type change --title "Connected NAME" --body "feeds KEY; verified against ..."`.

Mention the console's **Refresh** button and the optional daily refresh (Automations tab).
