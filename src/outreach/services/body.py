import re
from html.parser import HTMLParser

import nh3
from django.utils.html import linebreaks

ALLOWED_TAGS = {
    "p",
    "div",
    "br",
    "strong",
    "em",
    "del",
    "h1",
    "ul",
    "ol",
    "li",
    "blockquote",
    "a",
}
ALLOWED_ATTRIBUTES = {"a": {"href"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}
TAG_PATTERN = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
BLOCK_TAGS = {"p", "div", "h1", "blockquote"}
LIST_TAGS = {"ul", "ol"}
LIST_INDENT = "  "


class MailBodySanitizer:
    """Sanitises mail bodies with nh3 and converts them to plain text."""

    def clean(self, html: str) -> str:
        """Keep only the editor's tags, ``href`` on links, and http, https or mailto URLs.

        A body with no HTML tag is treated as plain text and wrapped in paragraphs first.
        """
        if not TAG_PATTERN.search(html):
            html = linebreaks(html)
        return nh3.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            url_schemes=ALLOWED_URL_SCHEMES,
            strip_comments=True,
        )

    def to_text(self, html: str) -> str:
        converter = HtmlToTextConverter()
        converter.feed(html)
        converter.close()
        return converter.result()


class HtmlToTextConverter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, int | None]] = []
        self.current = ""
        self.link_url: str | None = None
        self.link_text = ""
        self.heading = False
        self.quote_depth = 0
        self.list_stack: list[dict[str, int | str]] = []
        self.list_group = 0
        self.bullet_marker: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.current += "\n"
        elif tag == "a":
            self.link_url = dict(attrs).get("href") or ""
            self.link_text = ""
        elif tag in LIST_TAGS:
            self.flush()
            if not self.list_stack:
                self.list_group += 1
            self.list_stack.append({"tag": tag, "count": 0})
        elif tag == "li":
            self.flush()
            self.bullet_marker = self.next_marker()
        elif tag == "h1":
            self.flush()
            self.heading = True
        elif tag == "blockquote":
            self.flush()
            self.quote_depth += 1
        elif tag in BLOCK_TAGS:
            self.flush()

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.link_url is not None:
            text = self.link_text.strip()
            if self.link_url and text != self.link_url.removeprefix("mailto:"):
                self.current += f" ({self.link_url})"
            self.link_url = None
        elif tag in LIST_TAGS:
            self.flush()
            if self.list_stack:
                self.list_stack.pop()
        elif tag == "li":
            self.flush()
            self.bullet_marker = None
        elif tag == "h1":
            self.flush()
            self.heading = False
        elif tag == "blockquote":
            self.flush()
            self.quote_depth = max(0, self.quote_depth - 1)
        elif tag in BLOCK_TAGS:
            self.flush()

    def next_marker(self) -> str:
        if not self.list_stack:
            return "- "
        current_list = self.list_stack[-1]
        if current_list["tag"] == "ol":
            current_list["count"] += 1
            return f"{current_list['count']}. "
        return "- "

    def handle_data(self, data: str) -> None:
        text = re.sub(r"[ \t\r\f\v]*\n[ \t\r\f\v]*|[ \t\r\f\v]+", " ", data)
        self.current += text
        if self.link_url is not None:
            self.link_text += text

    def flush(self) -> None:
        text = self.current.strip()
        self.current = ""
        if not text:
            return
        if self.heading:
            text = text.upper()
        prefix = "> " * self.quote_depth
        lines = [f"{prefix}{line.strip()}" for line in text.split("\n")]
        group = None
        if self.list_stack:
            group = self.list_group
            depth = len(self.list_stack)
            continuation_indent = LIST_INDENT * depth
            if self.bullet_marker is not None:
                marker_indent = LIST_INDENT * (depth - 1)
                lines[0] = f"{marker_indent}{self.bullet_marker}{lines[0]}"
                lines[1:] = [f"{continuation_indent}{line}" for line in lines[1:]]
                self.bullet_marker = None
            else:
                lines = [f"{continuation_indent}{line}" for line in lines]
        self.blocks.append(("\n".join(lines), group))

    def result(self) -> str:
        self.flush()
        text = ""
        previous_group: int | None = None
        for block_text, group in self.blocks:
            if text:
                is_same_list = group is not None and group == previous_group
                text += "\n" if is_same_list else "\n\n"
            text += block_text
            previous_group = group
        return text
