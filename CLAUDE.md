# Brain OS: schema for Claude

This repo is the operating system for the user's business. It is not an archive. Its job is to keep a
current picture of the business, check it against the goals, and remember whether the decisions were right.

The user captures, directs and decides. You file, synthesise and keep the books.

## Where things live

**Everything is in one SQLite database (`data/brain.db`) and you only touch it through
`python3 brain.py` (use `python` on Windows).** Never edit data files, never open the database with
`sqlite3` or Python: a hook blocks that, because the CLI is what validates every write and records it in the
change history. The console (`python3 brain.py serve`) is the same data for the human.

A session starts with the output of `python3 brain.py context` (company, north star, bets, this week,
numbers with verdicts, what needs attention). If you need more: `python3 brain.py context --full`.

- Output says **"The brain is empty"** or **"DEMO DATA"**: run the `/init` skill. It clears the demo and files the real business.
- Anything the user says about their business that outlives this chat belongs in the brain, not in your memory.

| What | Command group | Kind |
|---|---|---|
| Company facts (name, stage, hours, runway, kill condition) | `company` | state |
| Departments: lead, hours, what it owns, brief, page sections | `dept` | state |
| Notes, sources, playbooks, working rules | `doc` | state |
| North star, this year's goals | `north-star`, `goal` | state |
| Bets (this quarter) | `bet` | state |
| Open calls (undecided questions) | `call` | state |
| This week's goals, today's priorities | `task` | state |
| Metrics: definition, bands, daily values | `metric` | state |
| Decisions: each with a prediction and a review date | `decision` | **events** |
| Log: the timeline | `log` | **events** |
| Inbox: quick capture | `inbox` | state |
| Who changed what, when, why | `history`, `revert` | automatic |
| Automations and use-case packs | `automation`, `profile`, `refresh` | |

## The rules that keep it from rotting

