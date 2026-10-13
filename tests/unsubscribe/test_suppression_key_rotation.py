from django.test import override_settings

from outreach.choices import ProspectStatus
from outreach.services.unsubscribe import SuppressionList
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory

SUPPRESSED_EMAIL = "gone@test.com"
OLD_SECRET_KEY = "outreach-tests-only-secret-key"
NEW_SECRET_KEY = "outreach-rotated-secret-key"


class SuppressionKeyRotationTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        SuppressionList().add(SUPPRESSED_EMAIL)

    @override_settings(SECRET_KEY=NEW_SECRET_KEY, SECRET_KEY_FALLBACKS=[OLD_SECRET_KEY])
    def test_a_suppressed_address_stays_suppressed_while_the_old_key_is_a_fallback(
        self,
    ) -> None:
        suppression_list = SuppressionList()

        self.assertTrue(suppression_list.contains(SUPPRESSED_EMAIL))
        self.assertEqual(
            suppression_list.filter_suppressed([SUPPRESSED_EMAIL, "other@test.com"]),
            {SUPPRESSED_EMAIL},
        )

    @override_settings(SECRET_KEY=NEW_SECRET_KEY, SECRET_KEY_FALLBACKS=[OLD_SECRET_KEY])
    def test_a_prospect_created_again_after_the_rotation_is_unsubscribed(self) -> None:
        prospect = ProspectFactory(email=SUPPRESSED_EMAIL)

        self.assertEqual(prospect.status, ProspectStatus.UNSUBSCRIBED)

    @override_settings(SECRET_KEY=NEW_SECRET_KEY, SECRET_KEY_FALLBACKS=[])
    def test_the_list_is_lost_when_the_old_key_is_dropped(self) -> None:
        self.assertFalse(SuppressionList().contains(SUPPRESSED_EMAIL))
