import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from outreach.models import Audience, EmailTemplate, Mailing, Prospect


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda sequence_number: f"user_{sequence_number}")
    email = factory.LazyAttribute(lambda instance: f"{instance.username}@test.com")


class ProspectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Prospect

    email = factory.Sequence(lambda sequence_number: f"prospect_{sequence_number}@test.com")
    first_name = "Ada"
    last_name = "Lovelace"


class MailingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Mailing

    subject = factory.Sequence(lambda sequence_number: f"Mailing subject {sequence_number}")
    body_html = "<p>Hello from the mailing</p>"
    sender = "staff"


class AudienceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Audience

    name = factory.Sequence(lambda sequence_number: f"Audience {sequence_number}")


class EmailTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailTemplate

    name = factory.Sequence(lambda sequence_number: f"Template {sequence_number}")
    subject = factory.Sequence(lambda sequence_number: f"Template subject {sequence_number}")
    body_html = "<p>Hello from the template</p>"


OUTREACH_PROSPECT_PERMISSIONS = [
    "view_prospect",
    "add_prospect",
    "change_prospect",
    "delete_prospect",
]

OUTREACH_AUDIENCE_PERMISSIONS = [
    "view_audience",
    "add_audience",
    "change_audience",
    "delete_audience",
]

OUTREACH_TEMPLATE_PERMISSIONS = [
    "view_emailtemplate",
    "add_emailtemplate",
    "change_emailtemplate",
    "delete_emailtemplate",
]


def create_outreach_staff_user(
    permission_codenames: list[str] | None = None,
    user_factory: type[factory.django.DjangoModelFactory] | None = None,
):
    if permission_codenames is None:
        permission_codenames = OUTREACH_PROSPECT_PERMISSIONS
    if user_factory is None:
        user_factory = UserFactory
    staff_user = user_factory(is_staff=True)
    permissions = Permission.objects.filter(
        content_type__app_label="outreach", codename__in=permission_codenames
    )
    staff_user.user_permissions.set(permissions)
    return staff_user
