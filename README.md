# django-outreach

A reusable Django app for prospect lists, reusable email templates and bulk mail. It runs on its own admin site, separate from `/admin/`, and brings its own models, templates, static files and French translation.

What it does:

- Prospects (person or organisation) with an optional OneToOne link to the host project's user model.
- Message variables such as `{{ first_name }}` and `{{ first_name | friend }}` (fallback when empty), taken from a fixed list.
- Rich text message body (Trix editor), sanitised with nh3.
- Email templates: named subject and body pairs, shared by every staff member who has the permission, picked or saved from the compose page.
- Audiences: named lists of prospects, managed in the admin, to mail the same set again.
- A `Mailing` log for every send: subject, body as sent, sender, counts of sent, failed and skipped recipients.
- One-click unsubscribe links (`List-Unsubscribe` headers included) and a suppression list that survives the deletion of a prospect.
- CSV import with a preview step, and CSV export of selected prospects.
- A built-in help page for the staff who use it, in English and French.

Documentation: https://django-outreach.readthedocs.io/

See `example/` for a runnable host project.

## Requirements

- Python 3.10 or later
- Django 5.1 or 5.2 (`>=5.1,<6`)
- nh3 0.3.x

## Installation

django-outreach is a beta published on PyPI as `django-outreach`. The import name and the app label are `outreach`. Beta versions are only installed when you ask for them.

With uv:

```
uv add django-outreach --prerelease=allow
```

With pip:

```
pip install --pre django-outreach
```

