from functools import wraps
import logging
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

security_logger = logging.getLogger("kinetiq.security")

def email_verification_required(view_func):
    """
    Ensures that a user cannot access the view unless their email has been verified.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not request.user.is_email_verified and not request.user.is_superuser:
            return redirect("verification_sent")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_or_owner_required(view_func):
    """
    Restricts access to Organization Owners and Admins (plus Superusers).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not request.user.is_admin_or_owner:
            security_logger.warning(
                "Permission denied: user %s attempted to access admin/owner view %s from IP %s",
                getattr(request.user, "email", "Unknown"),
                request.path,
                request.META.get("REMOTE_ADDR"),
            )
            messages.error(request, "You do not have permission to access that page.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
