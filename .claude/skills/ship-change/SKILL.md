---
name: ship-change
description: Use after ANY change to the software itself (core/, brain.py, schema, console page, catalog, automations, skills, tools/): update the documentation and add or update tests in the same turn, then run the suite. Triggers on editing platform code, adding a command, changing the schema, adding a skill or folder.
---

# Ship a change

A change to the platform is not done until its docs and tests agree with it. Do all of this in the same turn as the change, without being asked.

1. **Tests first-class.** Add or update a test in `tests/test_core.py` for every new or changed behaviour: the happy path and the failure the user would hit (bad input, missing file, empty brain). Use the `Base` class (temp database); patch module-level paths such as `cli.DROP` into a temp dir so tests never touch real data. Bug fix: write the test that fails first.
2. **Run them.** `python3 -m unittest discover -s tests`. Everything must pass; report the count. If something unrelated fails, say so, don't hide it.
3. **Update the docs that describe what you touched.** Check each; edit only where the change makes it wrong or incomplete:
   - `CLAUDE.md`: schema, CLI cheat sheet, operations (weekly, ingest, record, lint), rules.
   - `docs/ARCHITECTURE.md`: file layout, data model, new modules or folders.
   - `docs/GUIDE.md`: anything a user does by hand (steps, folders, commands).
   - `docs/PROMPTS.md`: new copy-paste prompts, if a user-facing flow changed.
   - `README.md`: the loop table, the folder overview, the skill list.
   - The skills in `.claude/skills/` that call the changed command or flow.
   - `catalog/automations/<pack>/README.md` or `automations/README.md` for automations.
   - `--help` text in `core/cli.py` for new commands and flags.
4. **New folder or file users touch?** Add it to `.gitignore` if it holds private data, and a `.gitkeep` if it must exist when empty.
5. **Say what you did.** End with the list: tests added, suite result, docs edited. If you skipped a doc on purpose, say why.

Don't write a changelog or a separate markdown file about the change; the docs above are the record. Keep prose short and match the existing tone.
