# Custom user model

The app reaches the host's users through `settings.AUTH_USER_MODEL` and imports nothing else from
the host project.

## What is read

- The email field name, from `get_user_model().get_email_field_name()`.
- `first_name` and `last_name`, only if the model has them.
- `is_active`, by `outreach_load_users`, only if the model has it.
- In templates: `user.get_username`, `get_short_name`, `email` and `date_joined`, guarded with
  `firstof` or `if`, so they degrade silently on a custom model that lacks them. This includes
  the `{% member_since %}` tag, which is empty without `date_joined`.

Nothing else is read.

## Relation

`Prospect.user` is an optional `OneToOneField` to the user model, with `SET_NULL` on delete and the
reverse name `outreach_prospect`. Deleting a user keeps the prospect.

The test suite runs against a user model that uses the email as its username field and has no
name fields, to keep this contract honest.
