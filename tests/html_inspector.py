from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class Element:
    tag: str
    attributes: dict[str, str | None]
    form_index: int | None
    text: str = ""


class PageInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[Element] = []
        self.open_form_index: int | None = None
        self.form_count = 0
        self.open_anchor: Element | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "form":
            self.open_form_index = self.form_count
            self.form_count += 1
        element = Element(tag, dict(attrs), self.open_form_index)
        self.elements.append(element)
        if tag in ("a", "button"):
            self.open_anchor = element

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.open_form_index = None
        if tag in ("a", "button"):
            self.open_anchor = None

    def handle_data(self, data: str) -> None:
        if self.open_anchor is not None:
            self.open_anchor.text += data

    def find(self, tag: str, **attributes: str) -> list[Element]:
        return [
            element
            for element in self.elements
            if element.tag == tag
            and all(element.attributes.get(key) == value for key, value in attributes.items())
        ]

    def submit_buttons_in_form(self, form_index: int | None) -> list[Element]:
        return [
            element
            for element in self.elements
            if element.tag == "button"
            and element.form_index == form_index
            and element.attributes.get("type", "submit") == "submit"
        ]


def inspect_page(content: bytes) -> PageInspector:
    inspector = PageInspector()
    inspector.feed(content.decode())
    return inspector
