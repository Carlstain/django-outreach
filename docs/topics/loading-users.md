# Loading users as prospects

A user account is not a prospect, and not consent to bulk mail, so by default nothing creates
prospects from users by itself. Run the command when the host decides to, or turn on
[automatic sync](#automatic-sync) for new users:

```shell
python manage.py outreach_load_users --dry-run
python manage.py outreach_load_users
```

- Users come from `get_user_model()`. The address is read from the model's email field, and
  `first_name` and `last_name` only if the model has them.
- Active users with a non-empty email are loaded. `--include-inactive` adds the others.
- Each prospect is created with `Prospect.save()`, so the address is lower-cased, a suppressed
  address is created as unsubscribed and the user is linked. An *added* event by `system` is
  recorded.
- A user who already has a prospect (same address, or already linked) is counted and left alone.
- A user whose data does not validate is counted as invalid and skipped.
- `--dry-run` writes nothing. The output is counts only, never addresses.

The work is done by {class}`~outreach.services.user_loading.UserProspectLoader`, see
{doc}`../reference/commands`.

## Extra fields

For fields the package can not know, point `OUTREACH_USER_PROSPECT_FIELDS` to a callable that
takes the user and returns a dict. It may return `kind`, `first_name`, `last_name`,
`organization`, `city` and `country`. Any other key makes the command fail.

```python
OUTREACH_USER_PROSPECT_FIELDS = "myproject.outreach.prospect_fields"


def prospect_fields(user):
    if hasattr(user, "company"):
        return {"kind": "organization", "organization": user.company.name}
    return {}
```

## Linking

Separately from loading, a prospect is linked to a user when exactly one user has the same email
(case-insensitive, on `get_user_model().get_email_field_name()`) and that user has no prospect
yet. It happens when a prospect is created, and the staff action *Link to user accounts* does it
for existing prospects. The names of the linked user are used only when the prospect has none, and
only if the user model has those fields.

## Automatic sync

`OUTREACH_SYNC_USERS` is off by default. When set, a `post_save` receiver syncs each *newly
created* user, after the transaction commits. A failure is logged on the `outreach` logger with
the user's primary key, never the address, and never breaks the sign-up.

| Value | A matching prospect | No prospect yet |
| --- | --- | --- |
| `False` (default) | untouched | nothing |
| `"link"` | linked to the user | nothing |
| `"create"` | linked to the user | created and linked |

Linking mails nobody new, so it is safe whatever the consent rules. **Creating** makes the
address mailable, so only use `"create"` if signing up is consent in your application. To honour
a choice the user made, add a filter. It runs after commit, so rows saved in the same transaction
as the user are visible:

```python
OUTREACH_SYNC_USERS = "create"
OUTREACH_SYNC_USERS_FILTER = "myproject.outreach.accepts_marketing"


def accepts_marketing(user):
    return user.profile.accepts_marketing
```

- A filter returning `False`, or raising, creates nothing. Linking still happens.
- Only active users are created. An inactive user, for example one waiting for email
  verification, is not picked up later: run `outreach_load_users` or call
  `ProspectSubscriptions.subscribe` when the user is activated.
- Only creation triggers the sync. Later saves, including an email change, do nothing.
- `bulk_create`, raw SQL and fixture loading skip signals. `outreach_load_users` is the catch-up.
- A created prospect gets an *added* event by `system` with the detail `user sync`.
  `OUTREACH_USER_PROSPECT_FIELDS` applies as it does for the command.

If the host manages consent itself, leave the sync off, or use `"link"` and create prospects
with `ProspectSubscriptions.subscribe` when the user opts in. An opt-out is
`ProspectUnsubscriber`, which suppresses the address **permanently**: there is no resubscribe.
