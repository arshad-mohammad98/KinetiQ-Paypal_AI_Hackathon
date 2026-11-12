from django.contrib import admin
from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "organization", "deal", "amount", "currency", "status", "recipient_email", "due_date", "created_at")
    list_filter = ("status", "currency", "organization")
    search_fields = ("invoice_number", "paypal_invoice_id", "recipient_email", "deal__title")
    readonly_fields = ("created_at", "updated_at")

