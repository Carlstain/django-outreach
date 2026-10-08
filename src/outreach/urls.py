from django.urls import include, path

from outreach.sites import outreach_site
from outreach.views import UnsubscribeView

public_urlpatterns = [
    path("unsubscribe/<str:token>/", UnsubscribeView.as_view(), name="unsubscribe"),
]

urlpatterns = [
    path("", include((public_urlpatterns, "outreach"))),
    path("", outreach_site.urls),
]
