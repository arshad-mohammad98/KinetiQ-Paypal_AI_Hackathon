import secrets
from datetime import timedelta
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from organizations.models import Organization

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "OWNER")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = [
        ("OWNER", "Business Owner"),
        ("ADMIN", "Administrator"),
        ("MEMBER", "Team Member"),
    ]

    username = None
    email = models.EmailField("Email Address", unique=True)
    first_name = models.CharField("First Name", max_length=50)
    last_name = models.CharField("Last Name", max_length=50)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="MEMBER")
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email

    @property
    def is_owner(self):
        return self.role == "OWNER" or self.is_superuser

    @property
    def is_admin_or_owner(self):
        return self.role in ["OWNER", "ADMIN"] or self.is_superuser

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class TeamInvitation(models.Model):
    INVITE_ROLES = [
        ("ADMIN", "Administrator"),
        ("MEMBER", "Team Member"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=INVITE_ROLES, default="MEMBER")
    token = models.CharField(max_length=64, unique=True, blank=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    is_accepted = models.BooleanField(default=False)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return not self.is_accepted and timezone.now() < self.expires_at

    def __str__(self):
        return f"Invite for {self.email} ({self.organization.name})"
