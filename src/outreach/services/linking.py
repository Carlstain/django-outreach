from django.contrib.auth import get_user_model

from outreach.choices import ACTOR_SYSTEM, EventKind
from outreach.models import Prospect, ProspectEvent


class UserLinker:
    def link(self, prospect: Prospect) -> bool:
        """Set ``prospect.user`` to the host user with the same email, without saving.

        Returns ``False`` and links nothing when no user, several users, or a user already
        linked to another prospect match.
        """
        user_model = get_user_model()
        email_field_name = user_model.get_email_field_name()
        matching_users = list(
            get_user_model().objects.filter(**{f"{email_field_name}__iexact": prospect.email})[
                :2
            ]
        )
        if len(matching_users) != 1:
            return False
        user = matching_users[0]
        if Prospect.objects.filter(user=user).exclude(pk=prospect.pk).exists():
            return False
        prospect.user = user
        return True

    def link_and_record(self, prospect: Prospect) -> bool:
        """Link a saved prospect to its user, save the link and record a *linked* event."""
        if not self.link(prospect):
            return False
        prospect.save(update_fields=["user", "updated_at"])
        ProspectEvent.record(prospect, EventKind.LINKED, ACTOR_SYSTEM)
        return True
