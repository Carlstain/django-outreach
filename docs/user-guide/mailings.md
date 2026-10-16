# Mailings

A mailing is the record of one send that had at least one recipient. *Mailings* in the sidebar
needs `outreach.view_mailing`.

## The list

![The mailing list](../_static/screenshots/mailings.png)

Each row shows the subject, who sent it, the date, and the counts of sent, failed and skipped
recipients. You can search the subject and the sender.

## The detail page

![A mailing](../_static/screenshots/mailing-detail.png)

Open a mailing to see:

- The subject and message exactly as they were sent (variables not replaced), in a frame cut off
  from the rest of the page.
- The recipients of the mailing with their status: pending, sent or failed. A failed recipient
  shows a short message, not the mail server's error. A prospect that was deleted since no longer
  appears. Mailings sent before deliveries were recorded list the recipients from the events of
  the mailing instead, with no status of their own.
- The number of skipped recipients per reason: unsubscribed, suppressed, contacted recently, over
  the send limit, not a member.
- Whether it was a newsletter or a notice, and its header text.

Skipped people are stored as counts, never as names. A mailing outlives the prospects it was sent
to, and it must not keep data about someone who asked for erasure.

## Retrying failed recipients

A failed recipient has a **Retry** button, and **Retry all failed** sends again to every one of
them. Both need `outreach.change_prospect`, the permission of the send action, and
`OUTREACH_BASE_URL`.

A retry claims the prospect again and goes through the same checks as a send: someone who
unsubscribed or was suppressed since the failure is skipped, and a notice still needs a member.
The resend cooldown is not applied, since you asked for the retry. A retry is capped like a send,
at `OUTREACH_MAX_RECIPIENTS_PER_SEND` in synchronous mode and
`OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND` with Celery, and the rest stay failed. With Celery the
deliveries are queued and show as pending until a worker sends them.

## What you can not do

Mailings can not be added or changed, only read and deleted. Deleting needs
`outreach.delete_mailing` and removes the log entry, not the mails.
