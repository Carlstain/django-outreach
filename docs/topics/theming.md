# Theming

`OUTREACH_THEME` changes the colours and the font of the admin site, the unsubscribe pages and
the mails. It accepts any subset of these keys. The values below are the defaults.

```python
OUTREACH_THEME = {
    "brand": "#2a2124",
    "accent": "#7a3b69",
    "on_accent": "#ffffff",
    "text": "#2a2124",
    "muted": "#75676b",
    "background": "#f8f4f4",
    "surface": "#fffcfc",
    "border": "#e8dedf",
    "avatar": None,  # derived from brand and surface when None
    "font_family": None,  # system font stack when None
    "dark": {  # same colour keys, each falls back to the dark defaults
        "brand": "#f0e7ea",
        "accent": "#d79bc6",
        "on_accent": "#240c1d",
        "text": "#f0e7ea",
        "muted": "#aa9aa1",
        "background": "#181316",
        "surface": "#231c20",
        "border": "#3b2f35",
    },
}
```

The defaults live in `outreach.theme` (`DEFAULT_LIGHT` and `DEFAULT_DARK`), which is the source to
trust if this page and the code ever disagree.

## Values

- Colours may be hex with 3 to 8 digits, `rgb()`, `rgba()`, `hsl()`, `hsla()` or a CSS colour
  name.
- `font_family` is a CSS font stack. No font is shipped: set `font_family` and load the font in
  your own CSS. Only sans-serif faces are used by default.
- The theme is written as CSS variables in one `<style>` block by `{% outreach_theme_css %}`
  (library `outreach_tags`), placed after the stylesheet. The dark values apply under
  `prefers-color-scheme: dark`.
- Email clients can not use CSS variables or dark mode, so mails always use the light values.

## Errors and fallbacks

{class}`~outreach.theme.OutreachTheme` is strict at check time and forgiving at runtime.

- An unknown key, an invalid value or a non-dict value is an error reported by the system check
  `outreach.E001`.
- At runtime a bad value never breaks a page: that key falls back to its default (the dark
  palette falls back to the dark defaults) and one warning per distinct problem is logged on the
  `outreach` logger. A typo in a setting must not take down the public unsubscribe page or a send.

## Logo

Set `OUTREACH_LOGO_STATIC_PATH` to the static path of a logo, and `OUTREACH_LOGO_DARK_STATIC_PATH`
for dark mode. Without a logo the site name is shown as text. No logo is shipped.
With `OUTREACH_EMAIL_LOGO_IN_HEADER` the logo is centered at the top of mails, and the site name
text is left out unless a template or a mail sets a header text.

## Overriding templates

To change markup, override a template by path (`outreach/base.html`,
`outreach/email/message.html`, `outreach/admin/index.html`, and so on, see
{doc}`../reference/templates`). Put it in a directory listed in `TEMPLATES["DIRS"]`, or in an app
listed before `outreach` in `INSTALLED_APPS`.

A strict Content Security Policy needs a nonce or hash for the theme `<style>` block.
