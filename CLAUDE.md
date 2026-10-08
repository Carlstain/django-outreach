# CLAUDE.md

Guidance for Claude Code in this repository: `django-outreach`, a reusable Django app (import name and app label `outreach`) for prospect lists, reusable email templates, rich text bulk mail and one-click unsubscribe, on its own admin site. The package is unreleased: until the first release the single `0001_initial` migration may be regenerated.

## Module map

Weights: core (change with care), small, infrastructure, vendored.

| Path | Weight | What it holds |
|---|---|---|
| `src/outreach/models/` | core | One model per file: `prospect.py`, `prospect_event.py`, `mailing.py`, `email_template.py`, `suppression.py` |
| `src/outreach/choices/` | small | `prospect_kind.py`, `prospect_status.py`, `event_kind.py`, `skip_reason.py`, `actors.py` (the `ACTOR_*` constants) |
| `src/outreach/services/mailing.py` | core | `ProspectMailer`: plan, claim, render, send. `MailPlan`, `MailReport` |
| `src/outreach/services/unsubscribe.py` | core | `SuppressionList`, `UnsubscribeTokens`, `ProspectUnsubscriber`, the two salts |
| `src/outreach/services/variables.py`, `body.py` | core | Variable whitelist and regex rendering. nh3 sanitiser and HTML to text |
| `src/outreach/admin/` | core | `prospect.py` (`ProspectAdmin`: send mail steps, actions), `mailing.py`, `email_template.py`, `member_filter.py`, `prospect_event_inline.py`. Each admin registers itself on `outreach_site` with `@admin.register`, and `admin/__init__.py` imports them all |
| `src/outreach/sites.py` | core | `OutreachAdminSite` (language override, counts, help page) and `outreach_site` |
| `src/outreach/views/`, `urls.py` | small | `views/unsubscribe.py` (public `UnsubscribeView`), URL include with the `outreach` namespace |
| `src/outreach/forms/` | small | `message_content.py` (shared checks), `message.py`, `email_template.py`, `save_template.py`, `prospect.py`, and the `outreach_*` admin forms (`outreach_authentication.py`, `outreach_import.py`, `outreach_export.py`; the prefix avoids the `import` keyword) |
| `src/outreach/widgets/`, `resources.py` | small | `widgets/trix.py` (`TrixWidget`, `TRIX_VERSION`), the import/export resource |
| `src/outreach/conf.py`, `theme.py`, `checks.py`, `apps.py`, `templatetags/outreach_tags.py` | infrastructure | `OUTREACH_*` settings, `OUTREACH_THEME`, system checks, app config, theme tag |
| `src/outreach/services/linking.py` | small | Links a prospect to a user by email |
| `src/outreach/services/templates.py` | small | `EmailTemplates.save`, `TemplateNameTaken`, `SavedTemplate` |
| `src/outreach/templates/outreach/`, `static/outreach/`, `locale/fr/` | infrastructure | Templates, CSS, JS, French catalogue |
| `src/outreach/static/outreach/vendor/trix/` | vendored | Trix 2.1.19, with its licence |
| `src/outreach/migrations/` | infrastructure | A single `0001_initial` until the first release |
| `tests/` | infrastructure | Standalone Django test project and the tests |
| `example/` | small | Runnable host project |

## Data model

```
Prospect (outreach_prospect)             Mailing (outreach_mailing)
  uuid pk                                  uuid pk
  email unique, lower-cased                subject, body_html (sanitised, variables not replaced)
  kind, first_name, last_name              sender
  organization, city, country              sent_count, failed_count, skipped_count
  status                                   skipped_reasons (JSON, counts per reason)
  user  -- OneToOne, optional,             created_at
          SET_NULL, host user model              ^
  last_mailed_at, created_at, updated_at         | SET_NULL, optional
        ^                                        |
        | CASCADE                          ProspectEvent (outreach_prospectevent)
        +----------------------------------  prospect FK, mailing FK
                                             kind, detail, actor, created_at

EmailTemplate (outreach_emailtemplate)   uuid pk, name (unique ignoring case), subject,
                                         body_html (sanitised), created_by, created_at,
                                         updated_at. No foreign key: a Mailing keeps a copy.

Suppression (outreach_suppression)       email_hash pk (salted HMAC of the address), created_at
                                         no foreign key: it outlives the prospect
```

