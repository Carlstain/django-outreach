# django-outreach

django-outreach is a reusable Django app for prospect lists, reusable email templates and bulk
mail with one-click unsubscribe. It runs on its own admin site, separate from `/admin/`, and
brings its own models, templates, static files and translations (English, French, Spanish, Portuguese and Brazilian Portuguese).

:::{warning}
django-outreach is at version 0.x. Use it in production with caution: until 1.0, a minor
version (`0.2`, `0.3`, ...) may change the interface, and every change is listed in the
changelog. Read the changelog before you upgrade, and test an upgrade on a copy of your data
first. Migrations are never edited once released. The Spanish and Portuguese catalogues are
drafts that a native speaker has not reviewed yet.
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
- CSV import with a preview step, and CSV export of selected prospects.
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
