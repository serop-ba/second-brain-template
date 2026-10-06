# Make it yours

How to take the template from "demo data" to "the place my business actually runs". Do it in this order. Each step is a prompt you can paste into Claude Code (`claude` in this folder). More prompts are in [PROMPTS.md](PROMPTS.md).

## 0. Look first (5 min)

```bash
python3 brain.py serve
```

The demo is a fictional consultancy. Click through: the orbit map on Overview (each planet is a department, the moons are its documents, decisions and numbers), a department page, a metric (click it for its history), Library, Activity (the change history). That is the shape you're filling.

## 1. Let Claude interview you (10 min)

```
/init
```

It clears the demo, then asks about the business, the constraints, the numbers, the direction and how you want Claude to work with you, and files everything. Answer honestly: the constraints (hours, runway, what would make you quit) matter more than the pitch.

If your business looks like one of the starter profiles (`creator`, `service`, `saas`, `ecommerce`), Claude will offer to start from it.

## 2. Tune what it filed (20 min)

Open the console and read it back as a skeptic. Fix, in this order:

**Departments.** Only functions that actually get your hours. An empty department reads as coverage when it's neglect. Three to five is typical. Rename, change hours, or delete any of them.
> *"Remove the Product department; I don't have one yet. Move its notes to Delivery."*

**Metrics.** 3 to 8. For each, ask: *if this number goes up, is the business definitely better?* If not, it's a vanity metric. Each needs:
- a **definition** that says exactly what is counted (so you and Claude read it the same way),
- **bands** in your own terms: `healthy >= 3000`, `watch 1500-2999`, `bad < 1500`. Leave a band blank until you really know. A metric with no bands says "not scored", which is honest.
> *"Look at my metrics. Which are vanity metrics? What would you track instead? Set bands from my goal of 3,000 a month."*

**Bets.** At most three this quarter, each with a number that says it worked ("Wins if"), carried by a department. A bet with nothing scheduled this week is a finding, not a bet.

**Working rules.** Library, "Working rules". Claude reads this at the start of every session. Change the tone, add things it must always or never do.
> *"Update my working rules: be blunter, never recommend tools I haven't asked about, always give a number."*

## 3. Get the numbers flowing (30 min)

For each metric, decide: **by hand** or **automatic**?

- **By hand** (`metric set KEY VALUE`, or "+ Log a value" in the console): fine for anything you check weekly. The weekly loop asks for stale ones.
- **From a file**: any tool that exports a CSV works with the installed `csv-import`: rows `metric,date,value` in `automations/csv-import/inbox/`, then Refresh.
- **From an API**: install a pack or let Claude build one.
  ```
  /connect  pull my MRR from Stripe
  ```
  Packs: **Stripe** (MRR, subscriptions, 30-day revenue), **YouTube** (subscribers, views), **Meta Ads CSV** (spend, results, cost per result). Anything else: Claude builds it from `automations/_template` and checks the number against the source with you.

Keys live in `automations/.env` (gitignored). Claude is blocked from reading that file; you paste the key yourself. Use read-only or restricted keys wherever the service offers them.

## 4. Build the rhythm (weekly)

```
/weekly
```

Or hit **Weekly loop** in the console's Automations tab. It empties the inbox, refreshes numbers, marks each bet on track / at risk / stalled with evidence, asks you for the outcome of any decision past its review date, rewrites each department's brief, and writes one log entry. The brief and the log are what make next week's conversation smarter than this week's.

Between loops: `/record` when something happens (a decision, a price change, an experiment), `/ingest` when you read or hear something worth keeping, and dump everything else in the inbox.

**Files go in `drop/`.** Put a transcript, article or PDF in the `drop/` folder, then tell Claude `/ingest`. `python3 brain.py doc sweep` imports `.md`, `.txt`, `.vtt`, `.srt` (and `.pdf` if `pdftotext` is installed: `brew install poppler`) as sources and moves the originals to `drop/done/`. Anything it can't read (scans, Word, images) stays in `drop/` and Claude reads it itself. The inbox is different: short text notes and ideas, not files.

## 5. Extend it

| I want to... | Do |
|---|---|
| Track a new number | *"Add a metric for newsletter open rate under Marketing"* |
| Connect a new tool | `/connect` |
| Add a department | Console, Departments, **+ Add**, or *"Add a Support department"* |
| Keep a playbook | Library, **+ New document**, kind `playbook` |
| See what changed | Console, Activity, Change history |
| Undo a mistake | Change history, ↶ on that row (or `python3 brain.py revert N`) |

## When something goes wrong

- **"Refused by the database" or a message about append-only.** Working as designed. Past decisions and log entries can't be rewritten. Log a new entry that supersedes it.
- **A wrong number.** `metric set KEY VALUE --date YYYY-MM-DD` replaces that day. `metric delete-point KEY DATE` removes it.
- **I deleted something.** Change history, undo it. Or `python3 brain.py history --entity documents` to find it.
- **I want to start over.** `python3 brain.py backup`, then delete `data/brain.db`, then `python3 brain.py serve --no-open` and `/init`.
- **A pull fails.** The console shows which one and why; the metric keeps its last real value. `python3 brain.py refresh NAME` reruns just that one.
- **Port in use.** `python3 brain.py serve --port 8766`.

## Migrating from the markdown second brain

```bash
python3 tools/migrate_markdown.py /path/to/old-brain --dry-run     # shows what it found
python3 tools/migrate_markdown.py /path/to/old-brain               # backs up, then imports
```

It brings across the company page (as facts and a document), departments and their sections, goals and bets, decisions (with their outcomes), the log, notes and sources, metrics with bands and their full history, the weekly goals and priorities, and the finance ledger. Nothing is deleted from the old folder.
