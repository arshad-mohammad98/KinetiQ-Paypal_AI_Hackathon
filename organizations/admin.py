from django.contrib import admin
from .models import Organization

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "subscription_state",
        "trial_ends_at",
        "current_period_end",
        "razorpay_subscription_id",
        "is_active",
        "created_at",
    )
    list_filter = ("plan_status", "is_active", "created_at")
    search_fields = ("name", "slug", "razorpay_subscription_id")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Subscription State")
    def subscription_state(self, obj):
        return obj.subscription_state.upper()