Pin an exact version in your own requirements, for example `django-outreach==0.1.0b3`, since the interface may still change before `0.1.0`. Every release also has its wheel and sdist attached to its [GitHub Release](https://github.com/Carlstain/django-outreach/releases).

### Beta

This is a beta: it is meant to be installed and tried, and the interface may still change before `0.1.0`. The initial migration `0001_initial` is frozen, so an installation can be upgraded without resetting its tables. Known limits: by default sending runs synchronously in the admin request with a per-send cap (Celery dispatch is available and recommended in production, see the documentation), and Outlook desktop shows a button as a plain coloured link. See [SECURITY.md](SECURITY.md) for how to report a vulnerability and for the known limitations.

## Try the example project

`example/` is a minimal host project with demo data. From a checkout of this repository:

```
docker compose run --rm -p 8765:8000 -e EXAMPLE_THEME=default app sh -c \
  "python example/manage.py migrate -v 0 && python example/manage.py shell < example/seed_demo.py && python example/manage.py runserver 0.0.0.0:8000"
```

Open http://localhost:8765/outreach/ and log in as `demo` / `demo` (a throwaway demo account, created by the seed script). Use `EXAMPLE_THEME=warm` to see the second theme. The example uses the console email backend, so nothing is ever sent, and keeps its SQLite database inside the container.

## Host project configuration

1. Add the apps. `outreach` needs `django.contrib.admin`, `auth`, `contenttypes`, `sessions`, `messages` and `staticfiles`.

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "outreach",
]
```

2. Middleware and template context processors: the same ones Django's admin requires (sessions, authentication, messages and CSRF middleware; the `request`, `auth` and `messages` context processors, with `APP_DIRS = True` or the app templates otherwise reachable). No `LocaleMiddleware` is needed, the app activates `OUTREACH_LANGUAGE` itself for its own pages.

3. Mount the URLs under any prefix:

```python
urlpatterns = [
    path("outreach/", include("outreach.urls")),
]
```

The unsubscribe page is `<prefix>/unsubscribe/<token>/` (URL name `outreach:unsubscribe`). The admin site instance is `outreach_admin`.

4. Set `OUTREACH_BASE_URL` (see the settings table) and your `EMAIL_*` settings, then migrate and collect static files:

```
python manage.py migrate
python manage.py collectstatic
```

5. Create staff users. Access to the whole site requires `is_staff`, `is_active` and the `outreach.view_prospect` permission (superusers have it). Staff need `outreach.view_prospect` to enter the site at all, so a user who holds only template permissions cannot reach the Templates pages. Give permissions through groups:

| Permission | Allows |
|---|---|
| `outreach.view_prospect` | Open the site, list and read prospects, export them as CSV, the help page and the dashboard |
| `outreach.add_prospect` | Add a prospect, import a CSV file |
| `outreach.change_prospect` | Edit a prospect, send a mail, add to or remove from an audience, unsubscribe selected, link to user accounts |
| `outreach.delete_prospect` | Delete prospects |
| `outreach.view_audience` | See the Audiences list |
| `outreach.add_audience` | Create audiences |
| `outreach.change_audience` | Edit audiences |
| `outreach.delete_audience` | Delete audiences |
| `outreach.view_mailing` | Read the Mailings list and detail |
| `outreach.delete_mailing` | Delete a mailing log entry (mailings cannot be added or changed) |
| `outreach.view_emailtemplate` | See the Templates list, use a template on the compose page |
| `outreach.add_emailtemplate` | Create templates, save a message as a template |
| `outreach.change_emailtemplate` | Edit templates, replace a template when saving a message |
| `outreach.delete_emailtemplate` | Delete templates |

## Settings

All settings are optional except `OUTREACH_BASE_URL` for sending. They are read lazily, so `override_settings` works.

| Setting | Default | Meaning |
|---|---|---|
| `OUTREACH_SITE_NAME` | `"Outreach"` | Name shown in the header, the title, the mails and the public pages |
| `OUTREACH_BASE_URL` | none | Absolute base URL put in front of unsubscribe links, for example `https://example.org`. Never taken from the request. Sending is refused while it is empty |
| `OUTREACH_FROM_EMAIL` | `DEFAULT_FROM_EMAIL` | Sender address of the mails |
| `OUTREACH_LANGUAGE` | `LANGUAGE_CODE` | Language of the Outreach pages, the unsubscribe pages and the mails |
| `OUTREACH_MAX_RECIPIENTS_PER_SEND` | `100` | Recipients per send action, the rest are skipped as over the limit |
| `OUTREACH_RESEND_COOLDOWN` | `timedelta(hours=24)` | A prospect mailed within this time is skipped |
| `OUTREACH_MAX_IMPORT_ROWS` | `5000` | An import file with more rows is rejected |
| `OUTREACH_MAX_IMPORT_BYTES` | `2000000` | An uploaded import file larger than this many bytes is rejected before it is parsed |
| `OUTREACH_LOGO_STATIC_PATH` | none | Static path of a logo (light). Without it the site name is shown as text |
| `OUTREACH_LOGO_DARK_STATIC_PATH` | none | Static path of the logo used in dark mode |
| `OUTREACH_IMPORT_HEADER_ALIASES` | `{}` | Extra import column names, see below |
| `OUTREACH_USER_PROSPECT_FIELDS` | none | Dotted path of a callable `(user) -> dict` giving extra prospect fields to `outreach_load_users`, see Loading users |
| `OUTREACH_THEME` | neutral palette | Colours and font, see Theming |

Settings the app relies on from Django:

| Setting | Use |
|---|---|
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | How mails leave. The app uses `django.core.mail.get_connection()` |
| `DEFAULT_FROM_EMAIL` | Sender when `OUTREACH_FROM_EMAIL` is not set |
| `SECRET_KEY` | Signs unsubscribe tokens and salts the suppression hashes, see Sending |

Import aliases: the CSV import reads the columns `email`, `first_name`, `last_name`, `organization`, `city`, `country` and `kind`. Headers are lower-cased and stripped. To accept other names, map the lower-case alias to a field name. They are also listed on the help page.

```python
OUTREACH_IMPORT_HEADER_ALIASES = {
    "prenom": "first_name",
    "nom": "last_name",
    "ville": "city",
}
```

Import rules: rows whose email already exists are skipped, never updated. One invalid row stops the whole file. A blank `kind` means `individual`. An address on the suppression list is imported as unsubscribed.

## Loading users as prospects

A user account is not a prospect, and not consent to bulk mail, so nothing creates prospects from users by itself. Run the command when the host decides to:

```
python manage.py outreach_load_users --dry-run
python manage.py outreach_load_users
```

- Users come from `get_user_model()`. The address is read from the model's email field, and `first_name` and `last_name` only if the model has them.
- Active users with a non-empty email are loaded. `--include-inactive` adds the others.
- Each prospect is created with `Prospect.save()`, so the address is lower-cased, a suppressed address is created as unsubscribed and the user is linked. An `added` event by `system` is recorded.
- A user who already has a prospect (same address, or already linked) is counted and left alone.
- `--dry-run` writes nothing. The output is counts only, never addresses.

