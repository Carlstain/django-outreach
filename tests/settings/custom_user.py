from tests.settings import *  # noqa: F403
from tests.settings import INSTALLED_APPS

INSTALLED_APPS = [*INSTALLED_APPS, "tests.accounts"]
AUTH_USER_MODEL = "accounts.EmailUser"
