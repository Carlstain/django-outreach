import logging
from functools import partial
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction

from outreach.conf import outreach_settings
from outreach.services.user_loading import UserProspectSyncer

logger = logging.getLogger("outreach")


def sync_new_user(
    sender: Any, instance: Any, created: bool, raw: bool = False, **kwargs: Any
) -> None:
    """Sync a newly created host user with the prospects, after the transaction commits."""
    if raw or not created or outreach_settings.sync_users is None:
        return
    transaction.on_commit(partial(sync_user_safely, instance.pk))


def sync_user_safely(user_pk: Any) -> None:
    """Run the sync and log a failure: the sign-up of the host must never break."""
    mode = outreach_settings.sync_users
    if mode is None:
        return
    try:
        user = get_user_model()._default_manager.get(pk=user_pk)
        UserProspectSyncer(mode).sync(user)
    except Exception:
        logger.exception("Syncing user %s with the prospects failed.", user_pk)
