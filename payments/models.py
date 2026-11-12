from django.conf import settings
from django.db import models
from django.utils import timezone
from organizations.models import TenantModel
from crm_core.models import Deal


class Invoice(TenantModel):
    """
    Business-scoped PayPal invoice linked to a Won Deal.
    Follows PayPal Invoicing API v2 lifecycle and enforces multi-tenant isolation.
    """
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
        ("SCHEDULED", "Scheduled"),
        ("PAID", "Paid"),
        ("MARKED_AS_PAID", "Marked as Paid"),
        ("CANCELLED", "Cancelled"),
        ("REFUNDED", "Refunded"),
        ("PARTIALLY_PAID", "Partially Paid"),
        ("PARTIALLY_REFUNDED", "Partially Refunded"),
        ("PAYMENT_PENDING", "Payment Pending"),
        ("UNPAID", "Unpaid"),
    ]

    deal = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        related_name="invoices",
        help_text="The Won deal associated with this invoice.",
    )
    paypal_invoice_id = models.CharField(max_length=100, db_index=True)
    invoice_number = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=50, default="SENT", db_index=True)
    recipient_email = models.EmailField()
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    payer_link = models.URLField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )
    date_paid = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.status}) - {self.currency} {self.amount}"

    @property
    def is_paid(self):
        return self.status in ("PAID", "MARKED_AS_PAID")

    @property
    def is_active(self):
        return self.status not in ("CANCELLED", "REFUNDED")
