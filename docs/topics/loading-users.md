# Loading users as prospects

A user account is not a prospect, and not consent to bulk mail, so nothing creates prospects from
users by itself. There is deliberately no `post_save` signal. Run the command when the host
decides to:

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
