# Brain OS

A business operating system you run with Claude Code. One database holds the whole picture of your business: the company, departments, goals and bets, every number with its history, every decision with a prediction, a timeline, and your notes. A local console draws it, and Claude files into it.

It isn't note-taking. It keeps a current picture of the business, checks it against your goals, records the decisions you make, and remembers whether they were right. **Every change is recorded: who made it, when, and why, and any change can be undone.**

## Start in five minutes

You need [Python 3.9+](https://www.python.org/downloads/) and [Claude Code](https://claude.com/claude-code). No packages to install.

```bash
git clone https://github.com/serop-ba/second-brain-template.git my-brain
cd my-brain
python3 brain.py serve        # opens the console, pre-filled with demo data (use `python` on Windows)
```

You'll see a fictional business so you know what a filled-in brain looks like. When you're ready for yours:

```bash
claude                        # in the same folder; accept the "trust this folder" prompt the first time
> /init
```

Claude removes the demo (only what the demo created), interviews you for about ten minutes, and files your real business. Then open the console again.

## The loop

| When | Do | Where |
|---|---|---|
| Any time | Capture a thought | Console, Activity, Inbox, or `python3 brain.py inbox add "..."` |
| Something happened | `/record` a decision, a change or an experiment | Claude |
| You have a document | Put the file in `drop/`, then `/ingest` it into notes | Claude |
| Weekly | `/weekly`: inbox to zero, numbers, bets, decisions due, briefs, log entry | Claude, or the console's **Weekly loop** button |
| A number should fill itself | `/connect` a tool (Stripe, YouTube, Meta Ads CSV, or anything with an API or export) | Claude |
| Anything | Open the console and look | `python3 brain.py serve` |

## What's in the box

```
brain.py            the command line: the one way Claude and you change the data
data/brain.db       your business (gitignored; back it up)
drop/               raw files waiting to be ingested (.md, .txt, .pdf...; gitignored)
core/               the platform: database, rules, console, orbit map (standard library only)
automations/        pullers that feed numbers in; csv-import ships installed
catalog/            use-case packs (Stripe, YouTube, Meta Ads) and starter profiles (creator, service, SaaS, e-commerce)
.claude/            the skills Claude uses (/init /weekly /record /ingest /connect /lint) and its guardrails
CLAUDE.md           how Claude works in here
docs/               GUIDE.md (make it yours), PROMPTS.md (copy-paste), ARCHITECTURE.md (how it works)
```

## Why a database and not files

- **Rules the system enforces, not rules you remember.** Past decisions and log entries can't be edited. A metric threshold must be a real band. A decision can't be logged without a prediction and a review date.
- **History for everything.** Rewrite a note, change a bet, delete a metric: it's in the change history, with the old version, and one command restores it.
- **Claude can't make a mess.** It changes data only through `brain.py`, which validates every write. A hook blocks it from touching the database any other way.
- **Safe to hand to a team or a student.** One file to back up, nothing to keep in sync.

## Your data

```bash
python3 brain.py backup               # a consistent copy in data/backups/ (the console also keeps one a day)
python3 brain.py history              # who changed what
python3 brain.py revert 42            # undo change 42
python3 brain.py demo clear           # remove the demo, keep anything you added
python3 brain.py export               # everything as JSON
```

## Migrating from the markdown version

Had the earlier file-based second brain? `python3 tools/migrate_markdown.py /path/to/old-brain` brings it across (see `docs/GUIDE.md`). The old version is tagged `v1-markdown`.

## License

MIT. Use it, change it, ship it, sell what you build with it.
