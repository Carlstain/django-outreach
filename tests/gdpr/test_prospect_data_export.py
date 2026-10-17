import json
from uuid import uuid4

from outreach.choices import DeliveryStatus, EventKind
from outreach.models import MailingDelivery, ProspectEvent
from outreach.services.prospect_export import ProspectDataExporter
from tests.base import OutreachTestCase
from tests.factories import (
    AudienceFactory,
    MailingFactory,
    ProspectFactory,
    UserFactory,
    create_outreach_staff_user,
)
from tests.routes import outreach_prospect_change_url, outreach_prospect_export_data_url


class ProspectDataExportTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))
        self.user = UserFactory(username="ada")
        self.prospect = ProspectFactory(
            first_name="Ada", last_name="Lovelace", city="London", user=self.user
        )
        audience = AudienceFactory(name="Friends")
        self.prospect.audiences.add(audience)
        mailing = MailingFactory(subject="Autumn news")
        ProspectEvent.record(
            self.prospect, EventKind.MAILED, "staff", "Autumn news", mailing=mailing
        )
        MailingDelivery.objects.create(
            mailing=mailing, prospect=self.prospect, status=DeliveryStatus.SENT, attempts=1
        )
        self.other_prospect = ProspectFactory(first_name="Other")
        ProspectEvent.record(self.other_prospect, EventKind.ADDED, "staff")

    def test_the_export_holds_everything_stored_about_the_prospect(self) -> None:
        data = ProspectDataExporter().export(self.prospect)

        self.assertEqual(data["email"], self.prospect.email)
        self.assertEqual(
            (data["first_name"], data["last_name"], data["city"]),
            ("Ada", "Lovelace", "London"),
        )
        self.assertEqual(data["account"], "ada")
        self.assertEqual(data["audiences"], ["Friends"])
        self.assertEqual(
            [(event["kind"], event["mailing"]) for event in data["events"]],
            [(EventKind.MAILED, "Autumn news")],
        )
        self.assertEqual(
            [(delivery["mailing"], delivery["status"]) for delivery in data["deliveries"]],
            [("Autumn news", DeliveryStatus.SENT)],
        )

    def test_the_export_does_not_include_another_prospect(self) -> None:
        content = json.dumps(ProspectDataExporter().export(self.prospect))

        self.assertNotIn(self.other_prospect.email, content)
        self.assertNotIn("Other", content)

    def test_the_download_is_a_json_attachment(self) -> None:
        response = self.client.get(outreach_prospect_export_data_url(self.prospect.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="prospect-{self.prospect.pk}.json"',
        )
        self.assertEqual(json.loads(response.content)["email"], self.prospect.email)

    def test_the_download_needs_the_view_permission(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_mailing"]))

        response = self.client.get(outreach_prospect_export_data_url(self.prospect.pk))

        self.assertNotEqual(response.status_code, 200)

    def test_an_unknown_prospect_is_a_404(self) -> None:
        response = self.client.get(outreach_prospect_export_data_url(str(uuid4())))

        self.assertEqual(response.status_code, 404)

    def test_the_prospect_page_links_to_the_download(self) -> None:
        response = self.client.get(outreach_prospect_change_url(self.prospect.pk))

        self.assertContains(response, outreach_prospect_export_data_url(self.prospect.pk))
