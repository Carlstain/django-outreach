# django-outreach

django-outreach is a reusable Django app for prospect lists, reusable email templates and bulk
mail with one-click unsubscribe. It runs on its own admin site, separate from `/admin/`, and
brings its own models, templates, static files and French translation.

:::{warning}
This is a beta. It is meant to be installed and tried, and the interface may still change before
`0.1.0`. The initial migration `0001_initial` is frozen, so an installation can be upgraded
without resetting its tables.
:::

## What it does

- Prospects (a person or an organisation) with an optional link to the host project's user model.
- Message variables such as `{{ first_name }}` and `{{ first_name | friend }}` (a fallback when the
  value is empty), taken from a fixed list.
- Computed tags such as `{% today %}`, and buttons written as `{% button "Read more" link %}`.
- A rich text message body (Trix editor), sanitised with nh3.
- Email templates: named subject and body pairs shared by every staff member who has the
  permission.
- A `Mailing` log for every send, with counts of sent, failed and skipped recipients.
- One-click unsubscribe links (with `List-Unsubscribe` headers) and a suppression list that
  survives the deletion of a prospect.
- CSV and spreadsheet import and export through django-import-export.
- A built-in help page for the staff, in English and French.

## Where to start

:::{list-table}
:header-rows: 1

* - You want to
  - Read
* - Add the app to a Django project
  - {doc}`installation`, then {doc}`configuration`
* - Use the admin site to mail people
  - {doc}`user-guide/index`
* - Write your own mail tags, theme the site or load users
  - {doc}`topics/index`
* - Look up a class, a template, a URL or a permission
  - {doc}`reference/index`
:::

A runnable host project is in the `example/` directory of the
[repository](https://github.com/Carlstain/django-outreach).

```{toctree}
:hidden:
:maxdepth: 2

installation
configuration
user-guide/index
topics/index
reference/index
changelog
```
