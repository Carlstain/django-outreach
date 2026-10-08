import factory

from tests.accounts.models import EmailUser


class EmailUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailUser

    email = factory.Sequence(lambda sequence_number: f"email_user_{sequence_number}@test.com")
