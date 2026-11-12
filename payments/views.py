import decimal
import logging
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import email_verification_required
from crm_core.models import Deal
from crm_core.utils import log_audit
from .models import Invoice
from . import paypal

logger = logging.getLogger("kinetiq.payments")


@login_required
@email_verification_required
def invoice_list_view(request):
    """
    Renders the Invoices list page for the user's organization.
    Supports search, status filter, and responsive layout for mobile cards.
    """
    org = request.user.organization
    if not org:
        return redirect("home")

    qs = Invoice.objects.filter(organization=org).select_related("deal", "created_by")

    # Search filter
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(invoice_number__icontains=q)
            | Q(recipient_email__icontains=q)
            | Q(description__icontains=q)
            | Q(deal__title__icontains=q)
            | Q(paypal_invoice_id__icontains=q)
        )

    # Status filter
    status_filter = request.GET.get("status", "ALL").strip().upper()
    if status_filter and status_filter != "ALL":
        qs = qs.filter(status=status_filter)

    # Metrics summary
    all_invoices = Invoice.objects.filter(organization=org)
    total_count = all_invoices.count()
    total_invoiced_agg = all_invoices.exclude(status__in=["CANCELLED", "REFUNDED"]).aggregate(total=Sum("amount"))["total"] or decimal.Decimal("0.00")
    total_paid_agg = all_invoices.filter(status__in=["PAID", "MARKED_AS_PAID"]).aggregate(total=Sum("amount"))["total"] or decimal.Decimal("0.00")
    total_pending_agg = all_invoices.filter(status__in=["SENT", "UNPAID", "PAYMENT_PENDING", "DRAFT"]).aggregate(total=Sum("amount"))["total"] or decimal.Decimal("0.00")

    context = {
        "invoices": qs,
        "search_query": q,
        "status_filter": status_filter,
        "total_count": total_count,
        "total_invoiced": total_invoiced_agg,
        "total_paid": total_paid_agg,
        "total_pending": total_pending_agg,
        "paypal_configured": paypal.is_paypal_configured(),
    }
    return render(request, "payments/invoice_list.html", context)


@login_required
@email_verification_required
def invoice_send_view(request, deal_id):
    """
    Creates and sends a PayPal Sandbox Invoice for a Won deal.
    Accessible strictly by Owner and Admin.
    Pre-filled with contact's email, deal value, currency, and due date.
    Enforces one active invoice per deal and prevents double submission.
    """
    org = request.user.organization
    deal = get_object_or_404(Deal, pk=deal_id, organization=org)

    # Permission check: Members cannot send invoices
    if request.user.role not in ("OWNER", "ADMIN"):
        messages.error(request, "Only workspace Owners and Admins can create and send PayPal invoices.")
        return redirect("deal_update", pk=deal.pk)

    # Deal stage check: Won deals only
    if not (deal.stage and deal.stage.is_won):
        messages.error(request, "PayPal invoices can only be generated for deals in the 'Won' stage.")
        return redirect("deal_update", pk=deal.pk)

    # Active invoice check
    existing = Invoice.objects.filter(deal=deal, organization=org).exclude(status__in=["CANCELLED", "REFUNDED"]).first()
    if existing:
        messages.warning(request, f"An active invoice (#{existing.invoice_number}) already exists for deal '{deal.title}'.")
        return redirect("deal_update", pk=deal.pk)

    # PayPal sandbox keys check
    if not paypal.is_paypal_configured():
        messages.error(request, "PayPal sandbox keys not configured, see README")
        return redirect("deal_update", pk=deal.pk)

    if request.method == "POST":
        recipient_email = request.POST.get("recipient_email", "").strip()
        amount_str = request.POST.get("amount", "").strip()
        currency = request.POST.get("currency", "USD").strip().upper() or "USD"
        description = request.POST.get("description", "").strip()
        days_due_str = request.POST.get("days_due", "7").strip()

        # Validate email
        try:
            validate_email(recipient_email)
        except ValidationError:
            messages.error(request, "Please enter a valid recipient email address.")
            return redirect("deal_update", pk=deal.pk)

        # Validate amount
        try:
            amount = decimal.Decimal(amount_str)
            if amount <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, "Please enter a valid positive invoice amount.")
            return redirect("deal_update", pk=deal.pk)

        # Calculate due date
        due_date = None
        try:
            days = int(days_due_str)
            if days > 0:
                due_date = timezone.localdate() + timedelta(days=days)
        except Exception:
            pass

        # Atomic double-submission guard and API execution
        with transaction.atomic():
            if Invoice.objects.filter(deal=deal, organization=org).exclude(status__in=["CANCELLED", "REFUNDED"]).exists():
                messages.warning(request, "An invoice was already created for this deal.")
                return redirect("deal_update", pk=deal.pk)

            try:
                access_token = paypal.get_access_token()
                draft = paypal.create_draft_invoice(
                    deal=deal,
                    recipient_email=recipient_email,
                    amount=amount,
                    currency=currency,
                    description=description or f"Invoice for {deal.title}",
                    due_date=due_date,
                    access_token=access_token,
                )
                paypal_invoice_id = draft["id"]
                invoice_number = draft["invoice_number"]

                # Send invoice
                paypal.send_invoice(paypal_invoice_id, access_token=access_token)

                # Fetch updated status and payer link
                details = paypal.fetch_invoice(paypal_invoice_id, access_token=access_token)

                # Save record to database
                invoice = Invoice.objects.create(
                    organization=org,
                    deal=deal,
                    paypal_invoice_id=paypal_invoice_id,
                    invoice_number=invoice_number,
                    amount=amount,
                    currency=currency,
                    status=details.get("status", "SENT"),
                    recipient_email=recipient_email,
                    description=description or f"Invoice for {deal.title}",
                    due_date=due_date,
                    payer_link=details.get("payer_link", ""),
                    created_by=request.user,
                    date_paid=details.get("date_paid"),
                )

                log_audit(
                    request,
                    "CREATE",
                    invoice,
                    description=f"Created and sent PayPal invoice #{invoice_number} for deal '{deal.title}' ({currency} {amount:.2f})"
                )
                messages.success(request, f"PayPal invoice #{invoice_number} successfully sent to {recipient_email}!")
            except paypal.PayPalConfigError as e:
                messages.error(request, str(e))
            except paypal.PayPalAPIError as e:
                logger.error("PayPal API Error creating invoice for deal %s: %s", deal.pk, e)
                messages.error(request, f"PayPal error: {e}")
            except Exception as e:
                logger.exception("Unexpected error creating PayPal invoice for deal %s: %s", deal.pk, e)
                messages.error(request, "Connection to PayPal sandbox timed out or failed. No invoice was created.")

        return redirect("deal_update", pk=deal.pk)

    return redirect("deal_update", pk=deal.pk)


