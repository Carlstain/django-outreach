from functools import partial

from django.db import transaction
from django.dispatch import Signal

prospect_subscribed = Signal()
prospect_unsubscribed = Signal()
mail_sent = Signal()
mail_failed = Signal()


def send_after_commit(signal: Signal, sender: type, **arguments: object) -> None:
    transaction.on_commit(partial(signal.send_robust, sender, **arguments))
