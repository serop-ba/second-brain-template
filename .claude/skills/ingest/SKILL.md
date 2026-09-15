---
name: ingest
description: Ingest a source from raw/ into the second brain — writes or updates a note in wiki/. Triggers on "ingest", "process this source", "add this to the brain", or when a new file appears in raw/.
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

## Ingest it

1. Read it. Tell the user the 3–5 takeaways in a few lines and say which ones
   you'd file. Wait for a nod, unless they said to batch.
2. Write or update `wiki/<slug>.md` with frontmatter:
   `title`, `type: note`, `created`, `updated`, `tags`, plus `raw:` and
   `origin:` for a source page. Body: what it says, what it means for this
   business, links to related notes.
3. Cross-link **both ways** — add a link back from every note you reference.
   `wiki/` is flat, so links are plain `[name](name.md)`.
4. Contradicts something already filed? Note it inline ("as of X this was
   true; Y revises it to Z") — never overwrite silently — and flag it in step 6.
5. If it actually changes `company.md` or `goals.md`, update those too. Most
   sources don't. Don't force it.
6. Add `ingested: true` and `ingested_date: YYYY-MM-DD` to the raw file's
   frontmatter. This is the only permitted edit to `raw/`.
7. Append to `log.md`:
   `## [YYYY-MM-DD] ingest | <Title>` + one paragraph on what was touched and
   any contradiction found.

## Don't

- Don't edit `raw/` beyond the two `ingested*` keys.
- Don't create folders under `wiki/` — it's flat by design.
- Don't fabricate. If the source is thin, say so rather than padding the note.

## After

One or two lines: what was created, what it linked to, and — mentor mode —
whether it's actually worth acting on or just interesting.
