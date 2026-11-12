import os
from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.shortcuts import redirect
from django.urls import include, path

from organizations.views import home_view, terms_view, privacy_view
from config.views import custom_404, custom_403, custom_500, health_check_view
import config.admin  # activates superuser-only check & rate-limited login

handler404 = custom_404
handler403 = custom_403
handler500 = custom_500

admin_url_path = getattr(settings, "ADMIN_URL", "portal-admin/").strip("/")


def old_admin_view(request, *args, **kwargs):
    raise Http404("Not Found")


urlpatterns = [
    # Health probe
    path("health/", health_check_view, name="health_check"),
    # Public & Marketing Pages
    path("", home_view, name="home"),
    path("terms/", terms_view, name="terms"),
    path("privacy/", privacy_view, name="privacy"),
    # Shortcuts
    path("login/", lambda request: redirect("login")),
    path("signup/", lambda request: redirect("signup")),
    path("dashboard/", lambda request: redirect("dashboard")),
    # Apps
    path("accounts/", include("accounts.urls")),
    path("assistant/", include("assistant.urls")),
    path("", include("payments.urls")),
    path("", include("crm_core.urls")),
]

# Configure Custom Admin URL and ensure old /admin/ returns 404
if admin_url_path != "admin":
    urlpatterns.extend([
        path(f"{admin_url_path}/", admin.site.urls),
        path("admin/", old_admin_view, name="old_admin"),
        path("admin/<path:subpath>", old_admin_view, name="old_admin_subpath"),
    ])
else:
    urlpatterns.append(path("admin/", admin.site.urls))