Glossary:

- Prospect: a person or organisation that may be mailed. Statuses: `prospect` (never mailed), `contacted`, `unsubscribed`.
- Member: a prospect linked to a host user.
- Mailing: one send action that had at least one recipient.
- Email template: a named subject and body, shared by every staff member with the permission.
- Skip reasons: `unsubscribed`, `suppressed`, `cooldown`, `over_limit`.
- Suppression: the permanent do-not-mail list, stored as hashes.
- Claim: marking recipients as mailed (`last_mailed_at`) in a transaction before any SMTP call.

## Boundaries

- Host user model: through `settings.AUTH_USER_MODEL`. The app reads the email field name from `get_user_model().get_email_field_name()` and `first_name` and `last_name` only if present. Templates also read `user.get_username`, `get_short_name`, `email` and `date_joined`, guarded with `firstof` or `if`, so they degrade silently on a custom model that lacks them. Nothing else is read.
- Mail: Django's mail framework (`EMAIL_*`, `DEFAULT_FROM_EMAIL`, `get_connection()`). The app never sends from a request Host: links use `OUTREACH_BASE_URL`.
- django-import-export: `ProspectResource`, the import and export forms and templates, the formula escaping setting.
- Django admin: a second `AdminSite` (instance `outreach_admin`), reusing the admin's static files and ModelAdmin machinery. It needs the standard admin apps and middleware.
- Public contract with host projects: `include("outreach.urls")`, the `OUTREACH_*` settings, the `outreach.*` permissions, URL names `outreach:unsubscribe` and `outreach_admin:*`, template and static paths under `outreach/`, table names `outreach_*`.
- No other package is imported from the host project. No REST API.

## The way things are done here

- Settings are read lazily through `outreach_settings` (`conf.py`), never at import time, so `override_settings` works in tests.
- The language is set per view with `translation.override(OUTREACH_LANGUAGE)` (`OutreachAdminSite.admin_view`, `login`, `UnsubscribeView`). The site renders `TemplateResponse` inside the override on purpose, since rendering happens after the view returns. Reason: the host may have no `LocaleMiddleware`, and a project-wide change must not be forced on it.
- Variables are replaced by a regex over a fixed whitelist, never by the template engine. Reason: staff type the text, but it must never reach a code path.
- Bodies are sanitised in the form and again at render, and after substitution. Reason: a direct service call must not bypass the form, and a variable value must not create a `javascript:` link.
- Mail is claimed before it is sent, inside `transaction.atomic()` with `select_for_update(skip_locked=True)`, and the claim is restored on failure. Reason: a double submit must not send twice.
- Skipped recipients are stored as counts, never as names. Reason: a Mailing outlives prospects, and it must not hold data about a person who asked for erasure.
- One class per file inside the `models`, `forms`, `choices`, `views`, `widgets` and `admin` packages. Each package `__init__.py` re-exports its public names with `__all__`, and the rest of the code imports through those public paths (`from outreach.models import Prospect`), so the layout inside a package can change without touching callers. Siblings in one package import each other's module directly.
- Enum members are used instead of raw strings (`ProspectStatus`, `EventKind`, `SkipReason`).
- Colours in templates and CSS come from `OUTREACH_THEME` variables. No brand colour or hex literal outside the neutral defaults, except the status badge colours (`--st-*` in `outreach.css`) and the shadow, which are fixed semantic values.
- Code style: descriptive names, typed functions, no comments unless the reason is not obvious, ruff line length 95.

## Do-not-touch list

- `AppConfig.label` (`outreach`), the table names, the permission codenames, `outreach_admin` and `outreach:unsubscribe`: host projects store these in their database, groups and URLs.
- The salts `outreach.suppression` and `outreach.unsubscribe`: changing either breaks every link already sent or every stored suppression hash.
- Migrations once a version is released: they are never edited, only added to. Until then `0001_initial` is regenerated in the container with `makemigrations outreach`.
- `src/outreach/static/outreach/vendor/trix/`: vendored files, replaced only by a new verified download (check the package hash first). `src/outreach/THIRD_PARTY_NOTICES.md` goes with them.
- `src/outreach/locale/fr/LC_MESSAGES/django.mo`: generated. Edit the `.po`, run `scripts/compile_messages.sh`.