@login_required
@email_verification_required
def invoice_refresh_view(request, invoice_id):
    """
    Fetches the latest status of an invoice from the PayPal Sandbox API.
    Updates status and paid date in the database.
    Strictly tenant-scoped.
    """
    org = request.user.organization
    invoice = get_object_or_404(Invoice, pk=invoice_id, organization=org)

    if not paypal.is_paypal_configured():
        messages.error(request, "PayPal sandbox keys not configured, see README")
        return redirect("deal_update", pk=invoice.deal.pk)

    try:
        details = paypal.fetch_invoice(invoice.paypal_invoice_id)
        new_status = details.get("status", invoice.status)
        invoice.status = new_status
        if details.get("payer_link"):
            invoice.payer_link = details["payer_link"]
        if details.get("date_paid"):
            invoice.date_paid = details["date_paid"]
        invoice.save()

        log_audit(
            request,
            "UPDATE",
            invoice,
            description=f"Refreshed PayPal invoice #{invoice.invoice_number} status: {new_status}"
        )
        messages.success(request, f"Invoice #{invoice.invoice_number} status updated to '{new_status}'.")
    except Exception as e:
        logger.error("Error refreshing invoice %s: %s", invoice.pk, e)
        messages.error(request, f"Could not refresh invoice from PayPal: {e}")

    # Return to referring page or deal page
    referer = request.META.get("HTTP_REFERER")
    if referer and ("deals" in referer or "invoices" in referer):
        return redirect(referer)
    return redirect("deal_update", pk=invoice.deal.pk)


@login_required
@email_verification_required
def billing_view(request):
    """
    Displays the organization subscription and trial status.
    Keeps trial lifecycle and plan rules intact without external checkout buttons.
    """
    org = request.user.organization
    if not org:
        return redirect("home")

    is_trial = org.is_trial_active
    days_left = org.days_left_in_trial

    context = {
        "organization": org,
        "subscription_state": org.subscription_state,
        "is_trial": is_trial,
        "days_left": days_left,
        "plan_name": "Business",
        "plan_price_display": "$49 / month",
    }
    return render(request, "payments/billing.html", context)
