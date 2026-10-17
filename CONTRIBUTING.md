# Contributing

Thanks for looking at django-outreach. It is a small project, so keep changes focused.

## Setup

Everything runs in the project's container, with `docker compose` (v2):

```
docker compose build app
docker compose run --rm app pytest
docker compose run --rm app sh -c "ruff check . && ruff format --check ."
```

Tests run with `pytest`. Write them as Django `TestCase` classes, one class per `test_*.py` file, mock external services and never the database. To also run on PostgreSQL:

```
docker compose up -d database
docker compose run --rm -e DATABASE_URL=postgres://outreach:outreach@database:5432/outreach app pytest
```

The package runs on Python 3.10 to 3.13 with Django 5.1 and 5.2. CI covers that matrix.

## Changes

- Work on a branch, keep ruff clean (line length 95), and add tests for the behaviour you change.
- Use descriptive names and type every function. Add a comment only when the reason is not obvious.
- One class per file inside the `models`, `forms`, `choices`, `views`, `widgets` and `admin` packages, re-exported from the package `__init__.py`.
- Schema changes need a new migration, generated in the container with `makemigrations outreach`. `0001_initial` is frozen and is never edited.
- Translations: edit the `.po`, then run `scripts/compile_messages.sh` and commit the `.mo`. `scripts/check_translations.sh` checks they match.
- Add an entry to `CHANGELOG.md` under `[Unreleased]`.
- Commit messages are short, in English and in the imperative ("Add X", "Fix Y").

## Security

Do not report vulnerabilities in a public issue. See [SECURITY.md](SECURITY.md).
