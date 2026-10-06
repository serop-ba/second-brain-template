---
name: ingest
description: Turn source material (an article, transcript, call notes, competitor page, pasted text or a file) into notes in the library, updating the brain only where the source changes it. Triggers on "ingest", "file this", "here's a transcript", or a path to a document to learn from.
---

# Ingest

1. **Get it in.** If it's a file: `python3 brain.py doc import PATH --kind source --dept <slug> --tags a,b`. If it's pasted text: `doc add "Title" --kind source --body -` (stdin) or `--file`. Check `doc list --kind source` for sources not yet ingested (`not ingested`).
2. **Read it** with `doc get SLUG`.
3. **Discuss the takeaways first**, in a few lines, unless the user said to batch. Name what is new, what contradicts something already in the brain (`search WORDS` to check), and what you'd ignore.
4. **Write notes**: `doc add "..." --kind note --dept ... --tags ... --body "..."` or `doc update SLUG --body ...` for an existing one. Link related notes with `[[slug]]` in the body. If the source contradicts a claim, update that document and write the revision inline with the date; don't overwrite silently.
5. **Update the rest only if the source actually changes it**: a company fact, a bet's status, a metric value, a goal.
6. **Close the loop**: `doc ingest SLUG` (marks the source processed; sources are otherwise never edited), then `log add --type ingest --title "..." --body "what was filed, what changed"`.

Video or social-media sources that are really **ideas to react to** rather than knowledge: file one note per idea with the angle, the hook and what to show, tagged `idea`, instead of summarising the video.
