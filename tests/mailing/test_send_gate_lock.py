from unittest import skipUnless

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from outreach.services.send_gate import SendGate
from tests.base import CeleryMailTestCase
from tests.factories import MailingDeliveryFactory


@skipUnless(connection.vendor == "postgresql", "Advisory locks exist on PostgreSQL only.")
@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=2)
class SendGateLockTests(CeleryMailTestCase):
    def test_release_takes_a_lock_that_does_not_depend_on_the_waiting_rows(self) -> None:
        MailingDeliveryFactory()

        with CaptureQueriesContext(connection) as queries:
            SendGate.release_due()

        statements = [query["sql"] for query in queries.captured_queries]
        self.assertTrue(any("pg_advisory_xact_lock" in statement for statement in statements))
