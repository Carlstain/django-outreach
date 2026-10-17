from django.db import models


class OutreachLanguage(models.TextChoices):
    EN = "en", "English"
    FR = "fr", "Français"
    ES = "es", "Español"
    PT = "pt", "Português"
    PT_BR = "pt-br", "Português (Brasil)"

    @classmethod
    def parse(cls, code: str | None) -> str | None:
        normalised = (code or "").strip().lower().replace("_", "-")
        for candidate in (normalised, normalised.partition("-")[0]):
            if candidate in cls._value2member_map_:
                return candidate
        return None
