from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, TeamInvitation

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "organization", "is_staff")
    list_filter = ("role", "is_staff", "is_active", "organization")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Organization & Permissions", {"fields": ("organization", "role", "is_active", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "created_at")}),
    )
    readonly_fields = ("created_at",)

@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "is_accepted", "expires_at")
    list_filter = ("role", "is_accepted", "organization")
    search_fields = ("email", "organization__name")
