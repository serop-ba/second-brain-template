# Second Brain for Founders

A business operating system that lives in plain markdown and is maintained by
Claude Code. Seven pages, one folder per department, one weekly loop.

It's not note-taking. It's a system that keeps a current picture of your
business, checks it against your goals, records what you tried and what you
decided — and remembers whether either was right.

## Setup

1. Install [Claude Code](https://claude.com/claude-code).
2. Clone this repo, then open it:
   ```bash
   git clone https://github.com/serop-ba/second-brain-template.git
   cd second-brain-template
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
| `departments/` | One folder per area of work — marketing, sales. What you tried, and where it's going |
| `wiki/` | People, competitors, sources, playbooks |
| `raw/` | Source documents you drop in |
| `automations/` | Scripts that pull your real numbers. Empty until you add one |
| `.mcp.json` | Live connections to outside tools. Ships empty |
| `CLAUDE.md` | How the system works — and your rules for how Claude works |

## Departments

The root pages answer *how is the business doing*. `departments/` answers
*what did we actually try, and did it work* — one folder per area you're
spending real time on.

```
departments/
  marketing/
    direction.md          ← strategy across channels
    ads/
      direction.md        ← what's live, what's working, what's dead
      experiments.md      ← every test, with a hypothesis and a read date
    content/
      direction.md
      experiments.md
  sales/
    direction.md
    experiments.md
```

Two files per unit, and they're the same split as the root: `direction.md` is
**state** (always current, edited in place), `experiments.md` is **events**
(append-only, never rewritten). Nothing new to learn as the repo grows.

Every experiment carries a **hypothesis** and a **read-on date** — the weekly
loop hunts down any that are past due and still unjudged, and moves the finding
into `direction.md` under *what's working* or *what's dead*. That last section
is the one that pays for the whole folder: it's what stops you re-running a
failed ad test in six months because it felt new again.

An experiment is a test you run. A decision is a commitment you make.
Experiments feed decisions; they don't replace them.

Metrics are still defined **once**, in `company.md`, tagged with the department
that owns them. Department numbers roll up into the same single `dashboard.md`
— departments get a section there, never a dashboard of their own.

Delete a department you aren't using. An empty folder reads as coverage when
it's really neglect.

## The idea

**State vs events.** `company`, `goals`, `dashboard`, `wiki` and every
`direction.md` are always current — edited in place. `log`, `decisions` and
every `experiments.md` are append-only and never edited. Keeping those apart is
what stops the whole thing turning into a pile.

**Predictions are what make it learn.** A decision log that records what you
decided is an archive. One that records *what you expected and when to check*
teaches you something. Every entry in `decisions.md` carries both — and every
experiment carries a hypothesis and a read date for the same reason.

**One loop, weekly.** Empty the inbox → pull the data → read any experiment
that's come due → rebuild the dashboard → check it against your bets → write
one log entry. Everything else is on demand.

**One dashboard.** A dashboard you have to visit four of is four dashboards.

## Commands

- `/init` — set it up (run once, first)
- `/ingest` — turn a file in `raw/` into a note
- "run the weekly loop" — the main rhythm
- "log an experiment: I'm testing X" — starts a test with a read date
- "add a department for support" — scaffolds a new unit
- "lint the brain" — health check for staleness, contradictions, stalled bets,
  and experiments nobody ever judged

## Optional: automations

`automations/` ships empty — a template script and setup instructions, no
scripts. When you want your real numbers flowing into the dashboard, ask
Claude: *"add an automation that pulls my Meta ad spend"* and it writes it,
filed under the department that owns those numbers:

```
automations/scripts/marketing/meta_ads.py  →  Output/analytics/marketing/
```

Scripts route their own output by folder — there's nothing to configure.
Needs Python; see [automations/README.md](automations/README.md).

## Optional: connections (MCP)

`.mcp.json` is where you plug the brain into outside tools — Stripe, Notion,
your ad platform, a database. It ships empty:

```json
{
  "mcpServers": {}
}
```

Add one by asking Claude (*"connect this repo to Stripe over MCP"*), or by hand:

```json
{
  "mcpServers": {
    "stripe": {
      "command": "npx",
      "args": ["-y", "@stripe/mcp", "--tools=all"],
      "env": { "STRIPE_SECRET_KEY": "${STRIPE_SECRET_KEY}" }
    },
    "notion": {
      "type": "http",
      "url": "https://mcp.notion.com/mcp"
    }
  }
}
```

Restart Claude Code after editing; check with `/mcp`.

**This file is committed to git.** Never put a real key in it — use
`${VAR}` and set the value in `automations/.env`, which is gitignored.

Rule of thumb: a script in `automations/` for anything the weekly loop needs
to run unattended, MCP for things worth asking about interactively. Doing both
for the same data is one too many.

Everything works without either of these.

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
