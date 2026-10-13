# Templates

Every template lives under `outreach/` and can be overridden by path. Put the replacement in a
directory listed in `TEMPLATES["DIRS"]`, or in an app listed before `outreach` in
`INSTALLED_APPS`. Template paths are part of the public contract, see {doc}`admin`.

Colours come from `OUTREACH_THEME` through CSS variables, so prefer the theme to an override when
only colours change, see {doc}`../topics/theming`.

## Mail

Rendered once per recipient by `ProspectMailer.render`.

| Template | Purpose | Context |
|---|---|---|
| `outreach/email/message.html` | HTML part of the mail: table layout with inline styles, the header, the body and the footer (unsubscribe line for newsletters only) | `subject`, `body_html` (already sanitised), `body_text`, `unsubscribe_url`, `site_name`, `header_text` (the site name when empty), `is_newsletter`, `logo_url` (absolute, or `None`), `logo_in_header`, `logo_in_footer`, `prospect`, `theme` |
| `outreach/email/message.txt` | Plain-text part | The same context |

Email clients can not use CSS variables, so the HTML part uses `theme.email.*` colours (`background`,
`card`, `border`, `text`, `muted`, `brand`, `accent`, `on_accent`), always the light values.

## Public pages

| Template | Purpose | Context |
|---|---|---|
| `outreach/bare.html` | Base of the public pages. Blocks `title`, `extrastyle`, `extrahead`, `bodyclass`, `body`, `content`, `scripts` | |
| `outreach/unsubscribe.html` | Confirmation shown on GET | `masked_email`, `site_name`, `logo_path`, `logo_dark_path` |
| `outreach/unsubscribed.html` | Shown after the POST, and for a valid link whose prospect is gone | The same context, with an empty `masked_email` when the prospect is gone |
| `outreach/base.html` | Base of the admin pages, extends `bare.html`: sidebar, top bar, messages and the mobile tab bar. Block `page` wraps `content` | The admin site context |

## Admin pages

All extend `outreach/admin/base.html`, which extends `outreach/base.html`. The admin site context
(`each_context`) adds `site_name`, `logo_path`, `logo_dark_path`, `django_admin_url`, `theme` and
`counts` (prospects by status, `total`, `members`, `mailings`, `email_templates`) to the usual
Django admin context.

| Template | Page | Extra context |
|---|---|---|
| `outreach/admin/login.html`, `logged_out.html` | Sign in and signed out | |
| `outreach/admin/index.html` | Dashboard | `recent_events`, `max_recipients`, `cooldown_hours` |
| `outreach/admin/help.html` | *How to use* | `variables`, `mail_tags`, `max_recipients`, `cooldown_hours`, `import_columns` |
| `outreach/admin/change_list.html`, `change_form.html` | Prospect list and form | Django's |
| `outreach/admin/delete_confirmation.html`, `delete_selected_confirmation.html` | Delete confirmations | Django's |
| `outreach/admin/import.html`, `export.html` | Import and export | django-import-export's |
| `outreach/admin/compose.html` | Step 1 of a send | `form`, `plan`, `queryset_ids`, `select_across`, `max_recipients`, `email_templates`, `selected_template`, `template_applied`, `save_template_form`, `can_save_template`, `can_overwrite_template` |
| `outreach/admin/preview.html` | Step 2 of a send | The compose context plus `preview_prospect`, `preview_html`, `preview_subject`, `subject`, `preview_choices` |
| `outreach/admin/mailing_list.html`, `mailing_detail.html` | Mailings | `recipients`, `skipped_reasons` (detail) |
| `outreach/admin/emailtemplate_list.html`, `emailtemplate_form.html` | Templates | `sample_preview_html`, `sample_preview_subject` (form) |
| `outreach/admin/includes/mail_hidden_fields.html`, `mail_message_fields.html` | Parts of the send steps | |

## Includes and widgets

| Template | Purpose |
|---|---|
| `outreach/includes/logo.html` | Logo or site name |
| `outreach/includes/icons.html` | SVG sprite of the icons |
| `outreach/includes/actor.html` | Who did an event |
| `outreach/includes/skip_reason.html` | Badge for a skip reason |
| `outreach/widgets/trix.html` | The Trix editor widget (`TrixWidget`) |

## Template tag

`{% load outreach_tags %}` provides `{% outreach_theme_css %}`, which writes the theme as one
`<style>` block of CSS variables.

## Static files

`outreach/outreach.css`, `outreach/mail-editor.js` and the vendored editor in
`outreach/vendor/trix/` (Trix 2.1.19, with its licence). The vendored files are replaced only by a
new verified download. The admin's own static files are reused, so the standard admin apps are
required.
