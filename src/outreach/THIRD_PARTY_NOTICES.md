# Third party notices

This file ships inside the package, at `outreach/THIRD_PARTY_NOTICES.md`.

django-outreach ships the following third party software unmodified, under
`src/outreach/static/outreach/vendor/trix/`.

## Trix 2.1.19

- Files: `trix-2.1.19.umd.min.js`, `trix-2.1.19.css`, `trix-2.1.19.LICENSE`
- Source: https://github.com/basecamp/trix, npm package `trix`
- Licence: MIT

Header comment of `trix-2.1.19.umd.min.js`:

```
Trix 2.1.19
Copyright © 2026 37signals, LLC
```

Licence text, as shipped in `trix-2.1.19.LICENSE`:

```
Copyright (c) 37signals, LLC

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## DOMPurify 3.4.2, bundled inside the Trix build

`trix-2.1.19.umd.min.js` contains a copy of DOMPurify. Its licence header, as it
appears in the file:

```
/*! @license DOMPurify 3.4.2 | (c) Cure53 and other contributors | Released under the Apache license 2.0 and Mozilla Public License 2.0 | github.com/cure53/DOMPurify/blob/3.4.2/LICENSE */
```

The full licence texts are not included in the Trix build. They are published at
https://github.com/cure53/DOMPurify/blob/3.4.2/LICENSE.
