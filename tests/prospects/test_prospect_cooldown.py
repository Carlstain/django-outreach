from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_change_url, outreach_prospect_changelist_url

COOLDOWN_BADGE = ">cooldown</span>"


class ProspectCooldownTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())

    def test_the_list_flags_a_prospect_inside_the_cooldown(self) -> None:
        ProspectFactory(last_mailed_at=timezone.now())

        response = self.client.get(outreach_prospect_changelist_url())

        self.assertContains(response, COOLDOWN_BADGE)

    def test_the_list_does_not_flag_a_prospect_past_the_cooldown(self) -> None:
        ProspectFactory(last_mailed_at=timezone.now() - timedelta(minutes=5))
        ProspectFactory()

        response = self.client.get(outreach_prospect_changelist_url())

        self.assertNotContains(response, COOLDOWN_BADGE)

    @override_settings(OUTREACH_RESEND_COOLDOWN=timedelta(0))
    def test_the_list_flags_nobody_when_the_cooldown_is_off(self) -> None:
        ProspectFactory(last_mailed_at=timezone.now())

        response = self.client.get(outreach_prospect_changelist_url())

        self.assertNotContains(response, COOLDOWN_BADGE)

    def test_the_page_says_when_a_prospect_can_be_mailed_again(self) -> None:
        cooling_down = ProspectFactory(last_mailed_at=timezone.now())
        ready = ProspectFactory()

        cooling_down_response = self.client.get(outreach_prospect_change_url(cooling_down.pk))
        ready_response = self.client.get(outreach_prospect_change_url(ready.pk))

        self.assertContains(ready_response, '<div class="readonly">Now</div>', html=True)
        self.assertContains(cooling_down_response, "Can be mailed again")
        self.assertNotContains(
            cooling_down_response, '<div class="readonly">Now</div>', html=True
        )
