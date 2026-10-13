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
from outreach.services.mail_buttons import mail_buttons
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
    sent: list[Prospect] = field(default_factory=list)
    failed: list[Prospect] = field(default_factory=list)
    skipped: list[SkippedProspect] = field(default_factory=list)

    @property
    def skipped_counts(self) -> dict[str, int]:
        return count_by_reason(self.skipped)


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
        maximum = outreach_settings.max_recipients_per_send
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
        """Send the mail synchronously to every prospect that passes the plan.

        Recipients are claimed (``last_mailed_at`` set) in a transaction before any SMTP call,
        and the claim is restored for each one that fails. A failure on one recipient does not
        stop the others.
        """
        mail_plan, previous_mailed_at, mailing = self.claim(
            prospects, subject, body_html, header_text, is_newsletter
        )
        report = MailReport(mailing=mailing, skipped=mail_plan.skipped)
        if mailing is None:
            return report
        processed_pks: set[object] = set()
        connection = get_connection()
        try:
            for prospect in mail_plan.recipients:
                if not self.is_still_mailable(prospect, is_newsletter):
                    processed_pks.add(prospect.pk)
                    self.release(prospect, previous_mailed_at[prospect.pk])
                    report.skipped.append(
                        SkippedProspect(prospect, self.skip_reason_when_gone(is_newsletter))
                    )
                    continue
                try:
                    connection.open()
                    self.send_one(
                        prospect,
                        subject,
                        mailing.body_html,
                        connection,
                        header_text,
                        is_newsletter,
                    )
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
        self,
        prospects: Iterable[Prospect],
        subject: str,
        body_html: str,
        header_text: str,
        is_newsletter: bool,
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
            mail_plan = self.plan(fresh_prospects, is_newsletter=is_newsletter)
            previous_mailed_at = {
                prospect.pk: prospect.last_mailed_at for prospect in mail_plan.recipients
            }
            mailing = None
            if mail_plan.recipients:
                mailing = Mailing.objects.create(
                    subject=subject,
                    body_html=MailBodySanitizer().clean(body_html),
                    header_text=header_text,
                    is_newsletter=is_newsletter,
                    sender=self.actor[: Mailing._meta.get_field("sender").max_length],
                )
                Prospect.objects.filter(pk__in=previous_mailed_at).update(
                    last_mailed_at=timezone.now()
                )
        return mail_plan, previous_mailed_at, mailing

    def is_still_mailable(self, prospect: Prospect, is_newsletter: bool) -> bool:
        current = Prospect.objects.filter(pk=prospect.pk)
        if not is_newsletter:
            return current.filter(user__isnull=False).exists()
        is_unsubscribed = current.filter(status=ProspectStatus.UNSUBSCRIBED).exists()
        is_deleted = not current.exists()
        return not (
            is_unsubscribed or is_deleted or SuppressionList().contains(prospect.email)
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
