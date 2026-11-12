import json
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from assistant.models import ChatMessage
from assistant.services import process_user_message

security_logger = logging.getLogger("kinetiq.security")


def logo_preview_view(request):
    """
    Temporary developer-only preview page to compare Kine logo options.
    Strictly disabled in production: returns 404 whenever settings.DEBUG is False.
    """
    if not settings.DEBUG:
        raise Http404("Kine logo preview is only available in development mode.")

    return render(request, "assistant/logo_preview.html")


@login_required
@require_http_methods(["GET", "POST"])
def chat_view(request):
    """
    Handles fetching chat history (GET) and sending a message to Kine (POST).
    Strictly isolated per user and user's organization.
    """
    user = request.user
    org = user.organization
    if not org:
        return JsonResponse(
            {"success": False, "reply": "An active organization workspace is required to chat with Kine."},
            status=403,
        )

    if request.method == "GET":
        messages = ChatMessage.objects.filter(
            organization=org,
            user=user,
        ).order_by("created_at")[:50]

        history = [
            {
                "id": m.pk,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.strftime("%I:%M %p"),
            }
            for m in messages
        ]
        return JsonResponse({"success": True, "messages": history})

    # POST: Process new user message
    try:
        data = json.loads(request.body.decode("utf-8"))
        user_message = data.get("message", "")
    except Exception:
        return JsonResponse({"success": False, "reply": "Invalid JSON format in request body."}, status=400)

    result = process_user_message(user, user_message)

    if not result.get("success"):
        status_code = 429 if result.get("limit_reached") else 400
        return JsonResponse(result, status=status_code)

    return JsonResponse(result, status=200)


@login_required
@require_http_methods(["POST"])
def clear_chat_view(request):
    """
    Clears all stored chat history for the requesting user in their organization.
    """
    user = request.user
    org = user.organization
    if not org:
        return JsonResponse({"success": False, "error": "Unauthorized."}, status=403)

    deleted_count, _ = ChatMessage.objects.filter(
        organization=org,
        user=user,
    ).delete()

    security_logger.info(
        "Kine chat history cleared: user_id=%s, org_id=%s, messages_deleted=%d",
        user.pk,
        org.pk,
        deleted_count,
    )

    return JsonResponse({"success": True, "deleted_count": deleted_count})

