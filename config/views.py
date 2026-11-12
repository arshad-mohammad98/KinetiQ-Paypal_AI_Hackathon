import logging
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render

security_logger = logging.getLogger("kinetiq.security")
error_logger = logging.getLogger("django.request")


def custom_404(request, exception=None):
    """
    Friendly 404 Page Not Found error view. Never shows technical details.
    """
    return render(request, "404.html", status=404)


def custom_403(request, exception=None):
    """
    Friendly 403 Forbidden error view.
    Logs permission denial event to security log. Never shows technical details.
    """
    user_ident = (
        getattr(request.user, "email", "Anonymous")
        if (hasattr(request, "user") and request.user.is_authenticated)
        else "Anonymous"
    )
    security_logger.warning(
        "Permission denied (403) for %s on %s from IP %s",
        user_ident,
        request.path,
        request.META.get("REMOTE_ADDR"),
    )
    return render(request, "403.html", status=403)


def custom_500(request):
    """
    Friendly 500 Internal Server Error view.
    Logs error internally. Never reveals stack traces or technical details.
    """
    error_logger.error("Internal server error (500) encountered on %s", request.path)
    return render(request, "500.html", status=500)


def health_check_view(request):
    """
    Health check endpoint: returns HTTP 200 'ok' only if the database is reachable.
    Exposes zero technical details or database error strings.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row and row[0] == 1:
                return HttpResponse("ok", content_type="text/plain; charset=utf-8", status=200)
    except Exception as exc:
        security_logger.error("Health check probe failed: %s", exc)

    return HttpResponse("unavailable", content_type="text/plain; charset=utf-8", status=503)

