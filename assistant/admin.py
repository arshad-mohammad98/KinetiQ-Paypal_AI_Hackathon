from django.contrib import admin
from assistant.models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "organization", "role", "created_at")
    list_filter = ("role", "created_at", "organization")
    search_fields = ("user__email", "organization__name")
    readonly_fields = ("created_at",)

