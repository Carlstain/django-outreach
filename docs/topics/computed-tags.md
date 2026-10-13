# Computed tags

Besides `{{ variables }}`, a subject or message can call tags: `{% name %}` or
`{% name "text" variable %}`. A tag is a Python function run once per recipient at send time, and
its return value is written where the tag is.

- The output is always text and always escaped, so a tag can not insert markup.
- Staff can only name a registered tag and give it quoted text or a variable name. Nothing else
  is evaluated. This is why variables and tags are replaced by a regex over a fixed list and never
  by the Django template engine: staff type the text, and it must never reach a code path other
  than a named function.

## Built-in tags

| Tag | Result |
|---|---|
| `{% today %}` or `{% today "j F Y" %}` | The send date, in `OUTREACH_LANGUAGE`. The optional argument is a Django date format |
| `{% greeting %}` | Good morning, afternoon or evening, from the server's local time at send |
| `{% member_since %}` | The `date_joined` of the linked user, empty for a prospect with no user |

## Registering your own

Register tags in a `mail_tags.py` module of any installed app. They are found at startup, like
`admin.autodiscover`.

```python
from outreach.models import Prospect
from outreach.services.mail_tags import mail_tag_library


@mail_tag_library.register(label="Account manager", example="Sam Lee")
def account_manager(prospect: Prospect, fallback: str = "") -> str:
    return prospect.user.account_manager.get_full_name() if prospect.user else fallback
```

Then use it as `{% account_manager "your account team" %}`.

Rules, checked when the tag is registered (see {meth}`~outreach.services.mail_tags.MailTagLibrary.register`):

- The first parameter is always the prospect.
- Every other parameter needs a default, and arguments are strings.
- A tag name may not be `button` or equal to a variable key, and may not be registered twice.
  Each raises `ImproperlyConfigured` at startup.
- A bare word in a call, such as `{% initial last_name %}`, is replaced by the raw value of that
  variable, or by the output of a tag of that name called with the prospect only.
- Arguments come from staff, so treat them as untrusted input.

## Tags with side effects

A tag with side effects declares a keyword-only `preview` parameter with a default:

```python
@mail_tag_library.register(label="Booking link", example="https://example.org/book/abc")
def booking_link(prospect: Prospect, *, preview: bool = False) -> str:
    if preview:
        return "https://example.org/book/preview"
    return create_booking_link(prospect)
```

It receives `True` while a message is only previewed in step 2 of the send and `False` when the
message is sent, so it can return a placeholder and skip the side effect. Staff text can never
fill it, and registration refuses a `preview` parameter that is not keyword-only. A tag without
the parameter is called as usual.

## Failure, validation and preview

- An exception in a tag fails that recipient only: the mail is not sent, the claim is restored and
  a failure event is recorded.
- The compose form rejects unknown tags, a wrong number of arguments, an argument over 200
  characters and stray `{%` or `%}`.
- Tags are applied before variables, so a prospect's data (a name containing `{% ... %}`) is never
  run as a tag.
- The preview of an {doc}`email template <../user-guide/email-templates>` shows each tag's
  `example` and never runs the function, because there is no real prospect and a preview must not
  run host code.
- Tags are listed with their `label` and `example` on the help page.

## Buttons

`{% button "Read more" "https://example.org" %}` is a text construct handled by
{class}`~outreach.services.mail_buttons.MailButtons`, not a registered tag, which is why the name
`button` is reserved. It is not an editor feature because the editor keeps only `href` on links,
so any marker on a link would be lost.

- It takes exactly a label and a link, and only works in the message body, not in the subject.
- The link can be fixed text, a variable (`{% button "Leave" unsubscribe_url %}`) or a tag
  (`{% button "Book" booking_url %}`).
- The link must start with `http`, `https` or `mailto` and contain no space. The compose form
  rejects a fixed link that does not. A variable or tag link is checked at send time: if it is
  empty or invalid, that recipient is not sent the message and is counted as failed, with a
  failure event ({class}`~outreach.services.mail_buttons.InvalidButtonLink`).
- Each button is swapped for a random token before tags and variables run, and the styled link is
  written after the last sanitising pass, because the sanitiser strips inline styles. Prospect data
  can therefore never become a button.
- The style uses `accent` and `on_accent` from `OUTREACH_THEME`. Outlook desktop ignores the
  padding of a link and shows a plain coloured link.
