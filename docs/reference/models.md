# Models and choices

Models are imported from `outreach.models`, choices from `outreach.choices`. Table names are
`outreach_<model>` and are part of the public contract with host projects.

## Data model

```
Prospect (outreach_prospect)             Mailing (outreach_mailing)
  uuid pk                                  uuid pk
  email unique, lower-cased                subject, body_html (sanitised, variables not replaced)
  kind, first_name, last_name              sender
  organization, city, country              sent_count, failed_count, skipped_count
  status                                   skipped_reasons (JSON, counts per reason)
  user  -- OneToOne, optional,             created_at
          SET_NULL, host user model              ^
  last_mailed_at, created_at, updated_at         | SET_NULL, optional
        ^                                        |
        | CASCADE                          ProspectEvent (outreach_prospectevent)
        +----------------------------------  prospect FK, mailing FK
                                             kind, detail, actor, created_at

                                         MailingDelivery (outreach_mailingdelivery)
                                           mailing FK, prospect FK (both CASCADE)
                                           status, attempts, previous_mailed_at, last_error
                                           one row per recipient, unique (mailing, prospect)

EmailTemplate (outreach_emailtemplate)   uuid pk, name (unique ignoring case), subject,
                                         body_html (sanitised), created_by, updated_by (both
                                         optional FK to the host user model, SET_NULL),
                                         created_at, updated_at. No foreign key to it from a
                                         Mailing, which keeps a copy.

Audience (outreach_audience)           uuid pk, name (unique ignoring case), description,
                                         created_by, updated_by, created_at, updated_at.
                                         Prospect.audiences is a many-to-many to it
                                         (table outreach_prospect_audiences).

Suppression (outreach_suppression)       email_hash pk (salted HMAC of the address), created_at
                                         no foreign key: it outlives the prospect
```

## Models

```{eval-rst}
.. autoclass:: outreach.models.Prospect
   :members: display_name, initials
   :undoc-members:

.. autoclass:: outreach.models.ProspectEvent
   :members: record

.. autoclass:: outreach.models.Mailing

.. autoclass:: outreach.models.MailingDelivery

.. autoclass:: outreach.models.EmailTemplate

.. autoclass:: outreach.models.Audience

.. autoclass:: outreach.models.BaseModel

.. autoclass:: outreach.models.AuthoredModel

.. autoclass:: outreach.models.Suppression
```

## Choices

```{eval-rst}
.. autoclass:: outreach.choices.ProspectKind
   :members:
   :undoc-members:

.. autoclass:: outreach.choices.ProspectStatus
   :members:
   :undoc-members:

.. autoclass:: outreach.choices.EventKind
   :members:
   :undoc-members:

.. autoclass:: outreach.choices.SkipReason
   :members:
   :undoc-members:
```

The actors recorded on events are the constants `ACTOR_SYSTEM` (`"system"`), `ACTOR_RECIPIENT`
(`"recipient"`, an unsubscribe by the person) and `ACTOR_IMPORT` (`"import"`) in
`outreach.choices`. Staff actions record the user name instead.
