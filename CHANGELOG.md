# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses semantic versioning once it is released.

## [Unreleased]

### Added

- Celery dispatch: `OUTREACH_DISPATCH = "celery"` queues one `outreach.deliver_mail` task per recipient, with retries on transient SMTP errors, instead of sending inside the admin request. The task uses the Celery app of the host project. New settings `OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND` (default 5000), `OUTREACH_CELERY_QUEUE` and `OUTREACH_DELIVERY_MAX_RETRIES` (default 3), the `celery` extra and the `outreach_resume_deliveries` command.
- Migration `0003`: the `MailingDelivery` model, one row per recipient of a mailing. The Mailing admin shows how many are pending.
- System checks `outreach.E002`, `outreach.E003` and `outreach.W001`.
- Audiences: a named, static list of prospects (`Audience`, `Prospect.audiences`, migration `0005`). Prospects are added and removed with two actions of the prospect list (the add page can also create the audience from a typed name), the list can be filtered by audience, and the Audiences pages and permissions (`view`, `add`, `change`, `delete`) are new. Sending to an audience uses the existing filter, Select all and Send a mail. Two event kinds record the changes in the history of a prospect.

### Changed

- `EmailTemplate.created_by` is now an optional foreign key to the host user model (cleared when the account is deleted) instead of a username string, and `updated_by` records who changed a template last. Migration `0004` matches the existing usernames to users through `USERNAME_FIELD`: a template whose author no longer matches an account ends up without an author. `EmailTemplates.save` and `create` take the user instead of a username.
- `Prospect`, `MailingDelivery` and `EmailTemplate` share the abstract models `BaseModel` (uuid, `created_at`, `updated_at`) and `AuthoredModel` (adds `created_by`, `updated_by`). No schema change except the above.
- Synchronous sending stays the default but is not recommended in production: `outreach.W001` reports it in `check --deploy`. Its behaviour and the `OUTREACH_MAX_RECIPIENTS_PER_SEND` limit (100) are unchanged.
- `ProspectMailer.send` goes through the new `queue` and `deliver` steps, and `MailReport` has a `queued` list, filled in Celery mode.

## [0.1.0b6] - 2026-10-13

### Changed

- The header logo of mails (`OUTREACH_EMAIL_LOGO_IN_HEADER`) is centered horizontally. When no header text is set, the logo stands alone and the site name is no longer repeated as text under it (it stays the image `alt`). A header text is shown under the logo, centered with it. Without a header logo nothing changes. New template context keys `has_header_logo` and `header_logo_alt`.

## [0.1.0b5] - 2026-10-13

### Added

- Notices: a template or a mail not marked as newsletter is a notice to members. It has no unsubscribe footer and no `List-Unsubscribe` headers, goes to members only (new skip reason `not_member`) and still reaches members who unsubscribed from newsletters. A notice text cannot contain `{{ unsubscribe_url }}`.
- Header text on templates and mailings, shown at the top of the mail instead of the site name when set.
- `OUTREACH_EMAIL_LOGO_IN_HEADER` and `OUTREACH_EMAIL_LOGO_IN_FOOTER` put `OUTREACH_LOGO_STATIC_PATH` in the header and the footer of mails. The logo should be PNG or JPG: Gmail and Outlook do not show SVG.
- Migration `0002`: `header_text` and `is_newsletter` on `EmailTemplate` and `Mailing`. Existing rows become newsletters.
- Documentation, built with Sphinx and published on Read the Docs: installation, configuration, a user guide for the staff, topics for developers and a reference for the models, services, URLs, permissions and templates.
- Docstrings on the public classes and functions, which feed the reference.

### Changed

- The CSV import is built into the app. It keeps the preview and confirm steps, the same columns, aliases, limits and rules (existing emails skipped, one invalid row blocks the file), and reports row errors by line number. A repeated email in one file is imported once.
- The CI runs 8 jobs instead of 25: the oldest and newest Python and Django on SQLite and PostgreSQL, the host variants in one job, and pushes to `main` plus pull requests only.

### Removed

- The `django-import-export` and `tablib` dependencies. Only Django and nh3 remain. Spreadsheet formats (xlsx, json, tsv) are no longer read or written: the import and the export are CSV only.
- The `IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT` setting and the system check `outreach.W001`. The export now always escapes cells that start a spreadsheet formula.
- The URL name `outreach_admin:outreach_prospect_export`. The export is the admin action *Export the selected prospects as CSV*.
- `import_export` is no longer needed in `INSTALLED_APPS`. Leaving it there does no harm.

## [0.1.0b4] - 2026-10-13

### Added

- `manage.py outreach_load_users` creates a prospect for each active user account that has none, with `--dry-run` and `--include-inactive`. Prospects are created through `Prospect.save()`, so suppression and linking apply, and an `added` event by `system` is recorded. Existing prospects are left untouched and the output is counts only. There is no signal: loading is always explicit.
- `OUTREACH_USER_PROSPECT_FIELDS` setting: a dotted path to a callable `(user) -> dict` that supplies `kind`, `first_name`, `last_name`, `organization`, `city` or `country` for the command.

