from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation

from outreach.choices import EventKind, ProspectStatus, SkipReason
from outreach.conf import outreach_settings
from outreach.models import Mailing, Prospect, ProspectEvent
from outreach.services.body import MailBodySanitizer
from outreach.services.mail_tags import mail_tag_library
from outreach.services.unsubscribe import SuppressionList, UnsubscribeTokens
from outreach.services.variables import MailVariables


@dataclass
class SkippedProspect:
    prospect: Prospect
    reason: SkipReason


def count_by_reason(skipped: list[SkippedProspect]) -> dict[str, int]:
    counts = Counter(skipped_prospect.reason for skipped_prospect in skipped)
    return {reason.value: counts[reason] for reason in SkipReason}


@dataclass
class MailPlan:
    recipients: list[Prospect] = field(default_factory=list)
    skipped: list[SkippedProspect] = field(default_factory=list)

    @property
    def skipped_counts(self) -> dict[str, int]:
        return count_by_reason(self.skipped)


@dataclass
class RenderedMail:
    subject: str
    text: str
    html: str


@dataclass
class MailReport:
    mailing: Mailing | None = None
    sent: list[Prospect] = field(default_factory=list)
    failed: list[Prospect] = field(default_factory=list)
    skipped: list[SkippedProspect] = field(default_factory=list)

    @property
    def skipped_counts(self) -> dict[str, int]:
        return count_by_reason(self.skipped)


