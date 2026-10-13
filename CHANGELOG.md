# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses semantic versioning once it is released.

## [Unreleased]

### Changed

- New default look: a plum accent on warm neutrals, flat cards with a border and no shadow, and smaller corner radii. The default `OUTREACH_THEME` colours, the stylesheet defaults and the email card change with it. A project that sets every `OUTREACH_THEME` key is unaffected.
- Each prospect avatar takes one of six tints, chosen from its initials. The dashboard tiles show a status dot and the recent activity shows the prospect avatar.

### Added

- `Prospect.avatar_tone`, a number from 0 to 5 used for the avatar tint. It is a property, so there is no migration.

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
