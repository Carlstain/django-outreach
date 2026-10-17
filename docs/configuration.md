# Configuration

All settings are optional except `OUTREACH_BASE_URL`, which sending needs. They are read lazily,
so `override_settings` works in tests.

## Outreach settings

| Setting | Default | Meaning |
|---|---|---|
| `OUTREACH_SITE_NAME` | `"Outreach"` | Name shown in the header, the title, the mails and the public pages |
| `OUTREACH_BASE_URL` | none | Absolute base URL put in front of unsubscribe links, for example `https://example.org`. Never taken from the request. Sending is refused while it is empty |
| `OUTREACH_FROM_EMAIL` | `DEFAULT_FROM_EMAIL` | Sender address of the mails |
| `OUTREACH_LANGUAGE` | `LANGUAGE_CODE` | Default language of the Outreach pages and the unsubscribe pages. Each staff member can pick another for their own screens, see {doc}`topics/languages` |
| `OUTREACH_MAIL_LANGUAGE` | `OUTREACH_LANGUAGE` | Language the compose page starts on. A mail's language is chosen per mail, see {doc}`topics/languages`. One of `en`, `fr`, `es`, `pt`, `pt-br`, checked by `outreach.E004` |
| `OUTREACH_DISPATCH` | `"sync"` | `"sync"` sends inside the admin request, `"celery"` queues one task per recipient, see {doc}`topics/sending-with-celery`. Sync is not recommended in production |
| `OUTREACH_MAX_RECIPIENTS_PER_SEND` | `100` | Recipients per send action in sync mode, the rest are skipped as over the limit |
| `OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND` | `5000` | Same limit in Celery mode |
| `OUTREACH_CELERY_QUEUE` | none | Celery queue of the delivery tasks. Without it the default queue is used |
| `OUTREACH_DELIVERY_MAX_RETRIES` | `3` | Retries of a delivery after a transient error, Celery mode only |
| `OUTREACH_RESEND_COOLDOWN` | `timedelta(hours=24)` | A prospect mailed within this time is skipped |
| `OUTREACH_MAX_IMPORT_ROWS` | `5000` | An import file with more rows is rejected |
| `OUTREACH_MAX_IMPORT_BYTES` | `2000000` | An uploaded import file larger than this many bytes is rejected before it is parsed |
| `OUTREACH_LOGO_STATIC_PATH` | none | Static path of a logo (light). Without it the site name is shown as text |
| `OUTREACH_LOGO_DARK_STATIC_PATH` | none | Static path of the logo used in dark mode |
| `OUTREACH_EMAIL_LOGO_IN_HEADER` | `False` | Put `OUTREACH_LOGO_STATIC_PATH` centered at the top of mails. Without a header text the logo stands alone, the site name is not repeated as text |
| `OUTREACH_EMAIL_LOGO_IN_FOOTER` | `False` | Put `OUTREACH_LOGO_STATIC_PATH` at the start of the footer of mails |
| `OUTREACH_IMPORT_HEADER_ALIASES` | `{}` | Extra import column names, see {ref}`import-aliases` |
| `OUTREACH_USER_PROSPECT_FIELDS` | none | Dotted path of a callable `(user) -> dict` giving extra prospect fields to `outreach_load_users`, see {doc}`topics/loading-users` |
| `OUTREACH_THEME` | neutral palette | Colours and font, see {doc}`topics/theming` |

## Settings from Django

| Setting | Use |
|---|---|
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | How mails leave. The app uses `django.core.mail.get_connection()` |
| `DEFAULT_FROM_EMAIL` | Sender when `OUTREACH_FROM_EMAIL` is not set |
| `SECRET_KEY`, `SECRET_KEY_FALLBACKS` | Sign unsubscribe tokens and salt the suppression hashes, see {doc}`topics/security` |
| `USE_I18N` | Must be `True`, otherwise nothing is translated |

(import-aliases)=
## Import column aliases

The import reads the columns `email`, `first_name`, `last_name`, `organization`, `city`,
`country` and `kind`. Headers are lower-cased and stripped. To accept other names, map the
lower-case alias to a field name. They are also listed on the help page.

```python
OUTREACH_IMPORT_HEADER_ALIASES = {
    "prenom": "first_name",
    "nom": "last_name",
    "ville": "city",
}
```

Import rules:

- Rows whose email already exists are skipped, unless the import is asked to update them, see
  {doc}`user-guide/prospects`.
- One invalid row stops the whole file.
- A blank `kind` means `individual`.
- An address on the suppression list is imported as unsubscribed.

## Sending behaviour at a glance

- By default sending runs inside the admin request, one SMTP connection per action. This is not
  recommended in production: use `OUTREACH_DISPATCH = "celery"`, see
  {doc}`topics/sending-with-celery`.
- `OUTREACH_MAX_RECIPIENTS_PER_SEND` caps one synchronous action. A send takes about 0.3 s per
  SMTP message, so the default of 100 fits under a typical 60 s proxy timeout.
  `OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND` caps one action in Celery mode.
- `OUTREACH_RESEND_COOLDOWN` stops a double submit and an accidental second mailing.

The full rules are in {doc}`user-guide/sending-mail`.

## System checks

| Id | Level | Raised when |
|---|---|---|
| `outreach.E001` | Error | `OUTREACH_THEME` is not valid, see {doc}`topics/theming` |
| `outreach.E002` | Error | `OUTREACH_DISPATCH` is not `"sync"` or `"celery"` |
| `outreach.E003` | Error | `OUTREACH_DISPATCH` is `"celery"` and Celery is not installed |
| `outreach.W001` | Warning | `OUTREACH_DISPATCH` is `"sync"` and `DEBUG` is `False`. Only reported by `check --deploy` |