## [0.1.0b3] - 2026-10-13

The first beta published on PyPI. The repository is public from this release.

### Added

- `Prospect.avatar_tone`, a number from 0 to 5 used for the avatar tint. It is a property, so there is no migration.

### Changed

- New default look: a plum accent on warm neutrals, flat cards with a border and no shadow, and smaller corner radii. The default `OUTREACH_THEME` colours, the stylesheet defaults and the email card change with it. A project that sets every `OUTREACH_THEME` key is unaffected.
- Each prospect avatar takes one of six tints, chosen from its initials. The dashboard tiles show a status dot and the recent activity shows the prospect avatar.

### Security

- A `{% button %}` placed inside a link or another tag is rejected by the compose form and refused when a mail is rendered. It could previously write an anchor inside an attribute after the final sanitising pass.
- A button link may not contain a space, and an `http` or `https` link needs a host.
- The suppression list honours `SECRET_KEY_FALLBACKS`, like the unsubscribe links. A key rotation no longer lets a removed prospect that is imported again be mailed while the old key is listed.
- An import file larger than `OUTREACH_MAX_IMPORT_BYTES` (2 MB by default) is rejected before it is parsed.

## [0.1.0b2] - 2026-10-13

### Added

- A tag can declare a keyword-only `preview` parameter with a default, as in `def tag(prospect, *, preview=False)`. The package passes `preview=True` while a message is only previewed in the compose step, and `False` when it is sent, including when the tag is named as an argument of another tag or of a button. A tag with side effects can skip them in a preview. `ProspectMailer.render` takes a matching `preview` keyword, `False` by default.

### Notes

- Existing tags are unchanged: a tag without a `preview` parameter is called exactly as before.
- Registration refuses a `preview` parameter that is not keyword-only, since staff text could fill a positional one.

## [0.1.0b1] - 2026-10-13

First beta. It is meant to be installed and tried by projects that follow it, and the interface may still change before 0.1.0.

### Added

- Computed mail tags: `{% name "text" variable %}` in the subject or the message runs a registered Python function once per recipient and writes its escaped text result. Built-in tags are `today`, `greeting` and `member_since`. A host project adds its own with `@mail_tag_library.register` in a `mail_tags.py` module of any installed app. A bare word in a call names a variable, or a tag called with the prospect only.
- Buttons: `{% button "Label" link %}` in the message writes a link styled as a button, using `accent` and `on_accent` from `OUTREACH_THEME`. The link is fixed text, a variable or a tag, and must be `http`, `https` or `mailto`. A link that is empty or invalid at send time fails that recipient only.
- Prospect list with an optional OneToOne link to the host user model, an event timeline and a `Mailing` log, on its own admin site (`outreach_admin`) with a dashboard, import and export and a help page.
- Bulk mail with per-recipient variables (`{{ key }}` and `{{ key | fallback }}`), a Trix rich text editor, nh3 sanitising, a preview step, a cooldown, a per-send cap and claim-before-send.
- Email templates: named subject and body pairs shared by staff with the permission, a template picker and "Save this message as a template" on the compose page, a Templates section with a sample preview.
- One-click unsubscribe (`List-Unsubscribe` headers, signed links, a suppression list that survives deletion of a prospect).
- `OUTREACH_THEME` setting: colours, optional dark palette, optional font stack and avatar colour, rendered by the `{% outreach_theme_css %}` tag. Emails use the light colours through `theme.email`.
- `OUTREACH_IMPORT_HEADER_ALIASES` setting to accept extra import column names. No alias is built in.
- System checks `outreach.E001` (invalid `OUTREACH_THEME`) and `outreach.W001` (`IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT` is not `True`).
- English and French interface, with the catalogue compiled by Babel.
- Standalone test project in `tests/` (SQLite and PostgreSQL, custom user model, `LoginRequiredMiddleware`, admin not mounted), a Docker based test runner and a CI workflow.
- uv based packaging (`uv_build`, committed `uv.lock`).

### Changed

- Licensed under the BSD 3-Clause licence.
- The `models`, `forms`, `choices`, `views`, `widgets` and `admin` modules are packages with one class per file. Import paths such as `from outreach.models import Prospect` are unchanged.

### Notes

- `0001_initial` is frozen from this beta on: schema changes ship as new migration files, and the initial migration is never edited.
- The user model is not assumed to have `email`, `first_name` or `last_name` fields: linking uses `get_user_model().get_email_field_name()`, names of a linked user are read with a default.
- The unsubscribe view is exempt from Django's `LoginRequiredMiddleware`.
- The "Open Django admin" link is shown only when the default admin site is mounted.
- No brand colour, logo or font is shipped: the stylesheet has neutral defaults driven by CSS variables and one sans-serif system font stack.
