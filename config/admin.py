import logging
from django.contrib import admin
from django.http import HttpResponse
from django_ratelimit.decorators import ratelimit

security_logger = logging.getLogger("kinetiq.security")

# Configure Django Admin Branding for KinetiQ
admin.site.site_header = "KinetiQ Administration"
admin.site.site_title = "KinetiQ"
admin.site.index_title = "Welcome to KinetiQ Admin"

# Patch standard Django admin.site to strictly enforce superuser-only access
def _superuser_has_permission(request):
    """
    Enforces that ONLY active superusers can access the admin site.
    Standard staff users without is_superuser are denied.
    """
    return bool(request.user and request.user.is_active and request.user.is_superuser)

admin.site.has_permission = _superuser_has_permission

# Wrap admin.site.login to enforce brute-force rate limiting (5 attempts per minute per IP)
_original_admin_login = admin.site.login

@ratelimit(key="ip", rate="5/m", method="POST", block=False)
def rate_limited_admin_login(request, extra_context=None):
    if getattr(request, "limited", False):
        security_logger.warning(
            "Admin login rate limit exceeded from IP %s",
            request.META.get("REMOTE_ADDR"),
        )
        return HttpResponse("Too many admin login attempts. Please wait 1 minute before trying again.", status=429)

    if request.method == "POST":
        response = _original_admin_login(request, extra_context=extra_context)
        if not request.user.is_authenticated:
            username = request.POST.get("username", "")[:100]
            security_logger.warning(
                "Failed admin login attempt for user '%s' from IP %s",
                username,
                request.META.get("REMOTE_ADDR"),
            )
        return response

    return _original_admin_login(request, extra_context=extra_context)

admin.site.login = rate_limited_admin_login

