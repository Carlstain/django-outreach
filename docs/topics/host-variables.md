# Host variables

The variables of a mail (`{{ first_name }}`, `{{ city }}` and so on) come from a fixed list. Your
project can add its own, for example `{{ plan_name }}` or `{{ coupon }}`, without copying any
template. They are used, listed and refused exactly like the built-in ones.

## Registering a variable

Write a function that takes the prospect and returns the text, and register it in a
`mail_variables.py` module of an installed app. Outreach finds that module when Django starts.

```python
# myapp/mail_variables.py
from outreach.models import Prospect
from outreach.services.mail_variables import mail_variable_library


@mail_variable_library.register(label="Plan", example="Pro")
def plan_name(prospect: Prospect) -> str | None:
    subscription = (
        Subscription.objects.filter(email=prospect.email).select_related("plan").first()
    )
    return subscription.plan.name if subscription else None
```

Staff then write `{{ plan_name | your plan }}` in a subject or a message.

- The name is the function name, or `name="..."`. It must be letters, digits and `_`.
- `label` and `example` fill the *Insert variable* menu, the *How to use* page and the preview of an
  email template. Mark both for translation with `pgettext_lazy` if your project is multilingual.
- The function takes the prospect first. Any other parameter needs a default value.

## What it does

- **It runs only when a message uses it**, once for each recipient, however often the message writes
  it. A message without `{{ plan_name }}` never calls the function.
- **`None` or an empty text takes the fallback**: `{{ plan_name | your plan }}` writes "your plan"
  for a prospect without a subscription. Any other value is turned into text.
- **It runs while the delivery is locked.** A mail is rendered and sent inside the transaction that
  locks its delivery, so a slow function holds that one delivery. Keep it fast and make no network call.
- **A user is loaded with the prospect.** `prospect.user` costs no query when a mail is sent, so a
  variable can read the account. Any other lookup is a query for each recipient: keep it light, or cache it.
- **A function that raises fails that recipient**, like a tag that raises: the mail is not sent, the
  claim is restored and the failure is *the message could not be built*. The others still receive it.
- **The compose preview and a test send** pass `preview=True` to a function that declares a
  keyword-only `preview` parameter with a default, as a tag can, so a variable with a side effect can
  return a placeholder:

```python
@mail_variable_library.register(label="Coupon", example="SAVE10")
def coupon(prospect: Prospect, *, preview: bool = False) -> str:
    return "SAVE10" if preview else create_coupon(prospect)
```

## Rules

- A name that is a built-in variable (`first_name`, ..., `unsubscribe_url`), `button`, a registered
  tag or an already registered variable is refused with `ImproperlyConfigured` at startup. A tag can
  not take the name of a variable either, whichever is registered first.
- The template preview of an email template shows the `example` and never runs the function.

## Security

The value is plain text. In a message it is HTML-escaped, and in a subject or the text part its
line breaks are flattened. It is written in one pass, so a value that contains `{{ first_name }}`,
`{% tag %}` or `{% button %}` is shown as written and never run. The function itself is your code,
chosen by you and never by staff.

## A variable or a tag?

Use a variable for a value you simply write, with an optional fallback and an entry in the editor
menu. Use a {doc}`tag <computed-tags>` when staff pass it arguments, such as a name or a length.
A tag can take a variable as an argument: `{% button "Offer" offer_url %}`.
