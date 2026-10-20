## What does this change?

<!-- One or two sentences. Link the issue it closes, for example "Closes #12". -->

## Why?

<!-- The problem it solves, if the issue does not already say it. -->

## Checklist

- [ ] Tests added or updated for the behaviour I changed, and `pytest` passes.
- [ ] `ruff check .` and `ruff format --check .` are clean.
- [ ] An entry is added to `CHANGELOG.md` under `[Unreleased]`.
- [ ] Schema changes come with a new migration (`0001_initial` and released migrations are not edited).
- [ ] Translations: the `.po` is edited and the `.mo` is recompiled with `scripts/compile_messages.sh`.
- [ ] Documentation (`README.md`, `docs/`) is updated if the interface or a setting changed.
- [ ] This change breaks the interface (if yes, say how in the changelog entry).
