---
name: ingest
description: Ingest a source from raw/ into the second brain — writes a note in notes/, or a video idea if it's a YouTube source. Triggers on "ingest", "process this source", "add this to the brain", or when a new file appears in raw/.
---

# Ingest

Turn a file in `raw/` into knowledge. Read `../../../CLAUDE.md` first if it
isn't already in context — it owns the conventions; this skill only sequences
them.

## Pick the target

If the user named a file, use it. Otherwise find unprocessed sources:

```bash
cd "$(git rev-parse --show-toplevel)"
grep -L "^ingested: true" raw/*.md
```

Several unprocessed? List them and ask which — don't batch unless told to.

## Route it

Read the file. It's a **YouTube source** if frontmatter `source` matches
`youtube.com/watch` or `youtu.be/`, or the body is a timestamped transcript.

- YouTube → **Path B**. YouTube sources never become notes.
- Anything else → **Path A**.

## Path A — knowledge source

1. Read it. Tell the user the 3–5 takeaways in a few lines and say which ones
   you'd file. Wait for a nod, unless they said to batch.
2. Write or update `notes/<slug>.md` with frontmatter:
   `title`, `type: note`, `created`, `updated`, `tags`, plus `raw:` and
   `origin:` for a source page. Body: what it says, what it means for this
   business, links to related notes.
3. Cross-link **both ways** — add a link back from every note you reference.
   `notes/` is flat, so links are plain `[name](name.md)`.
4. Contradicts something already filed? Note it inline ("as of X this was
   true; Y revises it to Z") — never overwrite silently — and flag it in step 6.
5. If it actually changes `company.md` or `goals.md`, update those too. Most
   sources don't. Don't force it.
6. Append to `log.md`:
   `## [YYYY-MM-DD] ingest | <Title>` + one paragraph on what was touched and
   any contradiction found.

## Path B — YouTube source

1. Write `Output/video-ideas/YYYY-MM-DD-slug.md` (date = today, not the
   video's publish date). Frontmatter: `title`, `date`, `source` (relative
   link to the raw file), `source_video` (the URL). Three sections:
   - **Optimized title** — punchier than the original
   - **Hook** — the opening line or moment
   - **What to show** — concrete beats, enough to shoot without rewatching
2. Add `ingested: true` and `ingested_date: YYYY-MM-DD` to the raw file's
   frontmatter. This is the only permitted edit to `raw/`.
3. Append to `log.md`: `## [YYYY-MM-DD] video-idea | <Title>`.

## Don't

- Don't edit `raw/` beyond the two `ingested*` keys.
- Don't create folders under `notes/` — it's flat by design.
- Don't fabricate. If the source is thin, say so rather than padding the note.
- Don't write a note for a YouTube source, or a video idea for anything else.

## After

One or two lines: what was created, what it linked to, and — mentor mode —
whether it's actually worth acting on or just interesting.
