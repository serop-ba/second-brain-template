# Second Brain for Founders

A business operating system that lives in plain markdown and is maintained by
Claude Code. Seven files, three folders, one weekly loop.

It's not note-taking. It's a system that keeps a current picture of your
business, checks it against your goals, records the decisions you make — and
remembers whether they were right.

## Setup

1. Install [Claude Code](https://claude.com/claude-code).
2. Clone or download this repo, then open it:
   ```bash
   cd second-brain
   claude
   ```
3. Run `/init`. Claude interviews you about the business — about ten minutes —
   and fills in the scaffolding from your answers.

That's it. The rest fills itself in as you use it.

## What's in it

| File | What it holds |
|---|---|
| `company.md` | What the business is, what you sell, your constraints, what each metric means |
| `goals.md` | North star → this year → this quarter's bets |
| `dashboard.md` | Current state. Generated, not written by hand |
| `decisions.md` | Every decision with a prediction and a review date |
| `log.md` | Timeline of everything that happened |
| `inbox.md` | Dump zone. Emptied weekly |
| `notes/` | People, competitors, sources, playbooks |
| `raw/` | Source documents you drop in |
| `automations/` | Scripts that pull your real numbers. Empty until you add one |
| `CLAUDE.md` | How the system works — and your rules for how Claude works |

## The idea

**State vs events.** `company`, `goals`, `dashboard` and `notes` are always
current — edited in place. `log` and `decisions` are append-only and never
edited. Keeping those apart is what stops the whole thing turning into a pile.

**Predictions are what make it learn.** A decision log that records what you
decided is an archive. One that records *what you expected and when to check*
teaches you something. Every entry in `decisions.md` carries both.

**One loop, weekly.** Empty the inbox → pull the data → rebuild the dashboard
→ check it against your bets → write one log entry. Everything else is on
demand.

## Commands

- `/init` — set it up (run once, first)
- `/ingest` — turn a file in `raw/` into a note
- "run the weekly loop" — the main rhythm
- "lint the brain" — health check for staleness, contradictions, stalled bets

## Optional: automations

`automations/` ships empty — a template script and setup instructions, no
scripts. When you want your real numbers flowing into the dashboard, ask
Claude: *"add an automation that pulls my Stripe revenue"* and it writes it.
Needs Python; see [automations/README.md](automations/README.md).

Everything else works without it.

## License

MIT — use it, change it, ship it, sell what you build with it. No attribution
required.

## Notes

- Works with [Obsidian](https://obsidian.md) — it's all plain markdown with
  relative links.
- Claude edits these files directly. Keep it in git so you can always see what
  changed and roll back.
- `CLAUDE.md` is meant to be edited. It's the config for how Claude behaves in
  this repo — tone, rules, conventions. Change it as you learn what you want.
