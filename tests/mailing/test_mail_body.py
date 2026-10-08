from outreach.services.body import MailBodySanitizer
from tests.base import OutreachTestCase


class MailBodyTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.sanitizer = MailBodySanitizer()

    def test_script_tags_and_their_content_are_removed(self) -> None:
        cleaned = self.sanitizer.clean("<p>Hello</p><script>alert(1)</script>")

        self.assertEqual(cleaned, "<p>Hello</p>")

    def test_event_handler_attributes_are_removed(self) -> None:
        cleaned = self.sanitizer.clean('<p onclick="steal()" onmouseover="x()">Hi</p>')

        self.assertEqual(cleaned, "<p>Hi</p>")

    def test_javascript_links_lose_their_href(self) -> None:
        cleaned = self.sanitizer.clean('<a href="javascript:alert(1)">Click</a>')

        self.assertEqual(cleaned, '<a rel="noopener noreferrer">Click</a>')

    def test_style_and_class_attributes_are_removed(self) -> None:
        cleaned = self.sanitizer.clean('<p style="color:red" class="big">Hi</p>')

        self.assertEqual(cleaned, "<p>Hi</p>")

    def test_unknown_tags_are_stripped_but_their_text_is_kept(self) -> None:
        cleaned = self.sanitizer.clean("<marquee>Scrolling</marquee><img src='x.png'>")

        self.assertEqual(cleaned, "Scrolling")

    def test_allowed_tags_are_kept(self) -> None:
        html = (
            "<h1>Title</h1><p>One <strong>bold</strong> <em>italic</em> <del>gone</del><br></p>"
            "<ul><li>a</li></ul><ol><li>b</li></ol><blockquote>q</blockquote>"
            '<div>box</div><a href="https://example.org/page">link</a>'
        )

        cleaned = self.sanitizer.clean(html)

        for tag in ("h1", "p", "strong", "em", "del", "br", "ul", "ol", "li"):
            self.assertIn(f"<{tag}", cleaned)
        for tag in ("blockquote", "div"):
            self.assertIn(f"<{tag}", cleaned)
        self.assertIn('href="https://example.org/page"', cleaned)

    def test_mailto_links_are_kept(self) -> None:
        cleaned = self.sanitizer.clean('<a href="mailto:hello@example.org">Write</a>')

        self.assertIn('href="mailto:hello@example.org"', cleaned)

    def test_unsubscribe_placeholder_survives_as_a_link_target(self) -> None:
        cleaned = self.sanitizer.clean('<p><a href="{{ unsubscribe_url }}">Leave</a></p>')

        self.assertIn('href="{{ unsubscribe_url }}"', cleaned)

    def test_plain_text_keeps_its_paragraphs(self) -> None:
        cleaned = self.sanitizer.clean("First paragraph\n\nSecond paragraph")

        self.assertIn("<p>First paragraph</p>", cleaned)
        self.assertIn("<p>Second paragraph</p>", cleaned)

    def test_plain_text_line_breaks_become_br(self) -> None:
        cleaned = self.sanitizer.clean("Line one\nLine two")

        self.assertIn("<br", cleaned)

    def test_paragraphs_become_text_separated_by_a_blank_line(self) -> None:
        text = self.sanitizer.to_text("<p>First</p><p>Second</p>")

        self.assertEqual(text.strip(), "First\n\nSecond")

    def test_br_becomes_a_newline(self) -> None:
        text = self.sanitizer.to_text("<p>One<br>Two</p>")

        self.assertEqual(text.strip(), "One\nTwo")

    def test_list_items_become_dashed_lines(self) -> None:
        text = self.sanitizer.to_text("<ul><li>Apples</li><li>Pears</li></ul>")

        self.assertIn("- Apples\n- Pears", text)

    def test_heading_is_uppercase_on_its_own_line(self) -> None:
        text = self.sanitizer.to_text("<h1>Big news</h1><p>Body</p>")

        self.assertEqual(text.strip(), "BIG NEWS\n\nBody")

    def test_blockquote_lines_are_prefixed(self) -> None:
        text = self.sanitizer.to_text("<blockquote>Wise words</blockquote>")

        self.assertIn("> Wise words", text)

    def test_link_text_is_followed_by_its_url(self) -> None:
        text = self.sanitizer.to_text('<p><a href="https://example.org/x">Our site</a></p>')

        self.assertIn("Our site (https://example.org/x)", text)

    def test_link_whose_text_is_the_url_is_not_repeated(self) -> None:
        text = self.sanitizer.to_text(
            '<p><a href="https://example.org/x">https://example.org/x</a></p>'
        )

        self.assertEqual(text.strip(), "https://example.org/x")

    def test_nested_lists_keep_their_structure(self) -> None:
        text = self.sanitizer.to_text("<ul><li>a<ul><li>b</li></ul>c</li><li>d</li></ul>")

        self.assertEqual(text, "- a\n  - b\n  c\n- d")

    def test_mailto_link_whose_text_is_the_address_is_not_repeated(self) -> None:
        text = self.sanitizer.to_text(
            '<p><a href="mailto:team@example.org">team@example.org</a></p>'
        )

        self.assertEqual(text, "team@example.org")

    def test_real_editor_output_with_two_lists_and_a_trailing_line(self) -> None:
        html = (
            "<ul><li>A bulleted point</li><li>A second point with a nested list below"
            "<ul><li>A nested point</li></ul></li></ul>"
            "<ol><li>First step</li><li>Second step</li></ol>"
            '<div>Visit <a href="https://www.example.test">our website</a></div>'
        )

        self.assertEqual(
            self.sanitizer.to_text(html),
            "- A bulleted point\n"
            "- A second point with a nested list below\n"
            "  - A nested point\n"
            "\n"
            "1. First step\n"
            "2. Second step\n"
            "\n"
            "Visit our website (https://www.example.test)",
        )

    def test_ordered_list_is_numbered(self) -> None:
        text = self.sanitizer.to_text("<ol><li>One</li><li>Two</li><li>Three</li></ol>")

        self.assertEqual(text, "1. One\n2. Two\n3. Three")

    def test_nested_ordered_list_restarts_at_one_and_is_indented(self) -> None:
        text = self.sanitizer.to_text(
            "<ol><li>One<ol><li>Inner a</li><li>Inner b</li></ol></li><li>Two</li></ol>"
        )

        self.assertEqual(text, "1. One\n  1. Inner a\n  2. Inner b\n2. Two")

    def test_ordered_list_inside_a_bullet_list_keeps_its_own_markers(self) -> None:
        text = self.sanitizer.to_text(
            "<ul><li>Bullet<ol><li>First</li><li>Second</li></ol></li><li>Next</li></ul>"
        )

        self.assertEqual(text, "- Bullet\n  1. First\n  2. Second\n- Next")

    def test_consecutive_lists_are_separated_by_a_blank_line(self) -> None:
        text = self.sanitizer.to_text("<ul><li>A</li></ul><ul><li>B</li></ul>")

        self.assertEqual(text, "- A\n\n- B")