For fields the package cannot know, point `OUTREACH_USER_PROSPECT_FIELDS` to a callable. It may return `kind`, `first_name`, `last_name`, `organization`, `city` and `country`; any other key makes the command fail.

```python
OUTREACH_USER_PROSPECT_FIELDS = "myproject.outreach.prospect_fields"


def prospect_fields(user):
    if hasattr(user, "company"):
        return {"kind": "organization", "organization": user.company.name}
    return {}
```

## Theming

`OUTREACH_THEME` accepts any subset of these keys. The values below are the defaults.

```python
OUTREACH_THEME = {
    "brand": "#1f2a44",
    "accent": "#2563eb",
    "on_accent": "#ffffff",
    "text": "#1f2937",
    "muted": "#6b7280",
    "background": "#f8fafc",
    "surface": "#ffffff",
    "border": "#e5e7eb",
    "avatar": None,  # derived from brand when None
    "font_family": None,  # system font stack when None
    "dark": {  # same colour keys, each falls back to the dark defaults
        "brand": "#93a4c6",
        "accent": "#60a5fa",
        "on_accent": "#0b1220",
        "text": "#e5e7eb",
        "muted": "#9ca3af",
        "background": "#0b1220",
        "surface": "#111a2e",
        "border": "#243049",
    },
}
```

- Colours may be hex with 3 to 8 digits, `rgb()`, `rgba()`, `hsl()`, `hsla()` or a CSS colour name. `font_family` is a CSS font stack. Anything else, an unknown key, or a non-dict value is an error reported by the system check `outreach.E001`. At runtime a bad value never breaks a page: that key falls back to its default (the dark palette falls back to the dark defaults) and one warning per distinct problem is logged on the `outreach` logger.
- The theme is written as CSS variables in one `<style>` block by `{% outreach_theme_css %}` (library `outreach_tags`), placed after the stylesheet. The dark values apply under `prefers-color-scheme: dark`.
- Email clients cannot use CSS variables or dark mode, so mails always use the light values.
- No font is shipped. Set `font_family`, and load the font in your own CSS.
- To change markup, override a template by path (`outreach/base.html`, `outreach/email/message.html`, `outreach/admin/index.html`, ...). Put it in a directory listed in `TEMPLATES["DIRS"]`, or in an app listed before `outreach` in `INSTALLED_APPS`.

## Internationalisation

- Message ids are English. A French catalogue ships in `src/outreach/locale/fr`.
- `USE_I18N` must be `True`, otherwise nothing is translated.
- `OUTREACH_LANGUAGE` picks the language per request with `translation.override`, so the rest of your site is unaffected. Variable labels use the message context `mail variable`, examples `mail variable example`.
- Compile the French catalogue after editing the `.po` (Babel is a dev dependency):

```
scripts/compile_messages.sh
```

- Add a language by creating `src/outreach/locale/<code>/LC_MESSAGES/django.po` (copy the French one and translate), then compile it with `pybabel compile -d src/outreach/locale -D django -l <code>`. Only `fr` is checked in CI.

## Computed tags

Besides `{{ variables }}`, a subject or body can call tags: `{% name %}` or `{% name "text" variable %}`. A tag is a Python function run once per recipient at send time, and its return value is written where the tag is. The output is always text and always escaped, so a tag cannot insert markup. Staff can only name a registered tag and give it quoted text or a variable name, nothing else is evaluated.

Built-in tags:

| Tag | Result |
|---|---|
| `{% today %}` or `{% today "j F Y" %}` | The send date, in `OUTREACH_LANGUAGE`. The optional argument is a Django date format |
| `{% greeting %}` | Good morning, afternoon or evening, from the server's local time at send |
| `{% member_since %}` | The `date_joined` of the linked user, empty for a prospect with no user |

A host project registers its own tags in a `mail_tags.py` module of any installed app, found at startup like `admin.autodiscover`:

```python
from outreach.models import Prospect
from outreach.services.mail_tags import mail_tag_library


@mail_tag_library.register(label="Account manager", example="Sam Lee")
def account_manager(prospect: Prospect, fallback: str = "") -> str:
    return prospect.user.account_manager.get_full_name() if prospect.user else fallback
```

