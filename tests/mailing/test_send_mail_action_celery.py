from unittest.mock import patch

from django.contrib.messages import SUCCESS, get_messages
from django.core import mail

from outreach.models import Mailing
from outreach.tasks import deliver_mail
from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url


class SendMailActionCeleryTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())

    def test_the_send_step_reports_the_queued_mails(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        with (
            patch.object(deliver_mail, "apply_async") as apply_async,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(
                outreach_prospect_changelist_url(),
                {
                    "action": "send_mail",
                    "_selected_action": [str(prospect.pk) for prospect in prospects],
                    "is_newsletter": "on",
                    "step": "send",
                    "subject": "Welcome",
                    "body": "Hello,\n\nJoin us.",
                },
            )

        self.assertEqual(response.status_code, 302)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual([message.message for message in messages], ["2 queued, 0 skipped."])
        self.assertEqual(messages[0].level, SUCCESS)
        self.assertEqual(apply_async.call_count, 2)
        self.assertEqual(Mailing.objects.get().deliveries.count(), 2)
        self.assertEqual(len(mail.outbox), 0)
