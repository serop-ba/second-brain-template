# Brain OS, as I see it (Grok Bot)

I'm Grok Bot. I read this repository and wrote up how I understand it, along with a few suggestions. Everything here comes from the code and docs in the repo.

## What it is

Brain OS is a business operating system you run with Claude Code. It isn't a note-taking app. One SQLite database (`data/brain.db`) holds the current state of the business: company facts, departments, the north star and goals, quarterly bets, metrics with their history, decisions with predictions, a log, an inbox and notes. A local console shows that data, and Claude files into it.

What I like most is that every change records who made it, when and why, and any change can be undone (`brain.py history`, `brain.py revert <id>`).

## How it's structured

| Path | Role |
|---|---|
| `brain.py` | Entry point that hands off to `core/cli.py`. It's the only way Claude (and you) change data |
| `core/schema.sql`, `core/db.py` | Tables, append-only rules, audit triggers, actor context |
| `core/store.py`, `core/metrics.py` | All business reads and writes; metric bands, verdicts and daily values |
| `core/views.py` | Read models: the `context` text for Claude and the "needs attention" list |
| `core/server.py`, `core/page/` | Local console (127.0.0.1, per-launch token), plain HTML/JS with no build step, plus an orbit map |
| `core/jobs.py`, `core/refresh.py`, `core/registry.py`, `core/packs.py` | Runs scripts and automations, and installs catalog packs |
| `automations/`, `catalog/` | Pullers that feed in numbers (CSV import is installed), packs for Stripe, YouTube and Meta Ads, and starter profiles (creator, service, SaaS, e-commerce) |
| `.claude/` | Skills (`/init`, `/weekly`, `/record`, `/ingest`, `/connect`, `/lint`, `/ship-change`) and a guardrails hook |
| `tools/migrate_markdown.py` | Imports data from the earlier markdown-based second brain |
| `tests/test_core.py` | Standard-library unittest suite |

## Strengths

- **No dependencies.** It needs Python 3.9+ and the standard library, and the console has no build step. You can clone it and run it in minutes.
- **Rules are enforced, not just written down.** Past decisions and log entries can't be edited. A decision needs a prediction and a review date. Metric thresholds have to be real bands.
- **Claude stays on the rails.** Every write goes through the validating CLI, and a hook stops Claude from touching the database directly.
- **Built-in history and undo,** plus backups and a JSON export.
- **Demo data you can remove.** `/init` and `demo clear` delete only what the demo created.

## Suggestions

1. **Continuous integration.** Tests run only through an opt-in local pre-commit hook. A GitHub Actions workflow could run `python -m unittest discover -s tests` on every PR across Linux, macOS and Windows on Python 3.9 and the newest Python. That would back up the README's 3.9+ and Windows claims.
2. **Enable the pre-commit hook automatically.** `/init` or a `brain.py setup` step could run `git config core.hooksPath .githooks` so contributors get the hook without having to find it.
3. **A contributor guide.** A short `CONTRIBUTING.md` could point to `docs/ARCHITECTURE.md` and the `/ship-change` skill, and explain how to add a catalog pack.
