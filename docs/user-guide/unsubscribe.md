# Unsubscribing

Every mail ends with a link to stop receiving mail, and carries the `List-Unsubscribe` headers so
that mail apps can offer an *Unsubscribe* button.

## What the recipient sees

1. The link opens a page that shows the address with most of it hidden and asks *Stop receiving
   emails from* the site name. Opening the link changes nothing, because mail scanners follow links.
2. Pressing *Unsubscribe* confirms. The recipient lands on a confirmation page.
3. A mail app's one-click unsubscribe sends the same request without showing a page.

The link works without signing in, has no expiry, and is only valid for that recipient. A forged
link shows a "not found" page. A valid link for a prospect that was deleted since shows the
confirmation page.

## What it does

- The prospect becomes *Unsubscribed* and an *Unsubscribed* event is added to their history.
- The address is added to the suppression list, a permanent do-not-mail list kept as hashes. It
  stays when the prospect is deleted, so adding the same address again creates a prospect that is
  already unsubscribed.
- They are skipped in every later send.

## Unsubscribed is final

No admin action, import or form sets an unsubscribed prospect back. There is no re-subscribe form
on purpose: an address that asked to stop must not be mailed again by a mistake. There is no
supported way back.

Staff can unsubscribe people on their behalf with the *Unsubscribe the selected prospects*
action, for example when someone asks by phone.
