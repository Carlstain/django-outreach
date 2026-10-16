from django.test import override_settings

from outreach.models import Prospect
from outreach.services.unsubscribe import SuppressionList
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url

ERASE_ACTION = "erase_selected"


@override_settings(OUTREACH_LANGUAGE="en")
class ProspectEraseActionTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())
        self.first_prospect = ProspectFactory()
        self.second_prospect = ProspectFactory()
        self.kept_prospect = ProspectFactory()

    def post_action(self, prospects: list[Prospect], **extra_fields: str):
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": ERASE_ACTION,
                "_selected_action": [str(prospect.pk) for prospect in prospects],
                **extra_fields,
            },
            follow=True,
        )

    def test_the_first_step_asks_for_confirmation_and_deletes_nothing(self) -> None:
        response = self.post_action([self.first_prospect, self.second_prospect])

        self.assertContains(response, "This can not be undone.")
        self.assertContains(response, "2 prospects selected.")
        self.assertEqual(Prospect.objects.count(), 3)

    def test_confirming_erases_and_suppresses_only_the_selected_prospects(self) -> None:
        response = self.post_action([self.first_prospect, self.second_prospect], apply="1")

        self.assertContains(response, "2 prospects erased and suppressed.")
        self.assertEqual(list(Prospect.objects.all()), [self.kept_prospect])
        self.assertTrue(SuppressionList().contains(self.first_prospect.email))
        self.assertFalse(SuppressionList().contains(self.kept_prospect.email))

    def test_one_prospect_gets_the_singular_message(self) -> None:
        response = self.post_action([self.first_prospect], apply="1")

        self.assertContains(response, "1 prospect erased and suppressed.")

    def test_without_the_delete_permission_nothing_is_erased(self) -> None:
        self.client.force_login(
            create_outreach_staff_user(["view_prospect", "change_prospect"])
        )

        self.post_action([self.first_prospect], apply="1")

        self.assertEqual(Prospect.objects.count(), 3)
        self.assertFalse(SuppressionList().contains(self.first_prospect.email))
