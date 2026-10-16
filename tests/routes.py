from django.urls import reverse


def outreach_index_url() -> str:
    return reverse("outreach_admin:index")


def outreach_login_url() -> str:
    return reverse("outreach_admin:login")


def outreach_help_url() -> str:
    return reverse("outreach_admin:help")


def outreach_prospect_changelist_url() -> str:
    return reverse("outreach_admin:outreach_prospect_changelist")


def outreach_prospect_add_url() -> str:
    return reverse("outreach_admin:outreach_prospect_add")


def outreach_prospect_change_url(prospect_pk: str) -> str:
    return reverse("outreach_admin:outreach_prospect_change", args=[prospect_pk])


def outreach_prospect_delete_url(prospect_pk: str) -> str:
    return reverse("outreach_admin:outreach_prospect_delete", args=[prospect_pk])


def outreach_prospect_export_data_url(prospect_pk: str) -> str:
    return reverse("outreach_admin:outreach_prospect_export_data", args=[prospect_pk])


def outreach_prospect_import_url() -> str:
    return reverse("outreach_admin:outreach_prospect_import")


def outreach_prospect_process_import_url() -> str:
    return reverse("outreach_admin:outreach_prospect_process_import")


def outreach_mailing_changelist_url() -> str:
    return reverse("outreach_admin:outreach_mailing_changelist")


def outreach_mailing_add_url() -> str:
    return reverse("outreach_admin:outreach_mailing_add")


def outreach_mailing_change_url(mailing_pk: str) -> str:
    return reverse("outreach_admin:outreach_mailing_change", args=[mailing_pk])


def outreach_mailing_delete_url(mailing_pk: str) -> str:
    return reverse("outreach_admin:outreach_mailing_delete", args=[mailing_pk])


def outreach_mailing_cancel_schedule_url(mailing_pk: str) -> str:
    return reverse("outreach_admin:outreach_mailing_cancel_schedule", args=[mailing_pk])


def outreach_mailing_retry_url(mailing_pk: str) -> str:
    return reverse("outreach_admin:outreach_mailing_retry", args=[mailing_pk])


def outreach_emailtemplate_changelist_url() -> str:
    return reverse("outreach_admin:outreach_emailtemplate_changelist")


def outreach_emailtemplate_add_url() -> str:
    return reverse("outreach_admin:outreach_emailtemplate_add")


def outreach_emailtemplate_change_url(template_pk: str) -> str:
    return reverse("outreach_admin:outreach_emailtemplate_change", args=[template_pk])


def outreach_emailtemplate_delete_url(template_pk: str) -> str:
    return reverse("outreach_admin:outreach_emailtemplate_delete", args=[template_pk])


def outreach_audience_changelist_url() -> str:
    return reverse("outreach_admin:outreach_audience_changelist")


def outreach_audience_add_url() -> str:
    return reverse("outreach_admin:outreach_audience_add")


def outreach_audience_change_url(audience_pk: str) -> str:
    return reverse("outreach_admin:outreach_audience_change", args=[audience_pk])


def outreach_audience_delete_url(audience_pk: str) -> str:
    return reverse("outreach_admin:outreach_audience_delete", args=[audience_pk])


def outreach_unsubscribe_url(token: str) -> str:
    return reverse("outreach:unsubscribe", args=[token])


def outreach_unsubscribe_prefix() -> str:
    placeholder = "placeholder"
    return outreach_unsubscribe_url(placeholder).removesuffix(f"{placeholder}/")


def django_admin_index_url() -> str:
    return reverse("admin:index")
