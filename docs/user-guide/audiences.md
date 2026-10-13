# Audiences

An audience is a named list of prospects that you mail again and again, such as the visitors of an
event or the partner schools. A prospect can be in several audiences, and an audience can hold any
number of prospects.

- An audience is a list, not a consent. A member who unsubscribed stays in the audience but is
  never mailed, like any other unsubscribed prospect.
- Audiences are shared. Every staff member who holds `outreach.view_audience` sees all of them.
- Deleting an audience never deletes its prospects. Deleting a prospect removes it from its
  audiences.

## Managing audiences

*Audiences* in the sidebar lists them with their description and the number of prospects they
hold, and has a search. It needs `view_audience`. Adding, editing and deleting need `add_`,
`change_` and `delete_audience`. Names are unique, ignoring case.

## Adding and removing prospects

1. In *Prospects*, tick the people, or filter the list and use *Select all* under it.
2. Choose *Add the selected prospects to an audience* (or *Remove the selected prospects from an
   audience*) and press *Go*.
3. Pick the audience and confirm. To start a new audience from the selection, type its name
   in *Or create a new audience* instead of picking one: the audience is created and the selected
   prospects are added to it. Choose one or the other, not both, and a name that already exists
   (ignoring case) is refused.

Prospects that are already members are left as they are, and the message tells you how many were
really added or removed. Both actions need `change_prospect`, even to create an audience this way, and each change is
recorded in the history of the prospect. Removing only offers audiences that already exist.

A prospect's page lists the audiences it belongs to. The list can be filtered by audience.

## Sending to an audience

Filter the prospect list by the audience, use *Select all* under the list, then choose *Send a mail
to the selected prospects*. The mail steps are the same as for any selection, see
{doc}`sending-mail`: unsubscribed and suppressed prospects, the resend cooldown and the send
limit all apply.

The CSV import does not choose an audience. To put an imported file in an audience, import it, then
filter the list for the new prospects and add them.
