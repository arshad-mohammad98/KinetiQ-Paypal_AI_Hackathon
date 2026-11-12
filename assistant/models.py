from django.conf import settings
from django.db import models
from organizations.models import Organization


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ("user", "User"),
        ("assistant", "Assistant"),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="kine_messages",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kine_messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["organization", "user", "created_at"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.role}] user_id={self.user_id} org_id={self.organization_id} at {self.created_at}"

