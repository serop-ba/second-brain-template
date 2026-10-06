# Architecture

For people (and Claude) changing the platform itself. Everything is Python 3.9+ standard library; the console is plain HTML/JS with no build step.

```
brain.py                    entry point -> core/cli.py
core/
  schema.sql                tables and the append-only rules
  db.py                     connection, audit triggers, actor context
  store.py                  every read/write of the business (profile, departments, documents, goals, bets, tasks, decisions, log, inbox, history, revert, search)
  metrics.py                metric definitions, bands, verdicts, daily values
  views.py                  read models: `context` text for Claude, state for the console, "needs attention"
  cli.py                    argparse over store/metrics; the one write path for Claude
  server.py                 local HTTP server + JSON API for the console (127.0.0.1, per-launch token)
  jobs.py                   run scripts, headless Claude, terminals; output streaming
  refresh.py                run every automation's pull and record the points
  registry.py, packs.py     find automations, install catalog packs and profiles
  seed.py                   demo data (loads, clears exactly what it created)
  backup.py                 db copy, JSON export, restore
  graph.py                  rows -> nodes and links for the orbit map
  page/                     index.html, app.js, app.css, orbit.js
automations/                installed automations (+ _template)
drop/                       raw files to ingest; `doc sweep` (cli.py) imports them as sources and moves them to drop/done/
catalog/                    packs and profiles available to install
tools/migrate_markdown.py   import from the markdown second brain
tests/test_core.py          python3 -m unittest discover -s tests
```

## Data model

| Table | Purpose | Rule |
|---|---|---|
| `profile` | company facts (key/value) | state |
| `departments` | name, lead, hours, owns, intro, brief | state |
| `documents` | notes, sources, playbooks, and department page sections (`kind = section`, slug `dept/section`) | state |
| `goals` | north star + this year's goals | state |
| `bets` | this quarter's bets (`n` is the number people refer to) | state |
| `items` | weekly goals and daily priorities; `bet` is a bet number | state |
| `open_calls` | undecided questions | state |
| `metrics` | key, name, department, definition, unit, source, healthy/watch/bad bands | state |
| `metric_points` | one value per metric per day; `origin` is `manual`, an automation name, or `demo`; `deleted_at` tombstones a point removed by hand | state |
| `decisions` | title, decided, why, **expect**, **review_on**, outcome | **append-only** (outcome fillable later) |
| `log_entries` | timeline | **append-only** |
| `inbox` | quick capture; filing marks `filed_at` | state |
| `changes` | audit trail of every row change | **append-only, automatic** |
| `automation_runs`, `meta`, `ctx`, `demo_rows` | plumbing | not audited |

## The audit trail

`db.py` generates three triggers per audited table (insert, update, delete) that write the row's before/after JSON into `changes`, with `actor` and `reason` read from the one-row `ctx` table. `db.write(reason, who)` is the only way Python writes: it opens `BEGIN IMMEDIATE`, sets `ctx`, runs your statements, commits. So:

- raw SQL against the file is audited too (actor defaults to the last value left in `ctx`, but the change still exists),
- every change has an actor: `user` (CLI by a human), `claude` (CLI inside Claude Code, detected via `CLAUDECODE`), `console`, `automation:<name>`, `demo`; override with `BRAIN_ACTOR`,
- pulled metric points are *not* audited (they would drown the history); hand-entered ones are,
- `revert(change_id)` writes the old state back, which is itself audited.

Append-only rules are triggers in `schema.sql` (`RAISE(ABORT, ...)`) that read `ctx.purge`. Only `demo clear` sets `purge`, and nothing else can.

## Schema versions

`db.SCHEMA_VERSION` and `meta.schema_version`. To change the schema: edit `schema.sql` (use `CREATE TABLE IF NOT EXISTS`; for an `ALTER`, add a migration step in `db._ensure_schema` keyed on the old version), bump the version, add the new table to `db.AUDITED` and `db.WIPE_ORDER` if it holds content, update `CLAUDE.md`, and extend the tests. Triggers are regenerated whenever the version changes.

## The demo

`seed.load()` runs the seed under `actor = demo`, then records every new row id in `demo_rows`. `seed.clear()` deletes those rows (children first), their history, and the `demo_rows` entries, **except rows a non-demo actor has since changed**: those are yours now.

## Automations

A folder with `automation.json` and a script. The pull contract is JSON on stdout: `{"points": [{"metric", "value", "date"?}]}`. `refresh.py` runs each pull with `automations/.env` injected into its environment, records the points (unknown metric keys are reported, never created), and writes an `automation_runs` row. A failed pull never overwrites a value.

## Claude's boundaries

`.claude/settings.json` allows `python3 brain.py ...` and denies the database files; `.claude/hooks/guardrails.py` (PreToolUse) blocks secrets, destructive shell commands, force-pushes, and any `sqlite3` or `data/*.db` access. The `SessionStart` hook prints `brain.py context` so every session begins informed. Headless jobs from the console get only `Read`, `Glob`, `Grep` and `brain.py`.

## Console API

`GET /api/state|graph|doc|changes|search|jobs/<id>`, `POST /api/rpc {fn, args}` (a whitelist in `server.py` of store/metrics functions, so the UI and CLI share rules), `/api/run`, `/api/terminal`, `/api/backup`, `/api/refresh_at`. Every call needs the per-launch token and a `127.0.0.1`/`localhost` Host header.

## Tests

`python3 -m unittest discover -s tests` covers the audit trail (including raw SQL), append-only rules, revert, metric bands and tombstones, weekly carry-over, demo load/clear, backup/restore, the CLI flags, packs and the console API. The migration test runs when `BRAIN_MIGRATION_SOURCE=/path/to/markdown-brain` is set.