## Settled decisions

- Sending is synchronous in the admin request, capped per action. No Celery. A send takes about 0.3 s per SMTP message, so the default cap of 100 fits under a typical 60 s proxy timeout. A task queue is the upgrade path if that stops being enough.
- No public subscribe form and no double opt-in. Every mail carries an unsubscribe link.
- Unsubscribed is final: no admin action, import or form re-activates an address. Rejected: a re-subscribe form.
- The email of a prospect is immutable after creation (a changed address would carry the consent to another person).
- `city` and `country` are fields on `Prospect`. Rejected: reading them from user subtypes, since a portable app must not reach into host models.
- nh3 sanitises HTML. Rejected: a hand-written sanitiser.
- Trix is the editor, vendored as one minified file with no JavaScript build step. Tiptap was considered and not taken.
- `OUTREACH_THEME` (validated settings, one `<style>` block) rather than template-only overrides, so a host changes colours without copying templates. Templates can still be overridden by path.
- No font is shipped. A host sets `font_family` and loads its font itself.
- No built-in import aliases: `OUTREACH_IMPORT_HEADER_ALIASES` is empty by default.
- `OUTREACH_THEME` is validated strictly by the system check `outreach.E001`, but at runtime `OutreachTheme.css()` and `.email` never raise: an invalid value falls back to the default for that key and one warning per distinct problem is logged on the `outreach` logger. Reason: a typo in a setting must not take down the public unsubscribe page or a send. The theme is resolved once per instance, and the render context holds one instance.
- `django-import-export` is `>=4.2,<5,!=4.3.0`: 4.0 and 4.1 fail on import and export, 4.3.0 fails to import openpyxl.
- Email templates are shared by every staff member who holds the permission, not private to their author. Rejected: per-user templates, because the people who write the mail are a small team that wants one list. A `Mailing` keeps a copy of its subject and body and has no foreign key to a template, so deleting a template never rewrites history.
- The licence is BSD-3-Clause: it is Django's own licence and the norm for Django apps, close to MIT, with a clause against using the author's name to endorse derived products. Third-party licences are in `src/outreach/THIRD_PARTY_NOTICES.md`.
- Settings are `OUTREACH_*` only, there are no aliases.
- Template name uniqueness is case-insensitive through a `Lower("name")` unique constraint. On SQLite `lower()` folds only ASCII, so non-ASCII names that differ only by case can coexist there. PostgreSQL folds them.
- Packaging uses uv (`uv_build` backend, `uv.lock` committed).
- Fonts are sans-serif only: one system font stack, only sans-serif faces.
- Rotating `SECRET_KEY` invalidates unsubscribe links and suppression hashes. Documented, accepted.

## Running the tests

```
docker compose build app
docker compose run --rm app pytest
docker compose up -d database
docker compose run --rm -e DATABASE_URL=postgres://outreach:outreach@database:5432/outreach app pytest
docker compose run --rm app pytest tests/host/test_custom_user_model.py --ds=tests.settings.custom_user
docker compose run --rm app sh -c "ruff check . && ruff format --check ."
```

Use `pytest`, not `manage.py test`. The tests project is the `tests/settings/` package (`tests.settings`); the variants are `tests.settings.custom_user`, `tests.settings.no_tz`, `tests.settings.no_i18n` and `tests.settings.no_escape`.

## Negative facts

- There is no release and no tag yet. `v0.1.0` does not exist.
- Python 3.10 and Django 5.1 are covered only by the CI matrix. The local Docker image defaults to Python 3.12 and installs the versions pinned in `uv.lock`.
- There is no Celery, no task queue, no REST API, no public subscribe endpoint and no re-subscribe path.
- No font and no logo are shipped.
- Only `fr` is shipped besides English.
