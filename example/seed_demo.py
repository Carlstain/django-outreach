"""Demo data for the example project. Run: python example/manage.py shell < example/seed_demo.py

Creates a superuser demo / demo (for local demonstration only, never reuse it),
a few users, ten prospects at example.org and two mailings. Safe to run twice.
"""

import os
from datetime import timedelta

import django
from django.contrib.auth import get_user_model
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from outreach.choices import (  # noqa: E402
    ACTOR_IMPORT,
    ACTOR_RECIPIENT,
    ACTOR_SYSTEM,
    EventKind,
    ProspectKind,
    ProspectStatus,
)
from outreach.models import Mailing, Prospect, ProspectEvent  # noqa: E402
from outreach.services.templates import EmailTemplates  # noqa: E402
from outreach.services.unsubscribe import ProspectUnsubscriber, UnsubscribeTokens  # noqa: E402

User = get_user_model()

USERS = [
    ("alice", "Alice", "Carter", "alice.carter@example.org"),
    ("ben", "Ben", "Hughes", "ben.hughes@example.org"),
    ("chloe", "Chloe", "Reed", "chloe.reed@example.org"),
]

PROSPECTS = [
    ("Alice", "Carter", "", "alice.carter@example.org", "Austin", "United States"),
    ("Ben", "Hughes", "", "ben.hughes@example.org", "Denver", "United States"),
    ("Chloe", "Reed", "", "chloe.reed@example.org", "", ""),
    ("David", "Walker", "", "david.walker@example.org", "Boston", "United States"),
    ("Emma", "Stone", "", "emma.stone@example.org", "Seattle", "United States"),
    ("", "", "Acme Legal LLP", "hello@acmelegal.example.org", "Chicago", "United States"),
    ("", "", "Northwind Traders", "office@northwind.example.org", "Portland", "United States"),
    (
        "",
        "",
        "Riverside Community Trust",
        "info@riverside.example.org",
        "Seattle",
        "United States",
    ),
    ("Frank", "Miller", "", "frank.miller@example.org", "Toronto", "Canada"),
    ("Grace", "Lee", "", "grace.lee@example.org", "Leeds", "United Kingdom"),
]

BODY_WELCOME = (
    "<div>Hello {{ first_name | there }},</div>"
    "<div>Here is what is new this month.</div>"
    "<ul><li>A shorter sign-up flow</li><li>Events near {{ city | you }}</li></ul>"
    "<div>The team</div>"
)
BODY_SAVE_THE_DATE = (
    "<div>Hello {{ first_name | there }},</div><div>Save the date: 15 October.</div>"
)


def seed_users() -> None:
    admin, created = User.objects.get_or_create(
        username="demo", defaults={"is_staff": True, "is_superuser": True}
    )
    if created:
        admin.set_password("demo")
        admin.save()
    for username, first_name, last_name, email in USERS:
        User.objects.get_or_create(
            username=username,
            defaults={"first_name": first_name, "last_name": last_name, "email": email},
        )


def seed_prospects() -> dict[str, Prospect]:
    prospects: dict[str, Prospect] = {}
    for first_name, last_name, organization, email, city, country in PROSPECTS:
        prospect, created = Prospect.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "organization": organization,
                "kind": ProspectKind.ORGANIZATION if organization else ProspectKind.INDIVIDUAL,
                "city": city,
                "country": country,
            },
        )
        if created:
            ProspectEvent.record(prospect, EventKind.IMPORTED, ACTOR_IMPORT)
            if prospect.user_id:
                ProspectEvent.record(prospect, EventKind.LINKED, ACTOR_SYSTEM)
        prospects[email] = prospect
    return prospects


def seed_mailing(
    subject: str,
    body_html: str,
    sender: str,
    days_ago: int,
    sent: list[Prospect],
    failed: list[Prospect],
    skipped_reasons: dict[str, int],
) -> None:
    if Mailing.objects.filter(subject=subject).exists():
        return
    mailing = Mailing.objects.create(
        subject=subject,
        body_html=body_html,
        sender=sender,
        sent_count=len(sent),
        failed_count=len(failed),
        skipped_count=sum(skipped_reasons.values()),
        skipped_reasons=skipped_reasons,
    )
    sent_at = timezone.now() - timedelta(days=days_ago)
    Mailing.objects.filter(pk=mailing.pk).update(created_at=sent_at)
    for prospect in sent:
        ProspectEvent.record(prospect, EventKind.MAILED, sender, subject, mailing)
        prospect.status = ProspectStatus.CONTACTED
        prospect.last_mailed_at = sent_at
        prospect.save(update_fields=["status", "last_mailed_at"])
    for prospect in failed:
        ProspectEvent.record(prospect, EventKind.MAIL_FAILED, sender, "Mailbox full", mailing)


TEMPLATES = [
    (
        "Welcome message",
        "Hello {{ first_name | there }}, welcome aboard",
        "<div>Hello {{ first_name | there }},</div><div>Welcome aboard. Here is what happens next:</div>"
        "<ul><li>Your account is ready to use</li><li>Your first message arrives within a day</li></ul>"
        "<div>The team at {{ organization | our company }}</div>",
    ),
    (
        "Event invitation",
        "You are invited, {{ first_name | friend }}",
        "<div>Hello {{ first_name | friend }},</div><div>We would love to see you at our next event in "
        "{{ city | your city }}.</div><div>Reply to this message to reserve a seat.</div>",
    ),
    (
        "Follow up after a meeting",
        "Great to meet you, {{ full_name }}",
        "<div>Hello {{ first_name | there }},</div><div>Thank you for your time today. "
        "Here is a short summary of what we discussed.</div>",
    ),
]


def seed_templates() -> None:
    for name, subject, body_html in TEMPLATES:
        EmailTemplates().save(name, subject, body_html, None, overwrite=True)


def seed() -> None:
    seed_users()
    seed_templates()
    prospects = seed_prospects()
    by_email = prospects.__getitem__
    seed_mailing(
        "Save the date: 15 October",
        BODY_SAVE_THE_DATE,
        "demo",
        9,
        [by_email("alice.carter@example.org"), by_email("hello@acmelegal.example.org")],
        [by_email("ben.hughes@example.org")],
        {"cooldown": 1},
    )
    seed_mailing(
        "Welcome {{ first_name | there }}",
        BODY_WELCOME,
        "demo",
        2,
        [
            by_email("alice.carter@example.org"),
            by_email("info@riverside.example.org"),
            by_email("ben.hughes@example.org"),
        ],
        [],
        {"unsubscribed": 1, "cooldown": 1},
    )
    ines = by_email("emma.stone@example.org")
    if ines.status != ProspectStatus.UNSUBSCRIBED:
        ProspectUnsubscriber().unsubscribe(ines, ACTOR_RECIPIENT)
    test_prospect = by_email("frank.miller@example.org")
    print("Demo ready: log in at /outreach/ as demo / demo")
    print(
        "Unsubscribe page path:",
        f"/outreach/unsubscribe/{UnsubscribeTokens().make(test_prospect)}/",
    )


seed()
