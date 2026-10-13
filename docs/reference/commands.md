# Management commands

## `outreach_load_users`

Creates a prospect for each user account that has none. Existing prospects are untouched. See
{doc}`../topics/loading-users` for the rules.

```shell
python manage.py outreach_load_users [--dry-run] [--include-inactive]
```

| Option | Effect |
|---|---|
| `--dry-run` | Prints the counts and writes nothing |
| `--include-inactive` | Also loads inactive users |

The command prints counts only, never addresses:

```text
Users selected: 120. Prospects created: 97 (unsubscribed: 2). Already prospects: 20. Invalid: 3.
```

A `OUTREACH_USER_PROSPECT_FIELDS` callable that returns a key outside `kind`, `first_name`,
`last_name`, `organization`, `city` and `country` makes the command fail with an error.
