from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import override_settings

from outreach.choices import (
    ACTOR_IMPORT,
    EventKind,
    ImportRowStatus,
    ProspectKind,
    ProspectStatus,
)
from outreach.models import Audience, ProspectEvent
from outreach.services.prospect_csv import ProspectCsvImporter
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, UserFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_import_url, outreach_prospect_process_import_url

EXISTING_HEADER = "email,first_name,last_name,organization,city,country,kind\n"


@override_settings(OUTREACH_LANGUAGE="en")
class ProspectImportDuplicatesTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())
        self.existing = ProspectFactory(
            email="ada@test.com", first_name="Ada", last_name="Lovelace", city="London"
        )

    def upload(self, csv_text: str, update_existing: bool = False) -> HttpResponse:
        import_file = SimpleUploadedFile(
            "prospects.csv", csv_text.encode(), content_type="text/csv"
        )
        fields = {"import_file": import_file}
        if update_existing:
            fields["update_existing"] = "on"
        return self.client.post(outreach_prospect_import_url(), fields)

    def import_csv(self, csv_text: str, update_existing: bool = False) -> HttpResponse:
        preview_response = self.upload(csv_text, update_existing)
        confirm_form = preview_response.context["confirm_form"]
        return self.client.post(outreach_prospect_process_import_url(), confirm_form.initial)

    def statuses(self, csv_text: str, update_existing: bool = False) -> list[ImportRowStatus]:
        preview = ProspectCsvImporter().preview(csv_text, update_existing)
        return [row.status for row in preview.rows]

    def test_an_existing_email_a_repeat_and_a_new_row_are_told_apart(self) -> None:
        csv_text = (
            "email,first_name\n"
            "ada@test.com,Ada\n"
            "grace@test.com,Grace\n"
            "grace@test.com,Gracie\n"
            "ada@test.com,Again\n"
        )

        preview = ProspectCsvImporter().preview(csv_text)

        self.assertEqual(
            [row.status for row in preview.rows],
            [
                ImportRowStatus.SKIPPED,
                ImportRowStatus.NEW,
                ImportRowStatus.REPEATED,
                ImportRowStatus.REPEATED,
            ],
        )
        self.assertEqual(
            (len(preview.new_rows), len(preview.kept_rows), len(preview.repeated_rows)),
            (1, 1, 2),
        )
        self.assertEqual(preview.skipped_count, 3)

    def test_the_preview_page_shows_the_counts_and_the_labels(self) -> None:
        response = self.upload(
            "email,first_name\nada@test.com,Ada\ngrace@test.com,Grace\ngrace@test.com,G\n"
        )

        self.assertContains(
            response, "1 new, 0 to update, 1 kept as they are, 1 repeated in the file."
        )
        self.assertContains(response, "Repeated in the file")

    def test_without_the_update_option_an_existing_prospect_is_never_changed(self) -> None:
        response = self.import_csv("email,first_name,city\nada@test.com,Augusta,Paris\n")

        self.existing.refresh_from_db()
        self.assertEqual((self.existing.first_name, self.existing.city), ("Ada", "London"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertEqual(messages, ["0 prospects imported. 1 row skipped."])

    def test_with_the_update_option_a_filled_cell_that_differs_is_an_update(self) -> None:
        csv_text = f"{EXISTING_HEADER}ada@test.com,Ada,Byron,,London,,\n"

        preview = ProspectCsvImporter().preview(csv_text, update_existing=True)

        row = preview.rows[0]
        self.assertEqual(row.status, ImportRowStatus.UPDATE)
        self.assertEqual(row.changes, {"last_name": ("Lovelace", "Byron")})

    def test_an_identical_row_stays_skipped_in_update_mode(self) -> None:
        csv_text = "email,first_name,last_name,city\nada@test.com,Ada,Lovelace,London\n"

        self.assertEqual(
            self.statuses(csv_text, update_existing=True), [ImportRowStatus.SKIPPED]
        )

    def test_an_empty_cell_and_a_missing_column_change_nothing(self) -> None:
        self.existing.kind = ProspectKind.ORGANIZATION
        self.existing.save()

        self.import_csv("email,first_name,city\nada@test.com,,\n", update_existing=True)

        self.existing.refresh_from_db()
        self.assertEqual(
            (self.existing.first_name, self.existing.city, self.existing.kind),
            ("Ada", "London", ProspectKind.ORGANIZATION),
        )

    def test_applying_an_update_writes_only_the_changed_fields_and_one_edited_event(
        self,
    ) -> None:
        response = self.import_csv(
            "email,first_name,last_name,city\nada@test.com,Augusta,Lovelace,Paris\n",
            update_existing=True,
        )

        self.existing.refresh_from_db()
        self.assertEqual(
            (self.existing.first_name, self.existing.last_name, self.existing.city),
            ("Augusta", "Lovelace", "Paris"),
        )
        event = ProspectEvent.objects.get(prospect=self.existing, kind=EventKind.EDITED)
        self.assertEqual(event.actor, ACTOR_IMPORT)
        self.assertEqual(sorted(event.detail.split(", ")), ["city", "first_name"])
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertEqual(
            messages, ["0 prospects imported. 1 prospect updated. 0 rows skipped."]
        )

    def test_an_update_never_touches_the_email_status_account_mail_date_or_audiences(
        self,
    ) -> None:
        user = UserFactory()
        self.existing.user = user
        self.existing.status = ProspectStatus.UNSUBSCRIBED
        self.existing.audiences.add(Audience.objects.create(name="Friends"))
        self.existing.save()
        previous_mailed_at = self.existing.last_mailed_at

        self.import_csv("email,first_name\nada@test.com,Augusta\n", update_existing=True)

        self.existing.refresh_from_db()
        self.assertEqual(self.existing.first_name, "Augusta")
        self.assertEqual(self.existing.email, "ada@test.com")
        self.assertEqual(self.existing.status, ProspectStatus.UNSUBSCRIBED)
        self.assertEqual(self.existing.user, user)
        self.assertEqual(self.existing.last_mailed_at, previous_mailed_at)
        self.assertEqual(
            list(self.existing.audiences.values_list("name", flat=True)), ["Friends"]
        )

    def test_new_rows_and_updates_are_applied_together_with_both_counts(self) -> None:
        response = self.import_csv(
            "email,first_name\nada@test.com,Augusta\ngrace@test.com,Grace\nada@test.com,Dup\n",
            update_existing=True,
        )

        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertEqual(messages, ["1 prospect imported. 1 prospect updated. 1 row skipped."])

    def test_an_invalid_value_in_an_update_row_blocks_the_whole_import(self) -> None:
        response = self.upload(
            "email,first_name,kind\nada@test.com,Augusta,wizard\ngrace@test.com,Grace,\n",
            update_existing=True,
        )

        self.assertNotIn("confirm_form", response.context)
        self.assertEqual(len(response.context["preview"].invalid_rows), 1)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.first_name, "Ada")

    def test_an_update_only_preview_offers_the_confirmation(self) -> None:
        response = self.upload(
            "email,first_name\nada@test.com,Augusta\n", update_existing=True
        )

        self.assertIn("confirm_form", response.context)
        self.assertContains(response, "Confirm import")
        self.assertContains(response, "first_name: Ada")

    def test_the_confirm_step_re_reads_the_choice_and_revalidates_the_text(self) -> None:
        preview_response = self.upload(
            "email,first_name\nada@test.com,Augusta\n", update_existing=True
        )
        initial = dict(preview_response.context["confirm_form"].initial)
        self.assertTrue(initial["update_existing"])
        initial["csv_text"] = "email,first_name,kind\nada@test.com,Augusta,wizard\n"

        response = self.client.post(outreach_prospect_process_import_url(), initial)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["preview"].invalid_rows), 1)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.first_name, "Ada")

    def test_the_update_option_needs_the_change_permission(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect", "add_prospect"]))

        page = self.client.get(outreach_prospect_import_url())
        forged = self.client.post(
            outreach_prospect_process_import_url(),
            {
                "csv_text": "email,first_name\nada@test.com,Augusta\n",
                "file_name": "prospects.csv",
                "update_existing": "True",
            },
        )

        self.assertNotContains(page, "Update the prospects that already exist")
        self.assertEqual(forged.status_code, 403)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.first_name, "Ada")

    def test_the_option_is_offered_with_the_change_permission(self) -> None:
        page = self.client.get(outreach_prospect_import_url())

        self.assertContains(page, "Update the prospects that already exist")

    def test_many_emails_are_looked_up_in_chunks(self) -> None:
        ProspectCsvImporter.EMAIL_LOOKUP_CHUNK = 2
        self.addCleanup(setattr, ProspectCsvImporter, "EMAIL_LOOKUP_CHUNK", 500)
        ProspectFactory(email="grace@test.com")
        ProspectFactory(email="alan@test.com")
        csv_text = "email\nada@test.com\ngrace@test.com\nalan@test.com\nnew@test.com\n"

        statuses = self.statuses(csv_text)

        self.assertEqual(
            statuses,
            [ImportRowStatus.SKIPPED] * 3 + [ImportRowStatus.NEW],
        )

    def test_an_update_that_became_a_no_op_before_the_confirmation_is_not_counted(
        self,
    ) -> None:
        preview = ProspectCsvImporter().preview(
            "email,first_name\nada@test.com,Augusta\n", update_existing=True
        )
        self.existing.first_name = "Augusta"
        self.existing.save()

        result = ProspectCsvImporter().apply(preview, "prospects.csv")

        self.assertEqual((result.created, result.updated), (0, 0))
        self.assertFalse(ProspectEvent.objects.filter(kind=EventKind.EDITED).exists())