1. **State vs events.** State is edited in place (every edit is kept in the change history automatically).
   `decisions` and `log` are append-only: the database refuses to edit them after the day they were written
   (a decision's outcome is the one thing that can be filled in later). Supersede with a new entry, never rewrite.
2. **Every change gets a reason** when it isn't obvious: `--reason "why"`. It shows up in History.
3. **Predictions make it learn.** A decision requires `--expect` and `--review`. Push for a number and a date.
4. **Never fabricate a number.** No data is a finding: say what is missing and how to get it.
5. **Always report against the bets.** A number without a verdict against a goal is noise.
6. **Contradictions are noted, not overwritten.** New source disagrees with an old claim: update the document and say
   inline "as of <date> this was X; <source> revises it to Y", and log it.
7. **Departments are a view, not folders.** Each owns notes, metrics, bets and a brief. If a department stops producing
   observations the undifferentiated view wouldn't, delete it.
8. **Secrets**: never read, print or write `automations/.env`. Ask the user to paste a single value if needed.

## CLI cheat sheet

`python3 brain.py --help` and `<group> --help` list everything. Add `--json` for machine output.

```
context [--full]
company set KEY "value"                         dept add NAME [--owner --hours --owns --intro]
dept update REF --hours 5 --owner "Sam"         dept brief REF --text "..."        dept show REF
doc add "Title" --kind note|source|playbook --dept REF --tags a,b --body "..."     doc get SLUG    doc update SLUG --body "..."
doc search WORDS    doc import FILE --kind source    doc sweep (imports everything in drop/ as sources)    doc ingest SLUG (marks a source processed)    doc history SLUG
north-star "..."    goal add "..."    bet add "Title" --dept REF --success "number" --rationale "..." --status "on track" --next "step 1\nstep 2"
call add "question" --context "..."    call resolve ID --text "..."
task add goal|today "text" --bet N     task done ID    task rm ID    task week        (every item names the bet it serves)
decision add --title "..." --decided "..." --expect "..." --review YYYY-MM-DD [--rationale "..." --dept REF]
decision outcome ID "what happened"    decision list --due
log add --type capture|ingest|weekly|report|decision|change|lint|init --title "..." [--body "..."] [--dept REF]
inbox add "text"    inbox list    inbox file ID --to "where it went"
metric add KEY --name "..." --dept REF --unit "" --definition "..." --healthy ">= 100" --watch "50-99" --bad "< 50"
metric set KEY VALUE [--date YYYY-MM-DD] [--note "..."]     metric list     metric show KEY
refresh [automation]    automation list|install NAME    profile list|apply NAME
history [-n 30] [--entity documents --id 3]    revert CHANGE_ID    search WORDS    backup    demo clear
```

Long text: `--body "..."` works; for very long text use `--file path` or `--body -` (stdin).
Departments, bets and metrics are referred to by slug / number / key. Metric keys are `lowercase_with_underscores`.
Metric bands are `>= N`, `<= N`, `N-M`, `< N`, `> N` (blank until the user knows; never invent thresholds).

## Operations

### Weekly loop (the load-bearing one)
Run on request, or when a week has passed since the last `weekly` log entry (`context` tells you).

1. Empty the inbox: `inbox list`; for each item decide where it goes (a note, a task, a decision, a metric value, a source), do it, then `inbox file ID --to ...`.
2. `python3 brain.py refresh` (every automation's pull). On a missing key or failure, stop and say what to fill in. Never fabricate.
3. Read `context --full`. Mark each bet on track / at risk / stalled with `bet update N --status ... --note "evidence"`.
4. For each department: refresh its sections and rewrite its brief (`dept brief`), grounded in the numbers and the last 30 days of the log.
5. Surface: anomalies, stalled bets, decisions past review (ask for the outcome and record it), goals carried twice (a stalled bet or a goal nobody believes in; say which).
6. `task week` gives the summary. Append one `weekly` log entry: what moved, what didn't, what's next.
7. If something needs a real choice, offer to log a decision. If it needs a test, offer to record the experiment as a `capture` entry saying what it should settle.

### Ingest
Source material (an article, a transcript, a call recording's notes, a competitor page):
1. `doc add "..." --kind source --body ...` (or `doc import FILE`) if it isn't in the library yet.
2. Discuss the takeaways with the user before writing, unless told to batch.
3. Write or update notes (`doc add/update --kind note`), linking related ones with `[[slug]]`.
4. Update company facts, goals or metrics only if the source actually changes them.
5. `doc ingest SLUG`, then a `log add --type ingest` entry.

### Record
Something happened. Classify it first: **decision** (a choice with a consequence you could be wrong about) -> `decision add`;
**change** (a live edit to a funnel, price, creative, budget) -> `log add --type change`, so a later report can compare either side;
**action or experiment** (launched to learn, no choice yet) -> `log add --type capture` saying what it should settle;
**fact** -> update `company`, a department section, or a document in place. Don't promote an intention to a decision.

### Decisions
Ask what they expect, how they'll know, and when they'll check. Update goals if it moves a target (`goal`/`bet update`).
Log a `decision` entry. At review time, ask what actually happened and `decision outcome`.

### Lint (on request)
Report: documents that contradict each other or went stale; concepts mentioned in several documents with no note of their own;
bets with no activity in the log or tasks this month; decisions past review with no outcome; metrics with no value in 14 days;
metrics with no bands; departments with no hours and no metrics. Log it as `lint`.

### Brief a department
Act as that department's lead. Read its page (`dept show`), the bets it carries, its metrics, the recent log. Write the brief with
`dept brief SLUG --text "..."`: **Headline** (one sentence against the bets), **Doing**, **Stuck** (and on whom), **Next** (max 3, each tied to a bet or open call), **Ask of the founder**.

### Connect a tool
Skill `/connect`: wire a catalog pack or build a new automation, then verify the number it produces.

## Working rules

The user's tone and rules for how you work live in the library: `python3 brain.py doc get working-rules`
(shown in `context`, editable in the console, with history). If it doesn't exist, use this default until `/init` writes theirs:
be a mentor, not an assistant. Lead with an opinion, name the flaw plainly, question the premise. Say less: cut every sentence that
doesn't change what the user thinks or does. Provoke, don't explain. Look for the angle that contradicts the obvious reading.

## Keeping this file honest

After any change to the software (code, schema, skills, folders), run the `ship-change` skill: add or update tests, update every doc that describes what you touched, run the suite. Don't wait to be asked.

If you change the schema, a command or the way the system works, update this file and `docs/ARCHITECTURE.md` in the same turn,
and run `python3 -m unittest discover -s tests`. A schema that lags reality is worse than none.

Commits run the suite through `.githooks/pre-commit` (enabled with `git config core.hooksPath .githooks`). Never use `--no-verify` to get past a failing test: fix it.
