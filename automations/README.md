# Automations

Python scripts that pull external data (YouTube stats, finance ledger) for
this second brain. They're run as part of the weekly loop described in
`../CLAUDE.md` — but you can run them directly too.

Everything here is plain Python 3, one venv, no other runtimes.

## Setup

```bash
cd automations
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
```

`.env` and `.venv/` are gitignored — never commit real API keys.

## Layout

- `scripts/` — one script per data pull. Each prints a JSON result to stdout
  and also writes a timestamped copy to `../Output/analytics/`.
- `config/channels.yaml` — your channel + the competitor channels to track.
- `config/finance_log.csv` — manual ledger you append rows to by hand; scripts
  read it, they never write to it.
- `../Output/analytics/` — raw JSON snapshots from each run, alongside video
  ideas in `../Output/video-ideas/`. Scratch/cache, not the durable record —
  the durable record is `../dashboard.md` (current numbers) and the weekly
  entry in `../log.md` (what they meant). Safe to delete; scripts regenerate it.

## Scripts

| Script | What it needs | What it does |
|---|---|---|
| `youtube_channel_report.py` | `YOUTUBE_API_KEY`, your channel ID in `config/channels.yaml` | Pulls subscriber/view/video stats for your own channel(s) |
| `youtube_competitor_scan.py` | `YOUTUBE_API_KEY`, competitor IDs in `config/channels.yaml` | Pulls the same stats for tracked competitors, diffs against the last snapshot in `../Output/analytics/` |
| `finance_tracker.py` | nothing external — reads `config/finance_log.csv` | Computes trends/deltas per metric from your manually logged numbers |

Market/competitor research (news, positioning, narrative) isn't a script —
it's `WebSearch` + synthesis, filed as a note in `../notes/`. No API to wire
up there.

If `YOUTUBE_API_KEY` isn't set, the YouTube scripts print a clear error
instead of silently returning fake data — fill in `.env` before running them.
