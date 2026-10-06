# Automations

An automation is a folder here with an `automation.json` and a script. It gets numbers from somewhere (an API, a CSV export, a database) and hands them to the brain. Delete the folder and it's gone; the metrics and their history stay.

```
automations/
  csv-import/    ships installed: drop a CSV (metric,date,value) in inbox/ and refresh
  _template/     copy this to start a new one (folders starting with _ are ignored)
  .env           your secrets (gitignored). Copy .env.example to create it
```

## The contract

A pull is any script that prints JSON to stdout:

```json
{"points": [{"metric": "mrr", "value": 1200, "date": "2026-10-05"}]}
```

`metric` is the key of a metric that already exists. `date` is optional (today). The refresh records each point as that day's value, in the audited database, with the automation's name as the source. A failed pull never overwrites anything: the metric keeps its last real value and the dashboard says when it last updated.

## Use-case packs

`catalog/automations/` holds ready-made packs (YouTube, Stripe, Meta Ads CSV). Install one:

```bash
python3 brain.py automation list
python3 brain.py automation install stripe
```

It copies the folder here, creates the metrics it feeds, and tells you which keys to put in `.env`.

## Build your own

Ask Claude: *"/connect: pull my newsletter subscriber count from Beehiiv"*. It copies `_template/`, writes the script, adds the metric, runs a refresh and checks the number. Rules it follows: standard library only, secrets only from `.env`, read-only API keys where possible.

## Running

```bash
python3 brain.py refresh            # every pull
python3 brain.py refresh stripe     # one automation
```

The console's **Refresh** button does the same, and can run it daily while it's open.
