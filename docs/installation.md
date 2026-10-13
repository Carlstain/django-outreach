# Installation

## Requirements

- Python 3.10 or later
- Django 5.1 or 5.2 (`>=5.1,<6`)
- nh3 0.3.x

## Install the package

django-outreach is a beta published on PyPI as `django-outreach`. The import name and the app
label are `outreach`. Beta versions are only installed when you ask for them.

With uv:

```shell
uv add django-outreach --prerelease=allow
```

With pip:

```shell
pip install --pre django-outreach
```

Pin an exact version in your own requirements, for example `django-outreach==0.1.0b4`, since the
interface may still change before `0.1.0`. Every release also has its wheel and sdist attached to
its [GitHub Release](https://github.com/Carlstain/django-outreach/releases).

## Configure the host project

### 1. Add the apps

`outreach` needs `django.contrib.admin`, `auth`, `contenttypes`, `sessions`, `messages` and
`staticfiles`.

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "outreach",
]
```

### 2. Middleware and template context processors

Use the same ones Django's admin requires: the sessions, authentication, messages and CSRF
middleware, and the `request`, `auth` and `messages` context processors, with `APP_DIRS = True`
or the app templates otherwise reachable.

No `LocaleMiddleware` is needed. The app activates `OUTREACH_LANGUAGE` itself for its own pages,
see {doc}`topics/i18n`.

### 3. Mount the URLs

Mount them under any prefix:

```python
from django.urls import include, path

urlpatterns = [
    path("outreach/", include("outreach.urls")),
]
```

The unsubscribe page is `<prefix>/unsubscribe/<token>/` (URL name `outreach:unsubscribe`). The
admin site instance is `outreach_admin`. See {doc}`reference/admin` for every URL name.

### 4. Settings, migrations and static files

Set `OUTREACH_BASE_URL` and your `EMAIL_*` settings, see {doc}`configuration`. Sending is refused
while `OUTREACH_BASE_URL` is empty.

```shell
python manage.py migrate
python manage.py collectstatic
```

### 5. Create staff users

Access to the whole site requires `is_staff`, `is_active` and the `outreach.view_prospect`
permission (superusers have it). A user who holds only template permissions cannot reach the
Templates pages. Give permissions through groups, see {ref}`permissions`.

## Try the example project

`example/` is a minimal host project with demo data. From a checkout of the repository:

```shell
docker compose run --rm -p 8765:8000 -e EXAMPLE_THEME=default app sh -c \
  "python example/manage.py migrate -v 0 && python example/manage.py shell < example/seed_demo.py && python example/manage.py runserver 0.0.0.0:8000"
```

Open <http://localhost:8765/outreach/> and log in as `demo` / `demo` (a throwaway account created
by the seed script). Use `EXAMPLE_THEME=warm` to see the second theme. The example uses the
console email backend, so nothing is ever sent, and keeps its SQLite database inside the
container.

:::{warning}
`example/` is a demonstration only. Its secret key is public, `DEBUG` is on and the seed script
creates a `demo` / `demo` superuser. Never deploy it.
:::

## App label collisions

The app label is `outreach`, the same as the Python package. Tables are `outreach_prospect`,
`outreach_prospectevent`, `outreach_mailing`, `outreach_suppression` and `outreach_emailtemplate`.
A host project with another app labelled `outreach` will collide, so check before installing.
