# Services

The business logic lives in `outreach.services`. It takes models and plain values, never request
objects, and raises standard exceptions, so it can be called from a management command, a task or
a test as easily as from the admin.

## Sending

```{eval-rst}
.. autoclass:: outreach.services.mailing.ProspectMailer
   :members: plan, render, send, retry

.. autoclass:: outreach.services.mailing.MailPlan
   :members:

.. autoclass:: outreach.services.mailing.MailReport
   :members:
```

```python
from outreach.services.mailing import ProspectMailer

mailer = ProspectMailer(base_url="https://example.org", actor="cron")
report = mailer.send(prospects, "Hello {{ first_name | there }}", "<p>News for you.</p>")
print(len(report.sent), len(report.failed), report.skipped_counts)
```

## Variables, tags and buttons

```{eval-rst}
.. autoclass:: outreach.services.variables.MailVariables
   :members: values_for

.. autoclass:: outreach.services.mail_tags.MailTagLibrary
   :members: register, catalog, render

.. autoclass:: outreach.services.mail_buttons.MailButtons
   :members: is_valid_link, extract, insert

.. autoexception:: outreach.services.mail_buttons.InvalidButtonLink
```

The shared library instance is `outreach.services.mail_tags.mail_tag_library`, and the shared
button helper is `outreach.services.mail_buttons.mail_buttons`. The built-in tags are defined in
`outreach.mail_tags`:

```{eval-rst}
.. autofunction:: outreach.mail_tags.today

.. autofunction:: outreach.mail_tags.greeting

.. autofunction:: outreach.mail_tags.member_since
```

## Message bodies

```{eval-rst}
.. autoclass:: outreach.services.body.MailBodySanitizer
   :members: clean, to_text
```

## Unsubscribing and suppression

```{eval-rst}
.. autoclass:: outreach.services.unsubscribe.SuppressionList
   :members: contains, add, filter_suppressed

.. autoclass:: outreach.services.unsubscribe.UnsubscribeTokens
   :members: make, resolve, is_signed

.. autoclass:: outreach.services.unsubscribe.ProspectUnsubscriber
   :members: unsubscribe
```

## Subscribing

```{eval-rst}
.. autoclass:: outreach.services.subscription.ProspectSubscriptions
   :members: subscribe

.. autoclass:: outreach.services.subscription.SubscribeResult
   :members:
```

The signals are listed in {doc}`../topics/signals`.

## Access and erasure

```{eval-rst}
.. autoclass:: outreach.services.prospect_export.ProspectDataExporter
   :members: export

.. autoclass:: outreach.services.erasure.ProspectEraser
   :members: erase
```

## Templates

```{eval-rst}
.. autoclass:: outreach.services.templates.EmailTemplates
   :members: save

.. autoclass:: outreach.services.templates.SavedTemplate
   :members:

.. autoexception:: outreach.services.templates.TemplateNameTaken
```

## Audiences

```{eval-rst}
.. autoclass:: outreach.services.audiences.AudienceCreator
   :members: create

.. autoexception:: outreach.services.audiences.AudienceNameTaken

.. autoclass:: outreach.services.audiences.AudienceMembers
   :members: add, remove
```

## CSV import and export

```{eval-rst}
.. autoclass:: outreach.services.prospect_csv.ProspectCsvImporter
   :members: preview, apply

.. autoclass:: outreach.services.prospect_csv.ImportPreview
   :members:

.. autoclass:: outreach.services.prospect_csv.ProspectCsvExporter
   :members: to_csv

.. autoexception:: outreach.services.prospect_csv.CsvImportError
```

## Users

```{eval-rst}
.. autoclass:: outreach.services.linking.UserLinker
   :members: link

.. autoclass:: outreach.services.user_loading.UserProspectLoader
   :members: load

.. autoclass:: outreach.services.user_loading.UserLoadReport
   :members:
```

## Theme

```{eval-rst}
.. autoclass:: outreach.theme.OutreachTheme
   :members: errors, css, email
```
