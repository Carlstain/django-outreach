# Email templates

An email template is a named subject and message that you can reuse.

- The body is sanitised like any message and may contain variables, tags and buttons.
- Names are unique, ignoring case: "Welcome" and "welcome" are the same name.
- Templates are shared. Every staff member who holds `outreach.view_emailtemplate` sees all of
  them. The author is recorded for information only.
- A mailing keeps its own copy of the subject and message, so editing or deleting a template never
  changes a mailing already sent.

## Managing templates

*Templates* in the sidebar lists the templates with their subject, last change and author, and
has a search. It needs `view_emailtemplate`. Adding, editing and deleting need `add_`, `change_`
and `delete_emailtemplate`.

The edit page shows the template rendered with example values, in a frame cut off from the rest of
the page. Tags are never run in this preview: each one shows its example text, and a button with a
variable or tag link gets a placeholder link.

## Using a template when writing a mail

On the *Write a message* page, choose a template in the *Template* menu and press *Use template*.
The subject and message are replaced, and a note confirms which template is in use. Nothing is
sent and nothing is kept until you press *Preview message*.

## Saving the message as a template

Under the form, *Save this message as a template* stores the current subject and message under the
name you type.

- It needs `add_emailtemplate`.
- If the name is taken, it is refused, unless you tick *Replace the template if the name already
  exists*. That box only appears if you hold `change_emailtemplate`, and replacing keeps the
  original author.
- The message must be valid, as for a preview.
