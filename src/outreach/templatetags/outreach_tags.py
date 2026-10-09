from django import template
from django.utils.safestring import mark_safe

from outreach.conf import outreach_settings

register = template.Library()


@register.simple_tag
def outreach_theme_css() -> str:
    return mark_safe(f"<style>{outreach_settings.theme.css()}</style>")
