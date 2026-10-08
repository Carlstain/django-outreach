import os

SECRET_KEY = "outreach-example-only-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "import_export",
    "outreach",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/tmp/outreach-example.sqlite3",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en"
USE_I18N = True
USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
OUTREACH_BASE_URL = "http://localhost:8000"

IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT = True

WARM_THEME = {
    "brand": "#134e4a",
    "accent": "#d97706",
    "on_accent": "#ffffff",
    "text": "#1c1917",
    "muted": "#78716c",
    "background": "#fafaf9",
    "surface": "#ffffff",
    "border": "#e7e5e4",
    "dark": {
        "brand": "#5eead4",
        "accent": "#fbbf24",
        "on_accent": "#1c1917",
        "text": "#e7e5e4",
        "muted": "#a8a29e",
        "background": "#0c0a09",
        "surface": "#1c1917",
        "border": "#292524",
    },
}

if os.environ.get("EXAMPLE_THEME", "default") == "warm":
    OUTREACH_THEME = WARM_THEME
