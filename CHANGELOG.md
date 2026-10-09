# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses semantic versioning once it is released.

## [Unreleased]

### Added

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

- The user model is not assumed to have `email`, `first_name` or `last_name` fields: linking uses `get_user_model().get_email_field_name()`, names of a linked user are read with a default.
- The unsubscribe view is exempt from Django's `LoginRequiredMiddleware`.
- The "Open Django admin" link is shown only when the default admin site is mounted.
- No brand colour, logo or font is shipped: the stylesheet has neutral defaults driven by CSS variables and one sans-serif system font stack.