- The first parameter is always the prospect. Every other parameter needs a default, and arguments are strings. A bare word in a call, such as `{% initial last_name %}`, is replaced by the raw value of that variable, or by the output of a tag of that name called with the prospect only. Tag names may not be `button` or equal to a variable key.
- Arguments come from staff, so treat them as untrusted input. A name already taken raises `ImproperlyConfigured` at startup.
- A tag with side effects declares a keyword-only `preview` parameter with a default: `def tag(prospect: Prospect, *, preview: bool = False) -> str`. It receives `True` while a message is only previewed in the compose step and `False` when the message is sent, so it can return a placeholder and skip the side effect. Staff text can never fill it, and registration refuses a `preview` parameter that is not keyword-only. A tag without the parameter is called as before.
- An exception in a tag fails that recipient only: the mail is not sent, the claim is restored and a failure event is recorded.
- The compose form rejects unknown tags, too many arguments (over 200 characters each is also refused) and stray `{%` or `%}`. The template preview shows each tag's `example` and never runs the function.
- Tags are applied before variables, so a prospect's data (a name containing `{% ... %}`) is never run as a tag.

### Buttons

`{% button "Read more" "https://example.org" %}` writes a link styled as a button, using `accent` and `on_accent` from `OUTREACH_THEME`. It takes exactly a label and a link, and only works in the message body, not in the subject. The link can be fixed text, a variable (`{% button "Leave" unsubscribe_url %}`) or a tag (`{% button "Book" booking_url %}`).

- The link must start with `http`, `https` or `mailto`. The compose form rejects a fixed link that does not. A variable or tag link is checked at send time: if it is empty or invalid, that recipient is not sent the message and is counted as failed, with a failure event.
- The plain-text part shows `Label (link)`. The button markup is added after the final sanitising pass, since the sanitiser strips inline styles. Outlook desktop ignores the padding of a link and shows a plain coloured link.
- The template preview shows the button with a placeholder link when it comes from a variable or a tag.

## Email templates

- A template has a name, a subject and a body. The body is sanitised and may contain variables, as in a message. Names are unique ignoring case.
- Templates are shared: every staff member who holds `outreach.view_emailtemplate` sees all of them, and the author is recorded only for information.
- On the compose page, choose a template and press Use template to fill the subject and body. Nothing is sent and nothing is kept until you press Preview.
- Save this message as a template stores the current subject and body under a name. It needs `add_emailtemplate`. Replacing an existing template (box ticked) also needs `change_emailtemplate`. A name that is taken without the box ticked is refused.
- Templates are managed under Templates in the sidebar. The edit page shows the template rendered with example values in a sandboxed preview.
- A mailing keeps its own copy of the subject and body, so editing or deleting a template never changes a mailing that was already sent.

## Audiences

- An audience is a named list of prospects, shared by every staff member who holds `outreach.view_audience`. A prospect can be in several audiences.
- Prospects are added and removed with two actions of the prospect list, which need `change_prospect`. The add page can also create a new audience from a typed name, with the same permission. The list can be filtered by audience. There is no audience on the CSV import.
- To mail an audience, filter the list by it, use Select all, then Send a mail. Membership never overrides an unsubscription: unsubscribed and suppressed members are skipped like any other prospect.
- Deleting an audience keeps its prospects. Deleting a prospect removes its memberships.

## Sending behaviour

