# Languages

Outreach has three separate language choices. None of them translates the text your staff write.

| What | Who chooses | Where | Default |
|---|---|---|---|
| Language of the screens | Each staff member | The language menu in the header and on the login page | `OUTREACH_LANGUAGE` |
| Language of a mail | The person writing the mail | The *Language* field of the compose page and of a template | `OUTREACH_MAIL_LANGUAGE`, then `OUTREACH_LANGUAGE` |
| Language of the unsubscribe page | The mail it came from | The `lang` parameter of the link | `OUTREACH_LANGUAGE` |

Shipped languages: English (`en`), French (`fr`), Spanish (`es`), Portuguese (`pt`) and Brazilian
Portuguese (`pt-br`).

## The mail language

The language of a mail translates only what Outreach writes itself:

- the footer and the unsubscribe link text of a newsletter,
- the output of the tags `{% greeting %}`, `{% today %}` and `{% member_since %}`,
- the page the unsubscribe link opens.

The subject, the body, host variables and prospect data are never translated. To write to
prospects in several languages, write one mail per language and send each to its own
{doc}`audience <../user-guide/audiences>`, or save a template per language.

The compose page always starts on `OUTREACH_MAIL_LANGUAGE`, whatever language the staff member's
screens use, so two staff members start from the same value. Applying a template fills in its
language, or the default if it has none. A mailing keeps the language it was sent in, so a retry or
a scheduled send never changes language when a setting changes later. Mailings sent before the
field existed use `OUTREACH_LANGUAGE`.

A test send and the preview use the chosen language.

## The language of the screens

The menu stores the choice in the `outreach_language` cookie of the browser, for a year. It is a
preference of the person who set it and is never used for a mail. A missing or unknown value falls
back to `OUTREACH_LANGUAGE`. The choice is per browser, not per account.

## The unsubscribe page

The link in a mail carries `?lang=<code>` when the mail's language differs from
`OUTREACH_LANGUAGE`, and the page and its confirmation open in that language. The value is only
used to pick a shipped language. A regional code such as `es-MX` selects `es`, and an unknown one
selects the site language. The link's token is unchanged. A link copied from an older mail has no
`lang` and shows the site language.

## Settings

`OUTREACH_LANGUAGE` and `OUTREACH_MAIL_LANGUAGE` take any of `en`, `fr`, `es`, `pt` and `pt-br`
(`pt_BR` is accepted). `OUTREACH_MAIL_LANGUAGE` is checked by `outreach.E004`.
