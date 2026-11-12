import calendar
import datetime
from decimal import Decimal
import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django_ratelimit.decorators import ratelimit

from crm_core.models import AuditLog, Contact, Deal, Stage, Task
from organizations.models import Organization
from payments.models import Invoice
from .decorators import admin_or_owner_required, email_verification_required
from .forms import AcceptInviteForm, LoginForm, SignupForm, TeamInviteForm
from .models import TeamInvitation, User
from .utils import send_invitation_email, send_verification_email

security_logger = logging.getLogger("kinetiq.security")

def signup_view(request):
    """
    Self-service signup: creates an Organization with a 14-day trial
    and a primary User with the 'OWNER' role.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            # 1. Create Organization
            business_name = form.cleaned_data["business_name"].strip()
            organization = Organization.objects.create(
                name=business_name,
                plan_status="TRIAL",
            )

            # 2. Create Owner User
            user = User.objects.create_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                first_name=form.cleaned_data["first_name"].strip(),
                last_name=form.cleaned_data["last_name"].strip(),
                organization=organization,
                role="OWNER",
                is_email_verified=False,
            )

            # 3. Send Verification Email (delivered strictly via email)
            send_verification_email(request, user)
            request.session["pending_verification_email"] = user.email

            return redirect("verification_sent")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


def verification_sent_view(request):
    """
    Informs user to check their inbox for the verification email.
    """
    email = request.session.get("pending_verification_email")
    if not email and request.user.is_authenticated:
        email = request.user.email
    return render(request, "accounts/verification_sent.html", {"email": email})


@ratelimit(key="ip", rate="3/m", method=["GET", "POST"], block=False)
def resend_verification_view(request):
    """
    Resends verification email to the user (rate limited to 3 per minute).
    """
    if getattr(request, "limited", False):
        messages.error(request, "Too many resend attempts. Please wait a minute before requesting another email.")
        return redirect("verification_sent")

    email = request.session.get("pending_verification_email")
    if not email and request.user.is_authenticated:
        email = request.user.email

    if email:
        user = User.objects.filter(email=email).first()
        if user and not user.is_email_verified:
            send_verification_email(request, user)
            messages.success(request, f"A fresh verification link has been sent to {email}.")
    return redirect("verification_sent")


def verify_email_view(request, uidb64, token):
    """
    Validates email verification token and activates the account.
    """
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_email_verified = True
        user.save()
        login(request, user)
        messages.success(request, "Email verified successfully! Welcome to your CRM.")
        return redirect("dashboard")
    else:
        messages.error(request, "The verification link is invalid or has expired.")
        return redirect("login")


@ratelimit(key="ip", rate="5/m", method="POST", block=False)
def login_view(request):
    """
    User login with brute-force rate limiting (5 attempts per minute).
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    was_limited = getattr(request, "limited", False)
    if was_limited:
        security_logger.warning("Login rate limit exceeded from IP %s", request.META.get("REMOTE_ADDR"))
        messages.error(request, "Too many login attempts. Please wait 1 minute before trying again.")
        form = LoginForm()
        return render(request, "accounts/login.html", {"form": form}, status=429)

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            password = form.cleaned_data["password"]
            user = authenticate(request, email=email, password=password)

            if user is not None:
                login(request, user)
                security_logger.info("Successful login for user '%s' from IP %s", email, request.META.get("REMOTE_ADDR"))
                if not user.is_email_verified and not user.is_superuser:
                    request.session["pending_verification_email"] = user.email
                    return redirect("verification_sent")
                return redirect("dashboard")
            else:
                security_logger.warning("Failed login attempt for user '%s' from IP %s", email, request.META.get("REMOTE_ADDR"))
                messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    """
    Logs out the current user and redirects to login.
    """
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


