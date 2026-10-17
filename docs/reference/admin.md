# Admin site, URLs and permissions

## The admin site

```{eval-rst}
.. autoclass:: outreach.sites.OutreachAdminSite
   :no-members:
```

`outreach.sites.outreach_site` is the instance, named `outreach_admin`. Each `ModelAdmin` registers
itself on it with `@admin.register(Model, site=outreach_site)`, and `outreach.admin` imports them
all.

| Model admin | Notes |
|---|---|
| `ProspectAdmin` | CSV import with a preview step. Actions: send mail, add to or remove from an audience, unsubscribe, link users, export as CSV. The email, status, last mailed date and user are read-only once saved |
| `AudienceAdmin` | Full CRUD. Shows the number of prospects of each audience |
| `MailingAdmin` | Read and delete only: it can not add or change |
| `EmailTemplateAdmin` | Full CRUD. Shows a sandboxed sample preview that never runs tags |

The site has no navigation sidebar of its own (`enable_nav_sidebar = False`), and its templates
replace Django's.

## URLs

Mounted with `include("outreach.urls")`. With the prefix `outreach/`:

| URL name | Path | Purpose |
|---|---|---|
| `outreach:unsubscribe` | `outreach/unsubscribe/<token>/` | Public unsubscribe page (GET shows, POST unsubscribes) |
| `outreach_admin:index` | `outreach/` | Dashboard |
| `outreach_admin:login` / `logout` | `outreach/login/`, `outreach/logout/` | Own login and logout |
| `outreach_admin:help` | `outreach/help/` | The *How to use* page |
| `outreach_admin:outreach_prospect_changelist` | `outreach/outreach/prospect/` | Prospect list |
| `outreach_admin:outreach_prospect_add` / `change` / `delete` / `history` | `outreach/outreach/prospect/add/`, `<id>/change/`, … | Prospect CRUD |
| `outreach_admin:outreach_prospect_import` / `process_import` | `outreach/outreach/prospect/import/`, … | CSV import and its confirmation |
| `outreach_admin:outreach_mailing_changelist` / `change` / `delete` | `outreach/outreach/mailing/` | Mailings |
| `outreach_admin:outreach_audience_changelist` / `add` / `change` / `delete` | `outreach/outreach/audience/` | Audiences |
| `outreach_admin:outreach_emailtemplate_changelist` / `add` / `change` / `delete` | `outreach/outreach/emailtemplate/` | Templates |

The send flow is a Django admin action on the prospect list, not a URL of its own.

(permissions)=
## Permissions

Access to the whole site requires `is_staff`, `is_active` and `outreach.view_prospect`. The
permissions are the standard model permissions:

| Permission | Allows |
|---|---|
| `outreach.view_prospect` | Open the site, list and read prospects, export them as CSV, the help page and the dashboard |
| `outreach.add_prospect` | Add a prospect, import a CSV file |
| `outreach.change_prospect` | Edit a prospect, send a mail, add to or remove from an audience, unsubscribe selected, link to user accounts |
| `outreach.delete_prospect` | Delete prospects |
| `outreach.view_audience` | See the Audiences list |
| `outreach.add_audience` | Create audiences |
| `outreach.change_audience` | Edit audiences |
| `outreach.delete_audience` | Delete audiences |
| `outreach.view_mailing` | Read the Mailings list and detail |
| `outreach.delete_mailing` | Delete a mailing log entry (mailings can not be added or changed) |
| `outreach.view_emailtemplate` | See the Templates list, use a template on the compose page |
| `outreach.add_emailtemplate` | Create templates, save a message as a template |
| `outreach.change_emailtemplate` | Edit templates, replace a template when saving a message |
| `outreach.delete_emailtemplate` | Delete templates |

The permission codenames, the app label, the table names, the admin site instance name and the
URL names `outreach:unsubscribe` and `outreach_admin:*` are stored by host projects in their
database, groups and URLs. They are part of the public contract and are not renamed.
