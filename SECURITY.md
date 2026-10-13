# Security policy

## Supported versions

django-outreach is in beta. Only the latest release on PyPI receives security fixes.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private reporting: open the **Security** tab of the repository, choose **Report a vulnerability**, and describe the problem, the version, and how to reproduce it.

Reports are handled on a best-effort basis by a single maintainer. A fix is released as a new beta version and named in the changelog once it is out.

## Scope

django-outreach sends bulk email on behalf of staff users and holds personal data (names, email addresses, organisations). The most useful reports concern:

- Content that reaches a recipient or a staff browser without being sanitised (message bodies, variables, tags, buttons, the preview).
- Anything that mails an address that unsubscribed or is on the suppression list.
- Access to the outreach admin, the import or the export without the matching `outreach.*` permission.
- Forged or guessable unsubscribe links.

The `example/` project is a demonstration only. It has a public secret key, `DEBUG` on and a `demo` / `demo` superuser, so reports about deploying it as is are not vulnerabilities.

## Known limitations

These are understood and accepted for the beta. They are not vulnerabilities, but you should know them when you deploy:

- Sending is synchronous, runs inside the admin request, and is capped per action.
- If a send fails after the SMTP server may already have accepted the message (a timeout, for example), the claim on the recipient is restored and a later send can reach them again.
- Unsubscribe links do not expire and the unsubscribe page has no rate limit. The signature cannot be guessed, and permanent links are the norm for one-click unsubscribe.
- `SECRET_KEY` signs unsubscribe links and keys the suppression list. Keep the old key in `SECRET_KEY_FALLBACKS` after a rotation, or old links stop working and suppression entries stop matching.
- Prospect fields can be used as a button link or a tag argument. The link is still limited to `http`, `https` and `mailto`, and the value only affects that prospect's own mail.
- A failed send stores the error text in the prospect's history. An SMTP error can contain the recipient's address.
- The CSV export escapes cells that start with `=`, `+`, `-`, `@`, tab or carriage return, so spreadsheet formulas typed by users do not run. The import trusts nothing in the file: every row is validated like a form.