@login_required
@email_verification_required
def dashboard_view(request):
    """
    Kinetiq CRM Dashboard:
    - Summary cards: Contacts, Open Deals & Pipeline, Deals Won, Tasks Overdue & Due Today
    - Charts: Pipeline by Stage (Bar), Deals Won per Month (Last 6 Months), Contacts by Status (Doughnut)
    - Recent Activity: Last 8 AuditLog entries in plain readable sentences
    - Filters: Date range (This month, Last 30 days, Last 6 months) & Owner/Admin team member filter
    - Today Box: Logged-in user's overdue and due-today tasks with one-tap completion
    - Central data-separation system: completely isolated by organization.
    """
    org = request.user.organization
    today = timezone.localdate()

    if not org:
        return render(request, "accounts/dashboard.html", {"organization": None})

    # 1. Date Range Filter
    period = request.GET.get("period", "this_month").strip().lower()
    if period not in ["this_month", "last_30_days", "last_6_months"]:
        period = "this_month"

    if period == "last_30_days":
        date_from = today - datetime.timedelta(days=30)
        period_label = "Last 30 days"
    elif period == "last_6_months":
        date_from = today - datetime.timedelta(days=180)
        period_label = "Last 6 months"
    else:  # this_month
        date_from = today.replace(day=1)
        period_label = "This month"

    date_to = today

    # 2. Team Member Filter
    is_admin_or_owner = request.user.is_admin_or_owner
    member_id = request.GET.get("member", "").strip()
    selected_member = None

    if is_admin_or_owner:
        if member_id and member_id != "all":
            selected_member = User.objects.filter(pk=member_id, organization=org).first()
    else:
        # Members see only their own numbers for deals and tasks, and the business-wide contact count
        selected_member = request.user

    team_members = User.objects.filter(organization=org, is_active=True).order_by("first_name", "last_name")

    # --------------------------------------------------------------------------
    # SUMMARY CARDS
    # --------------------------------------------------------------------------
    # 1. Contacts: Business-wide count (even for members)
    base_contacts = Contact.objects.filter(organization=org)
    total_contacts_count = base_contacts.count()
    new_contacts_count = base_contacts.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).count()

    # Base deals query (scoped to member if selected or if user is Member)
    deal_qs = Deal.objects.filter(organization=org)
    if selected_member:
        deal_qs = deal_qs.filter(owner=selected_member)

    # 2. Open deals count and total open pipeline value
    open_deals_qs = deal_qs.filter(stage__is_won=False, stage__is_lost=False)
    open_deals_agg = open_deals_qs.aggregate(
        count=Count("id"),
        total=Sum("value"),
    )
    open_deals_count = open_deals_agg["count"] or 0
    total_open_pipeline_value = open_deals_agg["total"] or Decimal("0.00")

    # 3. Deals won in selected period (count and value)
    won_deals_qs = deal_qs.filter(
        stage__is_won=True,
        closed_date__gte=date_from,
        closed_date__lte=date_to,
    )
    won_deals_agg = won_deals_qs.aggregate(
        count=Count("id"),
        total=Sum("value"),
    )
    deals_won_count = won_deals_agg["count"] or 0
    deals_won_value = won_deals_agg["total"] or Decimal("0.00")

    # 4. Tasks overdue and tasks due today
    task_qs = Task.objects.filter(organization=org, is_completed=False, due_date__isnull=False)
    if selected_member:
        task_qs = task_qs.filter(assigned_to=selected_member)

    tasks_overdue_count = task_qs.filter(due_date__lt=today).count()
    tasks_due_today_count = task_qs.filter(due_date=today).count()

    # --------------------------------------------------------------------------
    # CHARTS DATA (Chart.js)
    # --------------------------------------------------------------------------
    # Chart 1: Pipeline by stage (bar chart of deal value per stage)
    stages = Stage.objects.filter(organization=org).order_by("order", "id")
    stage_deals_agg = deal_qs.values("stage_id").annotate(total=Sum("value"))
    stage_value_map = {item["stage_id"]: float(item["total"] or 0) for item in stage_deals_agg}

    pipeline_chart_labels = []
    pipeline_chart_values = []
    pipeline_total_val = 0.0

    for stg in stages:
        val = stage_value_map.get(stg.id, 0.0)
        pipeline_chart_labels.append(stg.name)
        pipeline_chart_values.append(val)
        pipeline_total_val += val

    pipeline_has_data = pipeline_total_val > 0 or deal_qs.exists()

    # Chart 2: Deals won per month for the last 6 months (bar/line chart)
    cur_year = today.year
    cur_month = today.month
    month_buckets = []
    for i in range(5, -1, -1):
        m = cur_month - i
        y = cur_year
        while m <= 0:
            m += 12
            y -= 1
        first_day = datetime.date(y, m, 1)
        last_day_num = calendar.monthrange(y, m)[1]
        last_day = datetime.date(y, m, last_day_num)
        label = first_day.strftime("%b %Y")
        month_buckets.append((first_day, last_day, label))

    earliest_won_date = month_buckets[0][0]
    latest_won_date = month_buckets[-1][1]

    won_in_6m = deal_qs.filter(
        stage__is_won=True,
        closed_date__gte=earliest_won_date,
        closed_date__lte=latest_won_date,
    )
    won_by_month = won_in_6m.annotate(m=TruncMonth("closed_date")).values("m").annotate(
        total=Sum("value"),
        count=Count("id"),
    )
    won_month_map = {
        item["m"].strftime("%b %Y"): (float(item["total"] or 0), item["count"])
        for item in won_by_month
        if item["m"]
    }

    won_monthly_labels = []
    won_monthly_values = []
    won_monthly_counts = []
    won_has_data = False

    for first_day, last_day, label in month_buckets:
        val, cnt = won_month_map.get(label, (0.0, 0))
        won_monthly_labels.append(label)
        won_monthly_values.append(val)
        won_monthly_counts.append(cnt)
        if val > 0 or cnt > 0:
            won_has_data = True

    # Chart 3: Contacts by status (Lead, Customer, Inactive)
    contact_status_agg = base_contacts.values("status").annotate(count=Count("id"))
    status_count_map = {item["status"]: item["count"] for item in contact_status_agg}

    contacts_status_labels = ["Lead", "Customer", "Inactive"]
    contacts_status_values = [
        status_count_map.get("LEAD", 0),
        status_count_map.get("CUSTOMER", 0),
        status_count_map.get("INACTIVE", 0),
    ]
    contacts_has_data = total_contacts_count > 0

    # --------------------------------------------------------------------------
    # RECENT ACTIVITY (Last 8 AuditLog entries for this business)
    # --------------------------------------------------------------------------
    recent_activity = AuditLog.objects.filter(
        organization=org
    ).select_related("user").order_by("-created_at")[:8]

    # --------------------------------------------------------------------------
    # "TODAY" BOX (My overdue and due-today tasks with one-tap Mark Done)
    # --------------------------------------------------------------------------
    today_and_overdue_tasks = Task.objects.filter(
        organization=org,
        assigned_to=request.user,
        is_completed=False,
        due_date__isnull=False,
        due_date__lte=today,
    ).select_related("contact", "deal").order_by("due_date", "due_time")

    # PayPal Invoicing metrics (business-scoped)
    inv_qs = Invoice.objects.filter(organization=org)
    active_inv = inv_qs.exclude(status__in=["CANCELLED", "REFUNDED"])
    paid_inv = inv_qs.filter(status__in=["PAID", "MARKED_AS_PAID"])
    awaiting_inv = inv_qs.filter(status__in=["SENT", "UNPAID", "PAYMENT_PENDING", "DRAFT"])

    invoices_total_amount = active_inv.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    invoices_total_count = active_inv.count()

    invoices_paid_amount = paid_inv.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    invoices_paid_count = paid_inv.count()

    invoices_awaiting_amount = awaiting_inv.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    invoices_awaiting_count = awaiting_inv.count()

    currency_totals = list(
        active_inv.values("currency").annotate(
            total_invoiced=Sum("amount"),
            total_count=Count("id")
        ).order_by("-total_invoiced")
    )

    return render(
        request,
        "accounts/dashboard.html",
        {
            "organization": org,
            "period": period,
            "period_label": period_label,
            "selected_member": selected_member,
            "selected_member_id": str(selected_member.id) if selected_member else "",
            "team_members": team_members,
            "is_admin_or_owner": is_admin_or_owner,
            # Invoicing Summary Cards (PayPal)
            "invoices_total_amount": invoices_total_amount,
            "invoices_total_count": invoices_total_count,
            "invoices_paid_amount": invoices_paid_amount,
            "invoices_paid_count": invoices_paid_count,
            "invoices_awaiting_amount": invoices_awaiting_amount,
            "invoices_awaiting_count": invoices_awaiting_count,
            "currency_totals": currency_totals,
            # Summary Cards
            "total_contacts_count": total_contacts_count,
            "new_contacts_count": new_contacts_count,
            "open_deals_count": open_deals_count,
            "total_open_pipeline_value": total_open_pipeline_value,
            "deals_won_count": deals_won_count,
            "deals_won_value": deals_won_value,
            "tasks_overdue_count": tasks_overdue_count,
            "tasks_due_today_count": tasks_due_today_count,
            # Charts
            "pipeline_chart_labels": pipeline_chart_labels,
            "pipeline_chart_values": pipeline_chart_values,
            "pipeline_has_data": pipeline_has_data,
            "won_monthly_labels": won_monthly_labels,
            "won_monthly_values": won_monthly_values,
            "won_monthly_counts": won_monthly_counts,
            "won_has_data": won_has_data,
            "contacts_status_labels": contacts_status_labels,
            "contacts_status_values": contacts_status_values,
            "contacts_has_data": contacts_has_data,
            # Recent Activity
            "recent_activity": recent_activity,
            # Today Box
            "today_and_overdue_tasks": today_and_overdue_tasks,
            "today": today,
        },
    )


