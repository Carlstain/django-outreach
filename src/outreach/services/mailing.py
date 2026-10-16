import smtplib
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from uuid import UUID

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation

from outreach.choices import (
    DeliveryStatus,
    DispatchMode,
    EventKind,
    ProspectStatus,
    SkipReason,
)
from outreach.conf import outreach_settings
from outreach.models import Mailing, MailingDelivery, Prospect, ProspectEvent
from outreach.services.body import MailBodySanitizer
from outreach.services.mail_buttons import mail_buttons
from outreach.services.mail_tags import mail_tag_library
from outreach.services.unsubscribe import SuppressionList, UnsubscribeTokens
from outreach.services.variables import MailVariables
from outreach.signals import mail_failed, mail_sent, send_after_commit


@dataclass
class SkippedProspect:
    prospect: Prospect
    reason: SkipReason


def count_by_reason(skipped: list[SkippedProspect]) -> dict[str, int]:
    counts = Counter(skipped_prospect.reason for skipped_prospect in skipped)
    return {reason.value: counts[reason] for reason in SkipReason}


@dataclass
class MailPlan:
    """Who will be mailed and who is skipped, with the reason for each skip."""

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
    """Outcome of a send. ``mailing`` is ``None`` when nobody was left to mail."""

    mailing: Mailing | None = None
    queued: list[Prospect] = field(default_factory=list)
    scheduled: list[Prospect] = field(default_factory=list)
    sent: list[Prospect] = field(default_factory=list)
    failed: list[Prospect] = field(default_factory=list)
    skipped: list[SkippedProspect] = field(default_factory=list)

    @property
    def skipped_counts(self) -> dict[str, int]:
        return count_by_reason(self.skipped)


@dataclass
class QueuedMailing:
    plan: MailPlan
    mailing: Mailing | None = None
    deliveries: list[MailingDelivery] = field(default_factory=list)


class TransientDeliveryError(Exception):
    """A delivery failed for a reason that a later attempt may overcome."""