class ProspectMailer:
    def __init__(self, base_url: str, actor: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.actor = actor
        self.tokens = UnsubscribeTokens()

    def plan(self, prospects: Iterable[Prospect]) -> MailPlan:
        prospect_list = list(prospects)
        suppressed_emails = SuppressionList().filter_suppressed(
            prospect.email for prospect in prospect_list
        )
        cooldown_start = timezone.now() - outreach_settings.resend_cooldown
        maximum = outreach_settings.max_recipients_per_send
        mail_plan = MailPlan()
        for prospect in prospect_list:
            reason = None
            if prospect.status == ProspectStatus.UNSUBSCRIBED:
                reason = SkipReason.UNSUBSCRIBED
            elif prospect.email in suppressed_emails:
                reason = SkipReason.SUPPRESSED
            elif prospect.last_mailed_at and prospect.last_mailed_at > cooldown_start:
                reason = SkipReason.COOLDOWN
            elif len(mail_plan.recipients) >= maximum:
                reason = SkipReason.OVER_LIMIT
            if reason:
                mail_plan.skipped.append(SkippedProspect(prospect, reason))
            else:
                mail_plan.recipients.append(prospect)
        return mail_plan

    def unsubscribe_url(self, prospect: Prospect) -> str:
        path = reverse("outreach:unsubscribe", args=[self.tokens.make(prospect)])
        return f"{self.base_url}{path}"

    def render(self, prospect: Prospect, subject: str, body_html: str) -> RenderedMail:
        variables = MailVariables()
        sanitizer = MailBodySanitizer()
        unsubscribe_url = self.unsubscribe_url(prospect)
        values = {**variables.values_for(prospect), "unsubscribe_url": unsubscribe_url}
        with translation.override(outreach_settings.language):
            tagged_subject = mail_tag_library.render(subject, prospect, values, html=False)
            personalised_subject = variables.render(tagged_subject, values, html=False)
            tagged_html = mail_tag_library.render(
                sanitizer.clean(body_html), prospect, values, html=True
            )
            personalised_html = sanitizer.clean(
                variables.render(tagged_html, values, html=True)
            )
            personalised_text = sanitizer.to_text(personalised_html)
            context = {
                "subject": personalised_subject,
                "body_html": personalised_html,
                "body_text": personalised_text,
                "unsubscribe_url": unsubscribe_url,
                "site_name": outreach_settings.site_name,
                "prospect": prospect,
                "theme": outreach_settings.theme,
            }
            text_part = render_to_string("outreach/email/message.txt", context)
            html_part = render_to_string("outreach/email/message.html", context)
        return RenderedMail(personalised_subject, text_part, html_part)

    def send(self, prospects: Iterable[Prospect], subject: str, body_html: str) -> MailReport:
        mail_plan, previous_mailed_at, mailing = self.claim(prospects, subject, body_html)
        report = MailReport(mailing=mailing, skipped=mail_plan.skipped)
        if mailing is None:
            return report
        processed_pks: set[object] = set()
        connection = get_connection()
        try:
            for prospect in mail_plan.recipients:
                if not self.is_still_mailable(prospect):
                    processed_pks.add(prospect.pk)
                    self.release(prospect, previous_mailed_at[prospect.pk])
                    report.skipped.append(SkippedProspect(prospect, SkipReason.UNSUBSCRIBED))
                    continue
                try:
                    connection.open()
                    self.send_one(prospect, subject, mailing.body_html, connection)
                except Exception as error:
                    processed_pks.add(prospect.pk)
                    connection.close()
                    self.release(prospect, previous_mailed_at[prospect.pk])
                    report.failed.append(prospect)
                    ProspectEvent.record(
                        prospect,
                        EventKind.MAIL_FAILED,
                        self.actor,
                        detail=str(error),
                        mailing=mailing,
                    )
                    continue
                processed_pks.add(prospect.pk)
                self.mark_mailed(prospect, subject, mailing)
                report.sent.append(prospect)
        finally:
            connection.close()
            for prospect in mail_plan.recipients:
                if prospect.pk not in processed_pks:
                    self.release(prospect, previous_mailed_at[prospect.pk])
            mailing.sent_count = len(report.sent)
            mailing.failed_count = len(report.failed)
            mailing.skipped_count = len(report.skipped)
            mailing.skipped_reasons = report.skipped_counts
            mailing.save(
                update_fields=[
                    "sent_count",
                    "failed_count",
                    "skipped_count",
                    "skipped_reasons",
                ]
            )
        return report

    def claim(
        self, prospects: Iterable[Prospect], subject: str, body_html: str
    ) -> tuple[MailPlan, dict[object, datetime | None], Mailing | None]:
        requested_pks = [prospect.pk for prospect in prospects]
        with transaction.atomic():
            locked_prospects = (
                Prospect.objects.select_for_update(skip_locked=True, of=("self",))
                .select_related("user")
                .filter(pk__in=requested_pks)
            )
            locked_by_pk = {prospect.pk: prospect for prospect in locked_prospects}
            fresh_prospects = [locked_by_pk[pk] for pk in requested_pks if pk in locked_by_pk]
            mail_plan = self.plan(fresh_prospects)
            previous_mailed_at = {
                prospect.pk: prospect.last_mailed_at for prospect in mail_plan.recipients
            }
            mailing = None
            if mail_plan.recipients:
                mailing = Mailing.objects.create(
                    subject=subject,
                    body_html=MailBodySanitizer().clean(body_html),
                    sender=self.actor[: Mailing._meta.get_field("sender").max_length],
                )
                Prospect.objects.filter(pk__in=previous_mailed_at).update(
                    last_mailed_at=timezone.now()
                )
        return mail_plan, previous_mailed_at, mailing

    def is_still_mailable(self, prospect: Prospect) -> bool:
        is_unsubscribed = Prospect.objects.filter(
            pk=prospect.pk, status=ProspectStatus.UNSUBSCRIBED
        ).exists()
        is_deleted = not Prospect.objects.filter(pk=prospect.pk).exists()
        return not (
            is_unsubscribed or is_deleted or SuppressionList().contains(prospect.email)
        )

    def release(self, prospect: Prospect, previous_mailed_at: datetime | None) -> None:
        Prospect.objects.filter(pk=prospect.pk).update(last_mailed_at=previous_mailed_at)
        prospect.last_mailed_at = previous_mailed_at

    def send_one(
        self, prospect: Prospect, subject: str, body_html: str, connection: BaseEmailBackend
    ) -> None:
        rendered = self.render(prospect, subject, body_html)
        message = EmailMultiAlternatives(
            subject=rendered.subject,
            body=rendered.text,
            from_email=outreach_settings.from_email,
            to=[prospect.email],
            connection=connection,
            headers={
                "List-Unsubscribe": f"<{self.unsubscribe_url(prospect)}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        )
        message.attach_alternative(rendered.html, "text/html")
        if message.send() == 0:
            raise RuntimeError("The mail server did not accept the message.")

    def mark_mailed(self, prospect: Prospect, subject: str, mailing: Mailing) -> None:
        now = timezone.now()
        Prospect.objects.filter(pk=prospect.pk).update(last_mailed_at=now, updated_at=now)
        Prospect.objects.filter(pk=prospect.pk, status=ProspectStatus.PROSPECT).update(
            status=ProspectStatus.CONTACTED, updated_at=now
        )
        prospect.refresh_from_db()
        ProspectEvent.record(
            prospect, EventKind.MAILED, self.actor, detail=subject, mailing=mailing
        )