- By default sending runs inside the admin request, one SMTP connection per action. This is not recommended in production. With `OUTREACH_DISPATCH = "celery"` one task per recipient is queued on the host project's Celery app, with retries on transient errors.
- Each recipient gets their own subject and body, personalised from their data. Variables are replaced by a fixed regex over a fixed list: `first_name`, `last_name`, `full_name`, `organization`, `email`, `city`, `country`, plus `unsubscribe_url`. Unknown or malformed placeholders are rejected by the compose form.
- Skipped recipients, with their reason: unsubscribed (status, or found unsubscribed just before sending), suppressed (address on the suppression list), recently contacted (inside `OUTREACH_RESEND_COOLDOWN`), over the send limit (beyond `OUTREACH_MAX_RECIPIENTS_PER_SEND`).
- Before the first mail, the recipients are claimed in a transaction (rows locked with `skip_locked`, `last_mailed_at` set, the `Mailing` created). A second click or a second request finds them in the cooldown. If a send fails or the recipient is no longer mailable, the previous `last_mailed_at` is restored.
- A `Mailing` stores counts per skip reason, never the names of skipped people. Its detail page lists the sent and failed recipients from the events recorded for it.
- The unsubscribe page changes nothing on GET (mail scanners follow links). A POST unsubscribes, and the same URL serves the `List-Unsubscribe-Post` one-click request. A valid link for a deleted prospect shows the confirmation page. A forged link is a 404.
- Unsubscribed is final: no admin action, import or form sets a prospect back. The address is also stored on a suppression list as a salted HMAC (`Suppression`), kept when the prospect is deleted. Adding the same address again creates a prospect that is already unsubscribed.
- Tokens are signed with `SECRET_KEY` (salt `outreach.unsubscribe`, no expiry). Suppression hashes use the salt `outreach.suppression` and `SECRET_KEY`. Both honour `SECRET_KEY_FALLBACKS`: after a rotation, sent unsubscribe links and the suppression list keep working while the old key stays in `SECRET_KEY_FALLBACKS`. Once the old key is removed, old links stop working and the old suppression hashes stop matching, so previously unsubscribed addresses can be mailed again until they are re-added.
- A prospect is linked to a user when exactly one user has the same email (case-insensitive, on `get_user_model().get_email_field_name()`) and that user has no prospect yet. The staff action "Link to user accounts" does it for existing prospects. First and last name of the linked user are used only when the prospect has none, and only if the user model has those fields.

## Security notes

- Message bodies are sanitised with nh3 when the form is cleaned and again when each mail is rendered. Allowed tags: `p div br strong em del h1 ul ol li blockquote a`, links limited to `http`, `https`, `mailto`. The result is sanitised once more after variables are inserted.
- Variable values are HTML-escaped. Author text never goes through the Django template engine.
- A `{% button %}` is only accepted in the text of a message. Inside a link or any other tag it is rejected, and a button link may not contain a space.
- Previews and the stored body of a mailing are shown in sandboxed iframes (`srcdoc`).
- `outreach_theme_css` writes values from `OUTREACH_THEME` into a `<style>` block. Only validated values reach it. A strict Content Security Policy needs a nonce or hash for that block.
- The CSV export always escapes cells that a spreadsheet would read as a formula (a leading `=`, `+`, `-`, `@`, tab or carriage return), because prospect fields are typed by users and exports are opened in spreadsheets.
- System check `outreach.E001` reports an invalid `OUTREACH_THEME`.
- Import and export are gated: import needs `add_prospect`, export needs `view_prospect`.

## App label

The app label is `outreach`, the same as the Python package. Tables are `outreach_prospect`, `outreach_prospect_audiences`, `outreach_prospectevent`, `outreach_mailing`, `outreach_mailingdelivery`, `outreach_suppression`, `outreach_emailtemplate` and `outreach_audience`; permissions are `outreach.*`; the URL namespace is `outreach` and the admin site instance is `outreach_admin`. A host project with another app labelled `outreach` will collide, so check before installing.

## Running the tests

Everything runs in Docker, nothing is installed on the host. The `app` service mounts the repository.

```
docker compose build app
docker compose run --rm app pytest
```

PostgreSQL:

```
docker compose up -d database
docker compose run --rm -e DATABASE_URL=postgres://outreach:outreach@database:5432/outreach app pytest
```

Custom user model (email as the username field, no names):

```
docker compose run --rm app pytest tests/host/test_custom_user_model.py --ds=tests.settings.custom_user
```

Lint:

```
docker compose run --rm app sh -c "ruff check . && ruff format --check ."
```

Another Python version for the image: `PYTHON_VERSION=3.13 docker compose build app`. CI runs Python 3.10 to 3.13 against Django 5.1 and 5.2, on SQLite and PostgreSQL.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report a security problem as described in [SECURITY.md](SECURITY.md), not in a public issue.

Licensed under the BSD 3-Clause licence, see `LICENSE`. Third-party notices are in `src/outreach/THIRD_PARTY_NOTICES.md`.
