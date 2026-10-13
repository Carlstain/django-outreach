# Security notes

To report a vulnerability, follow
[SECURITY.md](https://github.com/Carlstain/django-outreach/blob/main/SECURITY.md) and do not open
a public issue. The same file lists the known limitations.

## Message content

- Message bodies are sanitised with nh3 when the form is cleaned and again when each mail is
  rendered, and once more after variables are inserted. A direct service call can not bypass the
  form, and a variable value can not create a `javascript:` link.
- Allowed tags are `p div br strong em del h1 ul ol li blockquote a`. Links keep only `href`, and
  only `http`, `https` and `mailto` URLs are kept.
- Variable values are HTML-escaped, and tag output is escaped too. Author text never goes through
  the Django template engine.
- A `{% button %}` is only accepted in the text of a message. Inside a link or any other tag it is
  rejected, and a button link may not contain a space.
- Previews and the stored body of a mailing are shown in sandboxed iframes (`srcdoc`).

## Sending

- Links in mails use `OUTREACH_BASE_URL`, never the `Host` header of the request.
- Mail is claimed before it is sent, inside a transaction with `select_for_update(skip_locked=True)`,
  and the claim is restored on failure. A double submit can not send twice.
- Skipped recipients are stored as counts, never as names.

## Unsubscribe tokens and the suppression list

- Tokens are signed with `SECRET_KEY` (salt `outreach.unsubscribe`, no expiry). Suppression hashes
  are salted HMACs of the lower-cased address (salt `outreach.suppression`). Both honour
  `SECRET_KEY_FALLBACKS`.
- After a rotation, sent unsubscribe links and the suppression list keep working while the old key
  stays in `SECRET_KEY_FALLBACKS`. Once the old key is removed, old links stop working and the old
  hashes stop matching, so previously unsubscribed addresses can be mailed again until they are
  added again.
- The two salts must not change, or every link already sent and every stored hash breaks.
- A GET on the unsubscribe page changes nothing, because mail scanners follow links. A POST
  unsubscribes, and the same URL serves the `List-Unsubscribe-Post` one-click request. The page
  sends `Referrer-Policy: no-referrer`.

## Import and export

- The CSV export always escapes cells that start with `=`, `+`, `-`, `@`, a tab or a carriage
  return, with a leading apostrophe. Prospect fields are typed by users and exports are opened in
  spreadsheets, so a name such as `=SUM(1+1)` must not run there. There is nothing to configure.
- The import re-reads and re-validates the file when it is confirmed, so the text carried by the
  confirmation form is never trusted. Nothing is stored on the server between the two steps.
- Import needs `add_prospect` and export needs `view_prospect`. Files over
  `OUTREACH_MAX_IMPORT_BYTES` are rejected before they are parsed, and files over
  `OUTREACH_MAX_IMPORT_ROWS` rows are rejected.

## Theme

`outreach_theme_css` writes values from `OUTREACH_THEME` into a `<style>` block. Only validated
values reach it. A strict Content Security Policy needs a nonce or hash for that block.