class ProspectMailer:
    """Plans, renders and sends a mailing to prospects.

    Args:
        base_url: Origin used to build unsubscribe links, normally ``OUTREACH_BASE_URL``.
        actor: Who triggers the send, recorded on events and as the mailing sender.
    """

    def __init__(self, base_url: str, actor: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.actor = actor
        self.tokens = UnsubscribeTokens()

    def plan(self, prospects: Iterable[Prospect], *, is_newsletter: bool = True) -> MailPlan:
        """Split prospects into recipients and skipped ones.

        A newsletter skips prospects that are unsubscribed or suppressed. A notice skips
        prospects that are not members and ignores unsubscription, since it carries no
        unsubscribe action. Both skip prospects mailed within ``OUTREACH_RESEND_COOLDOWN``
        and those beyond ``OUTREACH_MAX_RECIPIENTS_PER_SEND``.
        """
        prospect_list = list(prospects)
        suppressed_emails = SuppressionList().filter_suppressed(
            prospect.email for prospect in prospect_list
        )
        cooldown_start = timezone.now() - outreach_settings.resend_cooldown
        maximum = outreach_settings.recipient_cap
        mail_plan = MailPlan()
        for prospect in prospect_list:
            reason = None
            if is_newsletter and prospect.status == ProspectStatus.UNSUBSCRIBED:
                reason = SkipReason.UNSUBSCRIBED
            elif is_newsletter and prospect.email in suppressed_emails:
                reason = SkipReason.SUPPRESSED
            elif not is_newsletter and prospect.user_id is None:
                reason = SkipReason.NOT_MEMBER
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

    def render(
        self,
        prospect: Prospect,
        subject: str,
        body_html: str,
        *,
        header_text: str = "",
        is_newsletter: bool = True,
        preview: bool = False,
    ) -> RenderedMail:
        """Render the subject and body for one prospect, as text and HTML.

        Tags run first, then variables, and the HTML is sanitised after substitution.
        """
        variables = MailVariables()
        sanitizer = MailBodySanitizer()
        unsubscribe_url = self.unsubscribe_url(prospect)
        values = {**variables.values_for(prospect), "unsubscribe_url": unsubscribe_url}
        with translation.override(outreach_settings.language):
            tagged_subject = mail_tag_library.render(
                subject, prospect, values, html=False, preview=preview
            )
            personalised_subject = variables.render(tagged_subject, values, html=False)
            body_with_tokens, buttons = mail_buttons.extract(
                sanitizer.clean(body_html),
                lambda argument: mail_tag_library.resolve_argument(
                    argument, prospect, values, html=True, preview=preview
                ),
            )
            tagged_html = mail_tag_library.render(
                body_with_tokens, prospect, values, html=True, preview=preview
            )
            cleaned_html = sanitizer.clean(variables.render(tagged_html, values, html=True))
            theme = outreach_settings.theme
            personalised_html = mail_buttons.insert(cleaned_html, buttons, theme.email)
            personalised_text = sanitizer.to_text(personalised_html)
            has_header_logo = bool(
                outreach_settings.email_logo_in_header and outreach_settings.email_logo_url
            )
            site_name = outreach_settings.site_name
            context = {
                "subject": personalised_subject,
                "body_html": personalised_html,
                "body_text": personalised_text,
                "unsubscribe_url": unsubscribe_url,
                "site_name": site_name,
                "header_text": header_text or ("" if has_header_logo else site_name),
                "header_logo_alt": header_text or site_name,
                "has_header_logo": has_header_logo,
                "is_newsletter": is_newsletter,
                "logo_url": outreach_settings.email_logo_url,
                "logo_in_header": outreach_settings.email_logo_in_header,
                "logo_in_footer": outreach_settings.email_logo_in_footer,
                "prospect": prospect,
                "theme": theme,
            }
            text_part = render_to_string("outreach/email/message.txt", context)
            html_part = render_to_string("outreach/email/message.html", context)
        return RenderedMail(personalised_subject, text_part, html_part)

    def send(
        self,
        prospects: Iterable[Prospect],
        subject: str,
        body_html: str,
        *,
        header_text: str = "",
        is_newsletter: bool = True,
    ) -> MailReport:
        """Send the mail to every prospect that passes the plan, or queue it for Celery.

        Recipients are claimed (``last_mailed_at`` set) in a transaction before any SMTP call,
        and the claim is restored for each one that fails. A failure on one recipient does not
        stop the others. With ``OUTREACH_DISPATCH = "celery"`` the deliveries are queued and
        ``MailReport.queued`` lists their prospects, with ``sent`` and ``failed`` left empty.
        """
        queued_mailing = self.queue(prospects, subject, body_html, header_text, is_newsletter)
        report = MailReport(
            mailing=queued_mailing.mailing, skipped=list(queued_mailing.plan.skipped)
        )
        if queued_mailing.mailing is None:
            return report
        self.dispatch(queued_mailing.deliveries, report, is_newsletter, self.discard_delivery)
        queued_mailing.mailing.refresh_from_db()
        return report

    def retry(self, mailing: Mailing, delivery_pk: UUID | None = None) -> MailReport:
        """Send again the failed deliveries of a mailing, or only the given one.

        Each delivery is claimed again and goes through ``deliver``, so a prospect that
        unsubscribed since the failure is skipped. The resend cooldown is not applied: the
        retry is an explicit choice. At most ``OUTREACH_MAX_RECIPIENTS_PER_SEND`` deliveries
        are retried in synchronous mode, ``OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND`` with
        Celery, and the rest stay failed.
        """
        deliveries = self.reopen(mailing, delivery_pk)
        report = MailReport(mailing=mailing)
        if deliveries:
            self.dispatch(deliveries, report, mailing.is_newsletter, self.fail_again)
        return report

    def reopen(
        self, mailing: Mailing, delivery_pk: UUID | None = None
    ) -> list[MailingDelivery]:
        with transaction.atomic():
            failed_deliveries = (
                MailingDelivery.objects.select_for_update(
                    skip_locked=True, of=("self", "prospect")
                )
                .select_related("prospect")
                .filter(mailing=mailing, status=DeliveryStatus.FAILED)
            )
            if delivery_pk is not None:
                failed_deliveries = failed_deliveries.filter(pk=delivery_pk)
            deliveries = list(failed_deliveries[: outreach_settings.recipient_cap])
            if not deliveries:
                return deliveries
            claimed_at = timezone.now()
            for delivery in deliveries:
                delivery.status = DeliveryStatus.PENDING
                delivery.attempts = 0
                delivery.previous_mailed_at = delivery.prospect.last_mailed_at
                delivery.updated_at = claimed_at
            MailingDelivery.objects.bulk_update(
                deliveries, ["status", "attempts", "previous_mailed_at", "updated_at"]
            )
            Prospect.objects.filter(
                pk__in=[delivery.prospect_id for delivery in deliveries]
            ).update(last_mailed_at=claimed_at)
            Mailing.objects.filter(pk=mailing.pk).update(
                failed_count=Greatest(F("failed_count") - len(deliveries), 0)
            )
        return deliveries

    def dispatch(
        self,
        deliveries: list[MailingDelivery],
        report: MailReport,
        is_newsletter: bool,
        abandon: Callable[[MailingDelivery], None],
    ) -> None:
        if outreach_settings.dispatch == DispatchMode.CELERY:
            self.enqueue(delivery.pk for delivery in deliveries)
            report.queued = [delivery.prospect for delivery in deliveries]
            return
        self.deliver_all(deliveries, report, is_newsletter, abandon)

    def deliver_all(
        self,
        deliveries: list[MailingDelivery],
        report: MailReport,
        is_newsletter: bool,
        abandon: Callable[[MailingDelivery], None],
    ) -> None:
        connection = get_connection()
        delivered_pks: set[object] = set()
        try:
            for delivery in deliveries:
                status = self.deliver(delivery.pk, connection)
                delivered_pks.add(delivery.pk)
                if status == DeliveryStatus.SENT:
                    report.sent.append(delivery.prospect)
                elif status == DeliveryStatus.FAILED:
                    report.failed.append(delivery.prospect)
                else:
                    report.skipped.append(
                        SkippedProspect(
                            delivery.prospect, self.skip_reason_when_gone(is_newsletter)
                        )
                    )
        finally:
            connection.close()
            for delivery in deliveries:
                if delivery.pk not in delivered_pks:
                    abandon(delivery)

    def discard_delivery(self, delivery: MailingDelivery) -> None:
        self.release(delivery.prospect, delivery.previous_mailed_at)
        delivery.delete()

    def fail_again(self, delivery: MailingDelivery) -> None:
        self.release(delivery.prospect, delivery.previous_mailed_at)
        delivery.status = DeliveryStatus.FAILED
        delivery.save(update_fields=["status", "updated_at"])
        Mailing.objects.filter(pk=delivery.mailing_id).update(
            failed_count=F("failed_count") + 1
        )

    def queue(
        self,
        prospects: Iterable[Prospect],
        subject: str,
        body_html: str,
        header_text: str,
        is_newsletter: bool,
        send_at: datetime | None = None,
    ) -> QueuedMailing:
        """Create the mailing with one delivery per recipient, and claim the recipients.

        With ``send_at`` the deliveries are ``scheduled`` and nothing is claimed: the claim
        happens when the mailing starts, see ``MailingScheduler``.
        """
        requested_pks = [prospect.pk for prospect in prospects]
        with transaction.atomic():
            locked_prospects = (
                Prospect.objects.select_for_update(skip_locked=True, of=("self",))
                .select_related("user")
                .filter(pk__in=requested_pks)
            )
            locked_by_pk = {prospect.pk: prospect for prospect in locked_prospects}
            fresh_prospects = [locked_by_pk[pk] for pk in requested_pks if pk in locked_by_pk]
            mail_plan = self.plan(fresh_prospects, is_newsletter=is_newsletter)
            if not mail_plan.recipients:
                return QueuedMailing(plan=mail_plan)
            mailing = Mailing.objects.create(
                subject=subject,
                body_html=MailBodySanitizer().clean(body_html),
                header_text=header_text,
                is_newsletter=is_newsletter,
                sender=self.actor[: Mailing._meta.get_field("sender").max_length],
                skipped_count=len(mail_plan.skipped),
                skipped_reasons=mail_plan.skipped_counts,
                scheduled_for=send_at,
            )
            status = DeliveryStatus.PENDING if send_at is None else DeliveryStatus.SCHEDULED
            deliveries = MailingDelivery.objects.bulk_create(
                MailingDelivery(
                    mailing=mailing,
                    prospect=prospect,
                    status=status,
                    previous_mailed_at=prospect.last_mailed_at if send_at is None else None,
                )
                for prospect in mail_plan.recipients
            )
            if send_at is None:
                Prospect.objects.filter(
                    pk__in=[prospect.pk for prospect in mail_plan.recipients]
                ).update(last_mailed_at=timezone.now())
        return QueuedMailing(plan=mail_plan, mailing=mailing, deliveries=deliveries)

    @staticmethod
    def enqueue(delivery_pks: Iterable[object]) -> None:
        from outreach.tasks import deliver_mail

        queue_name = outreach_settings.celery_queue
        for delivery_pk in delivery_pks:
            transaction.on_commit(
                partial(deliver_mail.apply_async, args=[str(delivery_pk)], queue=queue_name)
            )

    def deliver(
        self,
        delivery_pk: object,
        connection: BaseEmailBackend | None = None,
        *,
        may_retry: bool = False,
    ) -> DeliveryStatus | None:
        """Send one pending delivery and record the outcome.

        Returns ``None`` when the delivery is not pending anymore or is held by another worker.
        With ``may_retry``, a transient error raises ``TransientDeliveryError`` after
        ``attempts`` is saved, until ``OUTREACH_DELIVERY_MAX_RETRIES`` is reached.
        """
        transient_error = None
        with transaction.atomic():
            locked = (
                MailingDelivery.objects.select_for_update(skip_locked=True, of=("self",))
                .select_related("mailing", "prospect")
                .filter(pk=delivery_pk, status=DeliveryStatus.PENDING)
                .first()
            )
            if locked is None:
                return None
            mailing = locked.mailing
            prospect = locked.prospect
            is_newsletter = mailing.is_newsletter
            if not self.is_still_mailable(prospect, is_newsletter):
                self.release(prospect, locked.previous_mailed_at)
                self.settle(locked, DeliveryStatus.SKIPPED)
                self.skip_in_mailing(mailing, self.skip_reason_when_gone(is_newsletter))
                return DeliveryStatus.SKIPPED
            own_connection = connection is None
            mail_connection = get_connection() if own_connection else connection
            locked.attempts += 1
            try:
                mail_connection.open()
                self.send_one(
                    prospect,
                    mailing.subject,
                    mailing.body_html,
                    mail_connection,
                    mailing.header_text,
                    is_newsletter,
                )
            except Exception as error:
                mail_connection.close()
                can_retry = (
                    may_retry
                    and self.is_transient(error)
                    and locked.attempts <= outreach_settings.delivery_max_retries
                )
                if not can_retry:
                    self.fail_delivery(locked, error)
                    return DeliveryStatus.FAILED
                locked.last_error = str(error)[:255]
                locked.save(update_fields=["attempts", "last_error", "updated_at"])
                transient_error = error
            else:
                if own_connection:
                    mail_connection.close()
                self.settle(locked, DeliveryStatus.SENT)
                self.mark_mailed(prospect, mailing.subject, mailing)
                Mailing.objects.filter(pk=mailing.pk).update(sent_count=F("sent_count") + 1)
                send_after_commit(
                    mail_sent,
                    ProspectMailer,
                    delivery=locked,
                    mailing=mailing,
                    prospect=prospect,
                )
                return DeliveryStatus.SENT
        raise TransientDeliveryError(str(transient_error)) from transient_error

    @staticmethod
    def is_transient(error: Exception) -> bool:
        return isinstance(error, OSError) and not isinstance(
            error, smtplib.SMTPRecipientsRefused
        )

    def fail_delivery(self, delivery: MailingDelivery, error: Exception) -> None:
        self.release(delivery.prospect, delivery.previous_mailed_at)
        self.settle(delivery, DeliveryStatus.FAILED, error=str(error))
        Mailing.objects.filter(pk=delivery.mailing_id).update(
            failed_count=F("failed_count") + 1
        )
        ProspectEvent.record(
            delivery.prospect,
            EventKind.MAIL_FAILED,
            self.actor,
            detail=str(error),
            mailing=delivery.mailing,
        )
        send_after_commit(
            mail_failed,
            ProspectMailer,
            delivery=delivery,
            mailing=delivery.mailing,
            prospect=delivery.prospect,
        )

    @staticmethod
    def settle(delivery: MailingDelivery, status: DeliveryStatus, error: str = "") -> None:
        delivery.status = status
        delivery.last_error = error[:255]
        delivery.save(update_fields=["status", "attempts", "last_error", "updated_at"])

    @staticmethod
    def skip_in_mailing(mailing: Mailing, reason: SkipReason, count: int = 1) -> None:
        locked_mailing = (
            Mailing.objects.select_for_update()
            .only("skipped_count", "skipped_reasons")
            .get(pk=mailing.pk)
        )
        reasons = {skip_reason.value: 0 for skip_reason in SkipReason}
        reasons.update(locked_mailing.skipped_reasons)
        reasons[reason.value] += count
        locked_mailing.skipped_reasons = reasons
        locked_mailing.skipped_count += count
        locked_mailing.save(update_fields=["skipped_count", "skipped_reasons"])

    def is_still_mailable(self, prospect: Prospect, is_newsletter: bool) -> bool:
        if not is_newsletter:
            return prospect.user_id is not None
        return prospect.status != ProspectStatus.UNSUBSCRIBED and not (
            SuppressionList().contains(prospect.email)
        )

    def skip_reason_when_gone(self, is_newsletter: bool) -> SkipReason:
        return SkipReason.UNSUBSCRIBED if is_newsletter else SkipReason.NOT_MEMBER

    def release(self, prospect: Prospect, previous_mailed_at: datetime | None) -> None:
        Prospect.objects.filter(pk=prospect.pk).update(last_mailed_at=previous_mailed_at)
        prospect.last_mailed_at = previous_mailed_at

    def send_one(
        self,
        prospect: Prospect,
        subject: str,
        body_html: str,
        connection: BaseEmailBackend,
        header_text: str,
        is_newsletter: bool,
    ) -> None:
        rendered = self.render(
            prospect, subject, body_html, header_text=header_text, is_newsletter=is_newsletter
        )
        headers = {}
        if is_newsletter:
            headers = {
                "List-Unsubscribe": f"<{self.unsubscribe_url(prospect)}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            }
        message = EmailMultiAlternatives(
            subject=rendered.subject,
            body=rendered.text,
            from_email=outreach_settings.from_email,
            to=[prospect.email],
            connection=connection,
            headers=headers,
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
