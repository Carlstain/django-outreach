from django.urls import reverse

from outreach.choices import EventKind, SkipReason
from outreach.models import ProspectEvent
from tests.base import OutreachTestCase
from tests.factories import MailingFactory, ProspectFactory, create_outreach_staff_user
from tests.routes import (
    outreach_mailing_add_url,
    outreach_mailing_change_url,
    outreach_mailing_changelist_url,
    outreach_prospect_change_url,
    outreach_prospect_changelist_url,
)

ALL_MAILING_PERMISSIONS = [
    "view_prospect",
    "view_mailing",
    "add_mailing",
    "change_mailing",
    "delete_mailing",
]


class MailingAdminTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user(["view_prospect", "view_mailing"]))

    def test_changelist_lists_mailings(self) -> None:
        mailing = MailingFactory()

        response = self.client.get(outreach_mailing_changelist_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cl"].result_list), [mailing])
        self.assertContains(response, mailing.subject)

    def test_view_permission_is_required(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))
        mailing = MailingFactory()

        list_response = self.client.get(outreach_mailing_changelist_url())
        detail_response = self.client.get(outreach_mailing_change_url(mailing.pk))

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(detail_response.status_code, 403)

    def test_adding_a_mailing_is_refused_even_with_the_add_permission(self) -> None:
        self.client.force_login(create_outreach_staff_user(ALL_MAILING_PERMISSIONS))

        response = self.client.get(outreach_mailing_add_url())

        self.assertEqual(response.status_code, 403)

    def test_changing_a_mailing_is_refused_even_with_the_change_permission(self) -> None:
        self.client.force_login(create_outreach_staff_user(ALL_MAILING_PERMISSIONS))
        mailing = MailingFactory(subject="Original subject")

        response = self.client.post(
            outreach_mailing_change_url(mailing.pk), {"subject": "Edited", "sender": "x"}
        )

        self.assertEqual(response.status_code, 403)
        mailing.refresh_from_db()
        self.assertEqual(mailing.subject, "Original subject")

    def test_detail_shows_the_stored_body_and_the_recipients(self) -> None:
        mailing = MailingFactory(body_html="<p>Stored body text</p>")
        sent_to = ProspectFactory(first_name="Alice", last_name="Martin")
        failed_for = ProspectFactory(first_name="Bruno", last_name="Petit")
        ProspectEvent.record(
            sent_to, EventKind.MAILED, "staff", mailing.subject, mailing=mailing
        )
        ProspectEvent.record(
            failed_for, EventKind.MAIL_FAILED, "staff", "refused", mailing=mailing
        )

        response = self.client.get(outreach_mailing_change_url(mailing.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stored body text")
        recipient_prospects = {event.prospect for event in response.context["recipients"]}
        self.assertEqual(recipient_prospects, {sent_to, failed_for})
        self.assertContains(response, "Alice Martin")
        self.assertContains(response, "Bruno Petit")

    def test_detail_exposes_skipped_counts_per_reason(self) -> None:
        mailing = MailingFactory(
            skipped_count=2,
            skipped_reasons={SkipReason.COOLDOWN.value: 1, SkipReason.UNSUBSCRIBED.value: 1},
        )

        response = self.client.get(outreach_mailing_change_url(mailing.pk))

        self.assertEqual(
            response.context["skipped_reasons"],
            {SkipReason.COOLDOWN.value: 1, SkipReason.UNSUBSCRIBED.value: 1},
        )

    def test_sidebar_count_reflects_the_number_of_mailings(self) -> None:
        MailingFactory.create_batch(3)

        response = self.client.get(outreach_mailing_changelist_url())

        self.assertEqual(response.context["counts"]["mailings"], 3)

    def test_hostile_stored_body_is_escaped_inside_the_preview_frame(self) -> None:
        mailing = MailingFactory(
            body_html="<script>alert(1)</script><img src=x onerror=alert(1)>"
        )

        response = self.client.get(outreach_mailing_change_url(mailing.pk))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "<img src=x")
        self.assertNotContains(response, "onerror=alert(1)>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertContains(response, "&lt;img src=x onerror=alert(1)&gt;")

    def test_nav_links_to_mailings_are_shown_with_the_view_permission(self) -> None:
        mailings_href = f'href="{outreach_mailing_changelist_url()}"'

        for page_url in (reverse("outreach_admin:index"), outreach_prospect_changelist_url()):
            with self.subTest(page_url=page_url):
                response = self.client.get(page_url)

                self.assertContains(response, mailings_href, count=2)

    def test_nav_links_to_mailings_are_hidden_without_the_view_permission(self) -> None:
        self.client.force_login(create_outreach_staff_user())
        mailings_href = f'href="{outreach_mailing_changelist_url()}"'

        for page_url in (reverse("outreach_admin:index"), outreach_prospect_changelist_url()):
            with self.subTest(page_url=page_url):
                response = self.client.get(page_url)

                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, mailings_href)

    def test_timeline_links_to_the_mailing_with_the_view_permission(self) -> None:
        mailing = MailingFactory(subject="Autumn news")
        prospect = ProspectFactory()
        ProspectEvent.record(
            prospect, EventKind.MAILED, "staff", mailing.subject, mailing=mailing
        )

        response = self.client.get(outreach_prospect_change_url(prospect.pk))

        self.assertContains(
            response,
            f'<a href="{outreach_mailing_change_url(mailing.pk)}">Autumn news</a>',
            html=True,
        )

    def test_timeline_shows_the_subject_as_plain_text_without_the_view_permission(
        self,
    ) -> None:
        self.client.force_login(create_outreach_staff_user())
        mailing = MailingFactory(subject="Autumn news")
        prospect = ProspectFactory()
        ProspectEvent.record(
            prospect, EventKind.MAILED, "staff", mailing.subject, mailing=mailing
        )

        response = self.client.get(outreach_prospect_change_url(prospect.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Autumn news")
        self.assertNotContains(response, outreach_mailing_change_url(mailing.pk))