@login_required
@email_verification_required
@admin_or_owner_required
def team_list_view(request):
    """
    Team management view: lists team members and pending invites;
    allows inviting new members.
    """
    org = request.user.organization
    members = org.users.all().order_by("-created_at")
    pending_invites = org.invitations.filter(is_accepted=False).order_by("-created_at")

    if request.method == "POST":
        form = TeamInviteForm(request.POST, organization=org)
        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.organization = org
            invitation.invited_by = request.user
            invitation.save()

            send_invitation_email(request, invitation)
            messages.success(request, f"Invitation sent to {invitation.email}.")
            return redirect("team_list")
    else:
        form = TeamInviteForm(organization=org)

    return render(
        request,
        "accounts/team.html",
        {
            "members": members,
            "pending_invites": pending_invites,
            "form": form,
        },
    )


def accept_invite_view(request, token):
    """
    Allows an invited team member to join the existing organization.
    Rejects expired (older than 7 days) or already-accepted tokens.
    """
    invitation = TeamInvitation.objects.filter(token=token).first()

    if not invitation or not invitation.is_valid:
        return render(
            request,
            "accounts/invite_invalid.html",
            {"message": "This invitation link is invalid or has expired (invitations expire after 7 days)."},
            status=400,
        )

    if request.method == "POST":
        form = AcceptInviteForm(request.POST)
        if form.is_valid():
            # Check if email is already taken
            if User.objects.filter(email=invitation.email).exists():
                messages.error(request, "An account with this email already exists.")
                return redirect("login")

            # Create new user in the SAME organization with the invited role
            user = User.objects.create_user(
                email=invitation.email,
                password=form.cleaned_data["password"],
                first_name=form.cleaned_data["first_name"].strip(),
                last_name=form.cleaned_data["last_name"].strip(),
                organization=invitation.organization,
                role=invitation.role,
                is_email_verified=True,
            )

            # Mark invitation accepted
            invitation.is_accepted = True
            invitation.save()

            login(request, user)
            messages.success(request, f"Welcome to {invitation.organization.name}!")
            return redirect("dashboard")
    else:
        form = AcceptInviteForm()

    return render(
        request,
        "accounts/accept_invite.html",
        {
            "invitation": invitation,
            "form": form,
        },
    )
