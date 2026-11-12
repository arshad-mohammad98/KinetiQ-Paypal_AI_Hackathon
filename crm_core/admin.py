from django.contrib import admin
from .models import Company, Contact, Stage, Deal, Task, AuditLog

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "industry", "phone", "created_at")
    list_filter = ("organization", "industry")
    search_fields = ("name", "industry", "phone")

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "organization", "company", "status")
    list_filter = ("organization", "status")
    search_fields = ("first_name", "last_name", "email")

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "order", "is_won", "is_lost")
    list_filter = ("organization",)
    search_fields = ("name",)

@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "value", "stage", "company", "owner", "expected_close_date")
    list_filter = ("organization", "stage")
    search_fields = ("title", "company__name")

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "task_type", "due_date", "due_time", "is_completed", "assigned_to")
    list_filter = ("organization", "task_type", "is_completed")
    search_fields = ("title", "notes")

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action_type", "organization", "user", "target_model", "target_id", "created_at")
    list_filter = ("organization", "action_type")
    readonly_fields = ("created_at",)
