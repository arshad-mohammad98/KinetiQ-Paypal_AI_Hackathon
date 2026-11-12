import csv
import io
import logging
import zipfile
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import EmailValidator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import admin_or_owner_required, email_verification_required
from .csv_utils import (
    decode_csv_file,
    sanitize_export_cell,
    sanitize_import_cell,
    stream_csv_response,
)
from .forms import CompanyForm, ContactForm, ContactNoteForm, DealForm, TaskForm
from .models import Company, Contact, ContactNote, Deal, Stage, Task
from .signals import create_default_stages_for_org
from .utils import log_audit

User = get_user_model()
security_logger = logging.getLogger("kinetiq.security")

# ==============================================================================
# COMPANIES MODULE
# ==============================================================================

@login_required
@email_verification_required
def company_list_view(request):
    org = request.user.organization
    query = request.GET.get("q", "").strip()

    companies = Company.objects.filter(organization=org)
    if query:
        companies = companies.filter(
            Q(name__icontains=query) |
            Q(industry__icontains=query) |
            Q(city__icontains=query) |
            Q(phone__icontains=query)
        )

    paginator = Paginator(companies.order_by("name"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "crm_core/company_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "total_count": companies.count(),
        },
    )


@login_required
@email_verification_required
def company_create_view(request):
    org = request.user.organization

    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save(commit=False)
            company.organization = org
            company.created_by = request.user
            company.save()

            log_audit(request, "CREATE", company)
            messages.success(request, f"Company '{company.name}' created successfully.")
            return redirect("company_detail", pk=company.pk)
    else:
        form = CompanyForm()

    return render(request, "crm_core/company_form.html", {"form": form, "title": "Add Company"})


@login_required
@email_verification_required
def company_detail_view(request, pk):
    org = request.user.organization
    company = get_object_or_404(Company, pk=pk, organization=org)
    contacts = company.contacts.filter(organization=org).select_related("owner")

    return render(
        request,
        "crm_core/company_detail.html",
        {
            "company": company,
            "contacts": contacts,
        },
    )


@login_required
@email_verification_required
def company_update_view(request, pk):
    org = request.user.organization
    company = get_object_or_404(Company, pk=pk, organization=org)

    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            company = form.save()
            log_audit(request, "UPDATE", company)
            messages.success(request, f"Company '{company.name}' updated successfully.")
            return redirect("company_detail", pk=company.pk)
    else:
        form = CompanyForm(instance=company)

    return render(
        request,
        "crm_core/company_form.html",
        {"form": form, "company": company, "title": f"Edit {company.name}"},
    )


@login_required
@email_verification_required
@admin_or_owner_required
def company_delete_view(request, pk):
    org = request.user.organization
    company = get_object_or_404(Company, pk=pk, organization=org)

    if request.method == "POST":
        company_name = company.name
        log_audit(request, "DELETE", company, description=f"Deleted company: {company_name}")
        company.delete()
        messages.success(request, f"Company '{company_name}' has been deleted.")
        return redirect("company_list")

    return render(request, "crm_core/confirm_delete.html", {"object": company, "type": "Company"})


# ==============================================================================
# CONTACTS MODULE
# ==============================================================================

@login_required
@email_verification_required
def contact_list_view(request):
    org = request.user.organization
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    company_filter = request.GET.get("company", "").strip()
    owner_filter = request.GET.get("owner", "").strip()

    contacts = Contact.objects.filter(organization=org).select_related("company", "owner")

    if query:
        contacts = contacts.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(job_title__icontains=query)
        )

    if status_filter:
        contacts = contacts.filter(status=status_filter)
    if company_filter:
        contacts = contacts.filter(company_id=company_filter)
    if owner_filter:
        contacts = contacts.filter(owner_id=owner_filter)

    paginator = Paginator(contacts.order_by("first_name", "last_name"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Filter options scoped to organization
    companies = Company.objects.filter(organization=org).order_by("name")
    team_members = User.objects.filter(organization=org, is_active=True).order_by("first_name")

    return render(
        request,
        "crm_core/contact_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "status_filter": status_filter,
            "company_filter": company_filter,
            "owner_filter": owner_filter,
            "companies": companies,
            "team_members": team_members,
            "total_count": contacts.count(),
        },
    )


@login_required
@email_verification_required
def contact_create_view(request):
    org = request.user.organization
    prefill_company = request.GET.get("company_id")

    if request.method == "POST":
        form = ContactForm(request.POST, organization=org)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.organization = org
            contact.created_by = request.user
            contact.save()

            # Duplicate email warning (non-blocking)
            duplicate_exists = Contact.objects.filter(
                organization=org,
                email__iexact=contact.email
            ).exclude(pk=contact.pk).exists()

            if duplicate_exists:
                messages.warning(
                    request,
                    f"Notice: Another contact in your organization already has the email '{contact.email}'."
                )

            log_audit(request, "CREATE", contact)
            messages.success(request, f"Contact '{contact.full_name}' created successfully.")
            return redirect("contact_detail", pk=contact.pk)
    else:
        initial = {}
        if prefill_company:
            initial["company"] = prefill_company
        form = ContactForm(organization=org, initial=initial)

    return render(request, "crm_core/contact_form.html", {"form": form, "title": "Add Contact"})


@login_required
@email_verification_required
def contact_detail_view(request, pk):
    org = request.user.organization
    contact = get_object_or_404(Contact, pk=pk, organization=org)
    notes = contact.notes.filter(organization=org).select_related("author").order_by("-created_at")
    deals = contact.deals.filter(organization=org).select_related("stage", "owner").order_by("-created_at")
    tasks = contact.tasks.filter(organization=org).select_related("assigned_to", "deal").order_by("is_completed", "due_date")

    if request.method == "POST":
        note_form = ContactNoteForm(request.POST)
        if note_form.is_valid():
            note = note_form.save(commit=False)
            note.organization = org
            note.contact = contact
            note.author = request.user
            note.save()

            log_audit(request, "CREATE", note, description=f"Added note on {contact.full_name}")
            messages.success(request, "Note added to timeline.")
            return redirect("contact_detail", pk=contact.pk)
    else:
        note_form = ContactNoteForm()

    return render(
        request,
        "crm_core/contact_detail.html",
        {
            "contact": contact,
            "notes": notes,
            "note_form": note_form,
            "deals": deals,
            "tasks": tasks,
        },
    )


@login_required
@email_verification_required
def contact_update_view(request, pk):
    org = request.user.organization
    contact = get_object_or_404(Contact, pk=pk, organization=org)

    if request.method == "POST":
        form = ContactForm(request.POST, instance=contact, organization=org)
        if form.is_valid():
            contact = form.save()

            # Duplicate email check
            duplicate_exists = Contact.objects.filter(
                organization=org,
                email__iexact=contact.email
            ).exclude(pk=contact.pk).exists()

            if duplicate_exists:
                messages.warning(
                    request,
                    f"Notice: Another contact in your organization already has the email '{contact.email}'."
                )

            log_audit(request, "UPDATE", contact)
            messages.success(request, f"Contact '{contact.full_name}' updated successfully.")
            return redirect("contact_detail", pk=contact.pk)
    else:
        form = ContactForm(instance=contact, organization=org)

    return render(
        request,
        "crm_core/contact_form.html",
        {"form": form, "contact": contact, "title": f"Edit {contact.full_name}"},
    )


@login_required
@email_verification_required
@admin_or_owner_required
def contact_delete_view(request, pk):
    org = request.user.organization
    contact = get_object_or_404(Contact, pk=pk, organization=org)

    if request.method == "POST":
        contact_name = contact.full_name
        log_audit(request, "DELETE", contact, description=f"Deleted contact: {contact_name}")
        contact.delete()
        messages.success(request, f"Contact '{contact_name}' has been deleted.")
        return redirect("contact_list")

    return render(request, "crm_core/confirm_delete.html", {"object": contact, "type": "Contact"})


# ==============================================================================
# DEALS PIPELINE MODULE
# ==============================================================================

@login_required
@email_verification_required
def deal_board_view(request):
    """
    Renders the Deals Pipeline Kanban board with one column per stage.
    Displays deal count and total value per column, top-level metrics, and owner filter.
    """
    org = request.user.organization

    # Ensure default stages exist for this organization
    stages = Stage.objects.filter(organization=org).order_by("order")
    if not stages.exists():
        create_default_stages_for_org(org)
        stages = Stage.objects.filter(organization=org).order_by("order")

    owner_filter = request.GET.get("owner", "").strip()
    deals = Deal.objects.filter(organization=org).select_related("contact", "company", "stage", "owner")

    if owner_filter:
        if owner_filter == "unassigned":
            deals = deals.filter(owner__isnull=True)
        else:
            deals = deals.filter(owner_id=owner_filter)

    # Top-of-board metrics
    now = timezone.now()
    # Total open pipeline value (stages not marked Won or Lost)
    open_deals = deals.filter(stage__is_won=False, stage__is_lost=False).exclude(
        stage__name__in=["Won", "Lost", "won", "lost"]
    )
    total_open_pipeline_value = open_deals.aggregate(total=Sum("value"))["total"] or Decimal("0.00")

    # Number of deals won this month
    won_deals = deals.filter(Q(stage__is_won=True) | Q(stage__name__iexact="Won"))
    won_this_month = won_deals.filter(
        Q(closed_date__year=now.year, closed_date__month=now.month) |
        Q(closed_date__isnull=True, updated_at__year=now.year, updated_at__month=now.month)
    ).count()

    # Build stage columns with deal count and total value
    columns = []
    deals_list = list(deals)
    for stage in stages:
        stage_deals = [d for d in deals_list if d.stage_id == stage.id]
        stage_total_value = sum((d.value for d in stage_deals), Decimal("0.00"))
        columns.append({
            "stage": stage,
            "deals": stage_deals,
            "count": len(stage_deals),
            "total_value": stage_total_value,
        })

    team_members = User.objects.filter(organization=org, is_active=True).order_by("first_name", "last_name")
    total_deals_count = Deal.objects.filter(organization=org).count()

    return render(
        request,
        "crm_core/deal_board.html",
        {
            "columns": columns,
            "stages": stages,
            "total_open_pipeline_value": total_open_pipeline_value,
            "won_this_month": won_this_month,
            "team_members": team_members,
            "owner_filter": owner_filter,
            "total_deals_count": total_deals_count,
            "filtered_deals_count": len(deals_list),
        },
    )


@login_required
@email_verification_required
def deal_create_view(request):
    """
    Creates a new Deal. Owner, Admin, and Member can add deals.
    Pre-selects contact when 'contact_id' is provided.
    """
    org = request.user.organization
    prefill_contact = request.GET.get("contact_id")

    if request.method == "POST":
        form = DealForm(request.POST, organization=org)
        if form.is_valid():
            deal = form.save(commit=False)
            deal.organization = org
            deal.save()

            log_audit(request, "CREATE", deal, description=f"Created deal '{deal.title}'")
            messages.success(request, f"Deal '{deal.title}' created successfully.")
            return redirect("deal_board")
    else:
        initial = {}
        if prefill_contact:
            if Contact.objects.filter(pk=prefill_contact, organization=org).exists():
                initial["contact"] = prefill_contact
        form = DealForm(organization=org, initial=initial)

    return render(request, "crm_core/deal_form.html", {"form": form, "title": "Add Deal"})


@login_required
@email_verification_required
def deal_detail_view(request, pk):
    """
    Detail view for a Deal. Tapping a card opens the deal for editing.
    """
    org = request.user.organization
    deal = get_object_or_404(Deal, pk=pk, organization=org)
    return redirect("deal_update", pk=deal.pk)


@login_required
@email_verification_required
def deal_update_view(request, pk):
    """
    Updates an existing Deal. Owner, Admin, and Member can edit deals.
    """
    org = request.user.organization
    deal = get_object_or_404(Deal, pk=pk, organization=org)

    if request.method == "POST":
        form = DealForm(request.POST, instance=deal, organization=org)
        if form.is_valid():
            deal = form.save()
            log_audit(request, "UPDATE", deal, description=f"Updated deal '{deal.title}'")
            messages.success(request, f"Deal '{deal.title}' updated successfully.")
            return redirect("deal_board")
    else:
        form = DealForm(instance=deal, organization=org)

    tasks = deal.tasks.filter(organization=org).select_related("assigned_to", "contact").order_by("is_completed", "due_date")
    invoice = deal.invoices.filter(organization=org).first()
    is_won = bool(deal.stage and deal.stage.is_won)
    from payments.paypal import is_paypal_configured
    paypal_configured = is_paypal_configured()

    return render(
        request,
        "crm_core/deal_form.html",
        {
            "form": form,
            "deal": deal,
            "title": f"Edit {deal.title}",
            "tasks": tasks,
            "invoice": invoice,
            "is_won": is_won,
            "paypal_configured": paypal_configured,
        },
    )


@login_required
@email_verification_required
@admin_or_owner_required
def deal_delete_view(request, pk):
    """
    Deletes a Deal. Only Owner and Admin can delete, with confirmation.
    """
    org = request.user.organization
    deal = get_object_or_404(Deal, pk=pk, organization=org)

    if request.method == "POST":
        deal_title = deal.title
        log_audit(request, "DELETE", deal, description=f"Deleted deal: {deal_title}")
        deal.delete()
        messages.success(request, f"Deal '{deal_title}' has been deleted.")
        return redirect("deal_board")

    return render(request, "crm_core/confirm_delete.html", {"object": deal, "type": "Deal"})


@login_required
@email_verification_required
def deal_move_view(request, pk):
    """
    Moves a deal to a target stage.
    Supports desktop drag-and-drop (Fetch/AJAX) and phone/touch modal form submit.
    Strictly enforces tenant isolation: both Deal and Stage must belong to the user's business.
    """
    org = request.user.organization
    deal = get_object_or_404(Deal, pk=pk, organization=org)

    if request.method == "POST":
        stage_id = request.POST.get("stage_id")
        if not stage_id:
            try:
                import json
                data = json.loads(request.body.decode("utf-8"))
                stage_id = data.get("stage_id")
            except Exception:
                stage_id = None

        if not stage_id:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": "Stage ID is required."}, status=400)
            messages.error(request, "Please choose a valid stage.")
            return redirect("deal_board")

        # Crucial cross-tenant check: Stage MUST belong to user's organization!
        new_stage = get_object_or_404(Stage, pk=stage_id, organization=org)

        old_stage_name = deal.stage.name if deal.stage else "None"
        deal.stage = new_stage
        deal.save()

        log_audit(
            request,
            "MOVE",
            deal,
            description=f"Moved deal '{deal.title}' from '{old_stage_name}' to '{new_stage.name}'",
        )

        if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.content_type == "application/json":
            return JsonResponse({
                "success": True,
                "deal_id": deal.pk,
                "stage_id": new_stage.pk,
                "stage_name": new_stage.name,
                "closed_date": str(deal.closed_date) if deal.closed_date else None,
            })

        messages.success(request, f"Deal '{deal.title}' moved to {new_stage.name}.")
        return redirect("deal_board")

    return redirect("deal_update", pk=deal.pk)


# ==============================================================================
# TASKS & REMINDERS MODULE
# ==============================================================================

@login_required
@email_verification_required
def task_list_view(request):
    """
    Renders the tasks list view with tabs (My, All, Overdue, Today, Upcoming, Done),
    search box, filter by assigned person and type, and pagination.
    """
    org = request.user.organization
    today = timezone.localdate()
    tab = request.GET.get("tab", "my").strip()
    query = request.GET.get("q", "").strip()
    assigned_filter = request.GET.get("assigned", "").strip()
    type_filter = request.GET.get("type", "").strip()

    base_qs = Task.objects.filter(organization=org).select_related(
        "contact", "deal", "assigned_to", "created_by"
    )

    # Calculate counts for each tab
    my_tasks_count = base_qs.filter(assigned_to=request.user, is_completed=False).count()
    all_tasks_count = base_qs.filter(is_completed=False).count()
    overdue_count = base_qs.filter(is_completed=False, due_date__lt=today).count()
    today_count = base_qs.filter(is_completed=False, due_date=today).count()
    upcoming_count = base_qs.filter(is_completed=False, due_date__gt=today).count()
    done_count = base_qs.filter(is_completed=True).count()

    # Apply tab filter
    if tab == "all":
        tasks = base_qs.filter(is_completed=False)
    elif tab == "overdue":
        tasks = base_qs.filter(is_completed=False, due_date__lt=today)
    elif tab == "today":
        tasks = base_qs.filter(is_completed=False, due_date=today)
    elif tab == "upcoming":
        tasks = base_qs.filter(is_completed=False, due_date__gt=today)
    elif tab == "done":
        tasks = base_qs.filter(is_completed=True)
    else:
        tab = "my"
        tasks = base_qs.filter(assigned_to=request.user, is_completed=False)

    # Search filter
    if query:
        tasks = tasks.filter(
            Q(title__icontains=query) |
            Q(notes__icontains=query) |
            Q(contact__first_name__icontains=query) |
            Q(contact__last_name__icontains=query) |
            Q(deal__title__icontains=query)
        )

    # Filter by assigned person
    if assigned_filter == "unassigned":
        tasks = tasks.filter(assigned_to__isnull=True)
    elif assigned_filter:
        tasks = tasks.filter(assigned_to_id=assigned_filter)

    # Filter by task type
    if type_filter:
        tasks = tasks.filter(task_type=type_filter)

    # Order
    if tab == "done":
        tasks = tasks.order_by("-completed_at", "-updated_at")
    else:
        tasks = tasks.order_by("due_date", "due_time", "-created_at")

    paginator = Paginator(tasks, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    team_members = User.objects.filter(organization=org, is_active=True).order_by("first_name", "last_name")

    return render(
        request,
        "crm_core/task_list.html",
        {
            "page_obj": page_obj,
            "tab": tab,
            "query": query,
            "assigned_filter": assigned_filter,
            "type_filter": type_filter,
            "team_members": team_members,
            "task_types": Task.TYPE_CHOICES,
            "today": today,
            "my_tasks_count": my_tasks_count,
            "all_tasks_count": all_tasks_count,
            "overdue_count": overdue_count,
            "today_count": today_count,
            "upcoming_count": upcoming_count,
            "done_count": done_count,
            "total_count": tasks.count(),
        },
    )


@login_required
@email_verification_required
def task_create_view(request):
    """
    Creates a new Task. Owner, Admin, and Member can add tasks.
    Pre-selects contact or deal if query params are provided.
    """
    org = request.user.organization
    prefill_contact = request.GET.get("contact_id")
    prefill_deal = request.GET.get("deal_id")

    if request.method == "POST":
        form = TaskForm(request.POST, organization=org)
        if form.is_valid():
            task = form.save(commit=False)
            task.organization = org
            task.created_by = request.user
            task.save()

            log_audit(request, "CREATE", task, description=f"Created task '{task.title}'")
            messages.success(request, f"Task '{task.title}' created.")
            return redirect("task_list")
    else:
        initial = {}
        if prefill_contact:
            if Contact.objects.filter(pk=prefill_contact, organization=org).exists():
                initial["contact"] = prefill_contact
        if prefill_deal:
            deal = Deal.objects.filter(pk=prefill_deal, organization=org).first()
            if deal:
                initial["deal"] = deal.pk
                if deal.contact_id:
                    initial["contact"] = deal.contact_id

        # Default assignment to current user
        initial.setdefault("assigned_to", request.user.pk)
        form = TaskForm(organization=org, initial=initial)

    return render(request, "crm_core/task_form.html", {"form": form, "title": "Add Task"})


@login_required
@email_verification_required
def task_update_view(request, pk):
    """
    Updates an existing Task. Owner and Admin can edit all tasks.
    A Member can edit tasks assigned to them or created by them.
    """
    org = request.user.organization
    task = get_object_or_404(Task, pk=pk, organization=org)

    # Permission check for Member
    if not (request.user.is_admin_or_owner or task.assigned_to_id == request.user.id or task.created_by_id == request.user.id):
        messages.error(request, "You can only edit tasks assigned to you or created by you.")
        return redirect("task_list")

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, organization=org)
        if form.is_valid():
            task = form.save()
            log_audit(request, "UPDATE", task, description=f"Updated task '{task.title}'")
            messages.success(request, f"Task '{task.title}' updated.")
            return redirect("task_list")
    else:
        form = TaskForm(instance=task, organization=org)

    return render(
        request,
        "crm_core/task_form.html",
        {"form": form, "task": task, "title": f"Edit {task.title}"},
    )


@login_required
@email_verification_required
def task_toggle_done_view(request, pk):
    """
    Marks a task done or undoes completion.
    A Member can complete tasks assigned to them or created by them.
    Owner and Admin can complete all tasks.
    """
    org = request.user.organization
    task = get_object_or_404(Task, pk=pk, organization=org)

    # Permission check for Member
    if not (request.user.is_admin_or_owner or task.assigned_to_id == request.user.id or task.created_by_id == request.user.id):
        messages.error(request, "You can only complete tasks assigned to you or created by you.")
        return redirect("task_list")

    if request.method == "POST":
        if task.is_completed:
            task.is_completed = False
            task.completed_at = None
            task.completed_by = None
            task.save()
            log_audit(request, "UPDATE", task, description=f"Undid completion of task '{task.title}'")
            messages.success(request, f"Task '{task.title}' marked as incomplete.")
        else:
            task.is_completed = True
            task.completed_at = timezone.now()
            task.completed_by = request.user
            task.save()
            log_audit(request, "COMPLETE", task, description=f"Completed task '{task.title}'")
            messages.success(request, f"Task '{task.title}' marked as done!")

    return redirect(request.META.get("HTTP_REFERER") or "task_list")


@login_required
@email_verification_required
@admin_or_owner_required
def task_delete_view(request, pk):
    """
    Deletes a Task. Only Owner and Admin can delete, with confirmation.
    """
    org = request.user.organization
    task = get_object_or_404(Task, pk=pk, organization=org)

    if request.method == "POST":
        task_title = task.title
        log_audit(request, "DELETE", task, description=f"Deleted task: {task_title}")
        task.delete()
        messages.success(request, f"Task '{task_title}' has been deleted.")
        return redirect("task_list")

    return render(request, "crm_core/confirm_delete.html", {"object": task, "type": "Task"})


# ==============================================================================
# IMPORT & EXPORT MODULE
# ==============================================================================

MAX_CSV_FILE_SIZE = 2 * 1024 * 1024  # 2 MB limit
MAX_CSV_ROW_COUNT = 5000            # 5,000 rows limit


# ------------------------------------------------------------------------------
# COMPANY IMPORT & EXPORT
# ------------------------------------------------------------------------------

@login_required
@email_verification_required
@admin_or_owner_required
def company_import_view(request):
    """
    Imports Companies from a CSV file (Owner and Admin only).
    Columns: name (required), industry, website, city, phone.
    Skips rows whose name already exists in the business (case-insensitive).
    Runs in one atomic transaction so failures/crashes never leave partial data.
    """
    org = request.user.organization

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "Please select a .csv file to upload.")
            return render(request, "crm_core/company_import.html")

        if not uploaded_file.name.lower().endswith(".csv"):
            messages.error(request, "Invalid file format. Only .csv files are accepted.")
            return render(request, "crm_core/company_import.html")

        if uploaded_file.size > MAX_CSV_FILE_SIZE:
            messages.error(request, "File exceeds the 2 MB limit. Please upload a smaller CSV file.")
            return render(request, "crm_core/company_import.html")

        try:
            content = decode_csv_file(uploaded_file)
        except Exception as e:
            messages.error(request, f"Unable to read file: {e}")
            return render(request, "crm_core/company_import.html")

        reader = csv.reader(io.StringIO(content))
        try:
            headers = next(reader)
        except StopIteration:
            messages.error(request, "The CSV file is completely empty.")
            return render(request, "crm_core/company_import.html")

        header_map = {h.strip().lower(): i for i, h in enumerate(headers)}
        if "name" not in header_map:
            messages.error(request, "Missing required column: 'name' must be present in the CSV header.")
            return render(request, "crm_core/company_import.html")

        imported_count = 0
        skipped_count = 0
        failures = []

        try:
            with transaction.atomic():
                row_idx = 1  # Header was row 1
                for row in reader:
                    row_idx += 1
                    if row_idx - 1 > MAX_CSV_ROW_COUNT:
                        messages.error(request, f"File exceeds maximum allowed limit of {MAX_CSV_ROW_COUNT} rows.")
                        return render(request, "crm_core/company_import.html")

                    # Skip entirely empty trailing rows
                    if not any(field.strip() for field in row):
                        continue

                    def get_col(col_name):
                        idx = header_map.get(col_name)
                        return row[idx].strip() if idx is not None and idx < len(row) else ""

                    name = sanitize_import_cell(get_col("name"))
                    industry = sanitize_import_cell(get_col("industry"))
                    website = sanitize_import_cell(get_col("website"))
                    city = sanitize_import_cell(get_col("city"))
                    phone = sanitize_import_cell(get_col("phone"))

                    if not name:
                        failures.append({
                            "row": row_idx,
                            "reason": "Company name is required.",
                            "data": [name, industry, website, city, phone],
                        })
                        continue

                    # Check duplicate within the business
                    if Company.objects.filter(organization=org, name__iexact=name).exists():
                        skipped_count += 1
                        continue

                    Company.objects.create(
                        organization=org,
                        name=name,
                        industry=industry,
                        website=website,
                        city=city,
                        phone=phone,
                        created_by=request.user,
                    )
                    imported_count += 1

                # If all rows processed without crash, log audit
                log_audit(
                    request,
                    "IMPORT",
                    target_model="Company",
                    description=f"Imported {imported_count} companies from CSV ({skipped_count} skipped duplicates, {len(failures)} failed)",
                )

        except Exception as e:
            messages.error(request, f"Import process failed: {e}. No records were saved.")
            return render(request, "crm_core/company_import.html")

        request.session["company_failed_rows"] = failures

        return render(
            request,
            "crm_core/import_result.html",
            {
                "type": "Companies",
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "failed_count": len(failures),
                "failures": failures,
                "download_failed_url": reverse("company_import_failed_csv"),
                "back_url": reverse("company_list"),
            },
        )

    return render(request, "crm_core/company_import.html")


@login_required
@email_verification_required
@admin_or_owner_required
def company_sample_csv_view(request):
    """
    Downloads a sample CSV file with exact columns for company imports.
    """
    headers = ["name", "industry", "website", "city", "phone"]
    sample_rows = [
        ["Acme Technologies", "Software", "https://acme.example.com", "Bengaluru", "+91 98765 43210"],
        ["Apex Retailers", "Retail", "https://apex.example.com", "Mumbai", "+91 91234 56789"],
    ]
    return stream_csv_response("companies_sample.csv", headers, sample_rows)


@login_required
@email_verification_required
@admin_or_owner_required
def company_import_failed_csv_view(request):
    """
    Downloads failed company rows from the last import session with error reasons.
    """
    failed_rows = request.session.get("company_failed_rows", [])
    headers = ["name", "industry", "website", "city", "phone", "Error Reason", "CSV Row Number"]

    def row_generator():
        for item in failed_rows:
            data = item.get("data", ["", "", "", "", ""])
            # Pad data to 5 columns if necessary
            data = list(data) + [""] * (5 - len(data))
            yield data[:5] + [item.get("reason", ""), item.get("row", "")]

    return stream_csv_response("failed_companies.csv", headers, row_generator())


@login_required
@email_verification_required
@admin_or_owner_required
def company_export_view(request):
    """
    Exports filtered Companies matching search queries to a streamed CSV file.
    """
    org = request.user.organization
    query = request.GET.get("q", "").strip()

    companies = Company.objects.filter(organization=org)
    if query:
        companies = companies.filter(
            Q(name__icontains=query) |
            Q(industry__icontains=query) |
            Q(city__icontains=query) |
            Q(phone__icontains=query)
        )
    companies = companies.order_by("name")

    count = companies.count()
    log_audit(
        request,
        "EXPORT",
        target_model="Company",
        description=f"Exported {count} companies to CSV (Filter: '{query or 'All'}')",
    )

    headers = ["Name", "Industry", "Website", "City", "Phone", "Address", "Created At"]

    def row_generator():
        for comp in companies.iterator(chunk_size=500):
            yield [
                comp.name,
                comp.industry,
                comp.website,
                comp.city,
                comp.phone,
                comp.address,
                comp.created_at.strftime("%Y-%m-%d %H:%M:%S") if comp.created_at else "",
            ]

    timestamp = timezone.localdate().strftime("%Y%m%d")
    return stream_csv_response(f"companies_export_{timestamp}.csv", headers, row_generator())


# ------------------------------------------------------------------------------
# CONTACT IMPORT & EXPORT
# ------------------------------------------------------------------------------

@login_required
@email_verification_required
@admin_or_owner_required
def contact_import_view(request):
    """
    Imports Contacts from a CSV file (Owner and Admin only).
    Columns: name (required), email, phone, job_title, company, status (Lead, Customer, Inactive; default Lead).
    The company column is matched by name (ignoring capital letters) within the same business. If it does not exist, creates it.
    Skips rows whose email already exists in the business.
    Imported contacts get the importing user as owner.
    Runs in one atomic transaction so crashes never leave half-imported data.
    """
    org = request.user.organization
    validator = EmailValidator()

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "Please select a .csv file to upload.")
            return render(request, "crm_core/contact_import.html")

        if not uploaded_file.name.lower().endswith(".csv"):
            messages.error(request, "Invalid file format. Only .csv files are accepted.")
            return render(request, "crm_core/contact_import.html")

        if uploaded_file.size > MAX_CSV_FILE_SIZE:
            messages.error(request, "File exceeds the 2 MB limit. Please upload a smaller CSV file.")
            return render(request, "crm_core/contact_import.html")

        try:
            content = decode_csv_file(uploaded_file)
        except Exception as e:
            messages.error(request, f"Unable to read file: {e}")
            return render(request, "crm_core/contact_import.html")

        reader = csv.reader(io.StringIO(content))
        try:
            headers = next(reader)
        except StopIteration:
            messages.error(request, "The CSV file is completely empty.")
            return render(request, "crm_core/contact_import.html")

        header_map = {h.strip().lower(): i for i, h in enumerate(headers)}
        if "name" not in header_map:
            messages.error(request, "Missing required column: 'name' must be present in the CSV header.")
            return render(request, "crm_core/contact_import.html")

        imported_count = 0
        skipped_count = 0
        failures = []

        try:
            with transaction.atomic():
                row_idx = 1
                for row in reader:
                    row_idx += 1
                    if row_idx - 1 > MAX_CSV_ROW_COUNT:
                        messages.error(request, f"File exceeds maximum allowed limit of {MAX_CSV_ROW_COUNT} rows.")
                        return render(request, "crm_core/contact_import.html")

                    if not any(field.strip() for field in row):
                        continue

                    def get_col(col_name):
                        idx = header_map.get(col_name)
                        return row[idx].strip() if idx is not None and idx < len(row) else ""

                    name = sanitize_import_cell(get_col("name"))
                    email = sanitize_import_cell(get_col("email"))
                    phone = sanitize_import_cell(get_col("phone"))
                    job_title = sanitize_import_cell(get_col("job_title"))
                    company_name = sanitize_import_cell(get_col("company"))
                    status_raw = sanitize_import_cell(get_col("status"))

                    # Validation 1: Required name
                    if not name:
                        failures.append({
                            "row": row_idx,
                            "reason": "Contact name is required.",
                            "data": [name, email, phone, job_title, company_name, status_raw],
                        })
                        continue

                    # Validation 2: Email format & duplicate check
                    if email:
                        try:
                            validator(email)
                        except ValidationError:
                            failures.append({
                                "row": row_idx,
                                "reason": f"Invalid email format: '{email}'.",
                                "data": [name, email, phone, job_title, company_name, status_raw],
                            })
                            continue

                        if Contact.objects.filter(organization=org, email__iexact=email).exists():
                            skipped_count += 1
                            continue

                    # Validation 3: Status check
                    if not status_raw:
                        status = "LEAD"
                    else:
                        status_norm = status_raw.upper()
                        if status_norm in ["LEAD", "CUSTOMER", "INACTIVE"]:
                            status = status_norm
                        else:
                            failures.append({
                                "row": row_idx,
                                "reason": f"Invalid status: '{status_raw}'. Must be Lead, Customer, or Inactive.",
                                "data": [name, email, phone, job_title, company_name, status_raw],
                            })
                            continue

                    # Company matching (case-insensitive in the same business; create if not found)
                    company_obj = None
                    if company_name:
                        company_obj = Company.objects.filter(organization=org, name__iexact=company_name).first()
                        if not company_obj:
                            company_obj = Company.objects.create(
                                organization=org,
                                name=company_name,
                                created_by=request.user,
                            )

                    # Split name into first and last name
                    name_parts = name.split(None, 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

                    Contact.objects.create(
                        organization=org,
                        company=company_obj,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone=phone,
                        job_title=job_title,
                        status=status,
                        owner=request.user,
                        created_by=request.user,
                    )
                    imported_count += 1

                log_audit(
                    request,
                    "IMPORT",
                    target_model="Contact",
                    description=f"Imported {imported_count} contacts from CSV ({skipped_count} skipped duplicates, {len(failures)} failed)",
                )

        except Exception as e:
            messages.error(request, f"Import process failed: {e}. No records were saved.")
            return render(request, "crm_core/contact_import.html")

        request.session["contact_failed_rows"] = failures

        return render(
            request,
            "crm_core/import_result.html",
            {
                "type": "Contacts",
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "failed_count": len(failures),
                "failures": failures,
                "download_failed_url": reverse("contact_import_failed_csv"),
                "back_url": reverse("contact_list"),
            },
        )

    return render(request, "crm_core/contact_import.html")


@login_required
@email_verification_required
@admin_or_owner_required
def contact_sample_csv_view(request):
    """
    Downloads a sample CSV file with exact columns for contact imports.
    """
    headers = ["name", "email", "phone", "job_title", "company", "status"]
    sample_rows = [
        ["Jane Doe", "jane@example.com", "+91 98765 43211", "VP Engineering", "Acme Technologies", "Lead"],
        ["Rahul Sharma", "rahul@example.com", "+91 91234 56788", "Procurement Head", "Apex Retailers", "Customer"],
    ]
    return stream_csv_response("contacts_sample.csv", headers, sample_rows)


@login_required
@email_verification_required
@admin_or_owner_required
def contact_import_failed_csv_view(request):
    """
    Downloads failed contact rows from the last import session with error reasons.
    """
    failed_rows = request.session.get("contact_failed_rows", [])
    headers = ["name", "email", "phone", "job_title", "company", "status", "Error Reason", "CSV Row Number"]

    def row_generator():
        for item in failed_rows:
            data = item.get("data", ["", "", "", "", "", ""])
            data = list(data) + [""] * (6 - len(data))
            yield data[:6] + [item.get("reason", ""), item.get("row", "")]

    return stream_csv_response("failed_contacts.csv", headers, row_generator())


@login_required
@email_verification_required
@admin_or_owner_required
def contact_export_view(request):
    """
    Exports filtered Contacts matching search and filter queries to a streamed CSV file.
    """
    org = request.user.organization
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    company_filter = request.GET.get("company", "").strip()
    owner_filter = request.GET.get("owner", "").strip()

    contacts = Contact.objects.filter(organization=org).select_related("company", "owner")
    if query:
        contacts = contacts.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(job_title__icontains=query) |
            Q(company__name__icontains=query)
        )
    if status_filter:
        contacts = contacts.filter(status=status_filter)
    if company_filter:
        contacts = contacts.filter(company_id=company_filter)
    if owner_filter:
        contacts = contacts.filter(owner_id=owner_filter)

    contacts = contacts.order_by("first_name", "last_name")
    count = contacts.count()

    log_audit(
        request,
        "EXPORT",
        target_model="Contact",
        description=f"Exported {count} contacts to CSV",
    )

    headers = ["First Name", "Last Name", "Email", "Phone", "Job Title", "Company", "Status", "Owner", "Created At"]

    def row_generator():
        for c in contacts.iterator(chunk_size=500):
            yield [
                c.first_name,
                c.last_name,
                c.email,
                c.phone,
                c.job_title,
                c.company.name if c.company else "",
                c.get_status_display(),
                c.owner.full_name if c.owner else "",
                c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
            ]

    timestamp = timezone.localdate().strftime("%Y%m%d")
    return stream_csv_response(f"contacts_export_{timestamp}.csv", headers, row_generator())


# ------------------------------------------------------------------------------
# DEAL & TASK EXPORT
# ------------------------------------------------------------------------------

@login_required
@email_verification_required
@admin_or_owner_required
def deal_export_view(request):
    """
    Exports Deals matching owner filters to a streamed CSV file (Owner/Admin only).
    """
    org = request.user.organization
    owner_filter = request.GET.get("owner", "").strip()

    deals = Deal.objects.filter(organization=org).select_related("stage", "contact", "company", "owner")
    if owner_filter == "unassigned":
        deals = deals.filter(owner__isnull=True)
    elif owner_filter:
        deals = deals.filter(owner_id=owner_filter)

    deals = deals.order_by("-created_at")
    count = deals.count()

    log_audit(
        request,
        "EXPORT",
        target_model="Deal",
        description=f"Exported {count} deals to CSV",
    )

    headers = ["Title", "Value (INR)", "Stage", "Contact", "Company", "Owner", "Expected Close Date", "Closed Date", "Created At"]

    def row_generator():
        for d in deals.iterator(chunk_size=500):
            yield [
                d.title,
                str(d.value),
                d.stage.name if d.stage else "",
                d.contact.full_name if d.contact else "",
                d.company.name if d.company else "",
                d.owner.full_name if d.owner else "",
                str(d.expected_close_date) if d.expected_close_date else "",
                str(d.closed_date) if d.closed_date else "",
                d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else "",
            ]

    timestamp = timezone.localdate().strftime("%Y%m%d")
    return stream_csv_response(f"deals_export_{timestamp}.csv", headers, row_generator())


@login_required
@email_verification_required
@admin_or_owner_required
def task_export_view(request):
    """
    Exports Tasks matching tab, search, and type/assignee filters to a streamed CSV file.
    """
    org = request.user.organization
    today = timezone.localdate()
    tab = request.GET.get("tab", "all").strip()
    query = request.GET.get("q", "").strip()
    assigned_filter = request.GET.get("assigned", "").strip()
    type_filter = request.GET.get("type", "").strip()

    tasks = Task.objects.filter(organization=org).select_related("contact", "deal", "company", "assigned_to")

    if tab == "my":
        tasks = tasks.filter(assigned_to=request.user, is_completed=False)
    elif tab == "overdue":
        tasks = tasks.filter(is_completed=False, due_date__lt=today)
    elif tab == "today":
        tasks = tasks.filter(is_completed=False, due_date=today)
    elif tab == "upcoming":
        tasks = tasks.filter(is_completed=False, due_date__gt=today)
    elif tab == "done":
        tasks = tasks.filter(is_completed=True)
    # default "all" tasks

    if query:
        tasks = tasks.filter(
            Q(title__icontains=query) |
            Q(notes__icontains=query) |
            Q(contact__first_name__icontains=query) |
            Q(contact__last_name__icontains=query) |
            Q(deal__title__icontains=query)
        )
    if assigned_filter == "unassigned":
        tasks = tasks.filter(assigned_to__isnull=True)
    elif assigned_filter:
        tasks = tasks.filter(assigned_to_id=assigned_filter)
    if type_filter:
        tasks = tasks.filter(task_type=type_filter)

    tasks = tasks.order_by("due_date", "due_time")
    count = tasks.count()

    log_audit(
        request,
        "EXPORT",
        target_model="Task",
        description=f"Exported {count} tasks to CSV",
    )

    headers = ["Title", "Type", "Due Date", "Due Time", "Contact", "Deal", "Company", "Assigned To", "Status", "Notes", "Created At"]

    def row_generator():
        for t in tasks.iterator(chunk_size=500):
            yield [
                t.title,
                t.get_task_type_display(),
                str(t.due_date) if t.due_date else "",
                t.due_time.strftime("%H:%M") if t.due_time else "",
                t.contact.full_name if t.contact else "",
                t.deal.title if t.deal else "",
                t.company.name if t.company else "",
                t.assigned_to.full_name if t.assigned_to else "",
                t.status,
                t.notes,
                t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
            ]

    timestamp = timezone.localdate().strftime("%Y%m%d")
    return stream_csv_response(f"tasks_export_{timestamp}.csv", headers, row_generator())


# ------------------------------------------------------------------------------
# SETTINGS & FULL DATA BACKUP (OWNER ONLY)
# ------------------------------------------------------------------------------

@login_required
@email_verification_required
def settings_view(request):
    """
    Billing-free Settings page: accessible strictly to the business Owner.
    Provides general workspace details and the 'Download all my data' feature.
    """
    if request.user.role != "OWNER":
        messages.error(request, "Only the business Owner can access workspace settings.")
        return redirect("dashboard")

    org = request.user.organization
    return render(request, "crm_core/settings.html", {"organization": org})


@login_required
@email_verification_required
def download_all_data_view(request):
    """
    Creates and downloads an in-memory ZIP archive containing CSVs for:
    companies, contacts, deals, tasks, and notes for the owner's business only.
    Owner only.
    """
    if request.user.role != "OWNER":
        return HttpResponseForbidden("Only the business Owner can download all data.")

    org = request.user.organization

    def generate_csv_bytes(headers, row_list):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([sanitize_export_cell(h) for h in headers])
        for row in row_list:
            writer.writerow([sanitize_export_cell(c) for c in row])
        return output.getvalue().encode("utf-8-sig")

    # 1. Companies
    comp_headers = ["Name", "Industry", "Website", "City", "Phone", "Address", "Created At"]
    comp_rows = [
        [
            c.name, c.industry, c.website, c.city, c.phone, c.address,
            c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else ""
        ]
        for c in Company.objects.filter(organization=org).order_by("name")
    ]
    comp_csv = generate_csv_bytes(comp_headers, comp_rows)

    # 2. Contacts
    cont_headers = ["First Name", "Last Name", "Email", "Phone", "Job Title", "Company", "Status", "Owner", "Created At"]
    cont_rows = [
        [
            c.first_name, c.last_name, c.email, c.phone, c.job_title,
            c.company.name if c.company else "", c.get_status_display(),
            c.owner.full_name if c.owner else "",
            c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else ""
        ]
        for c in Contact.objects.filter(organization=org).select_related("company", "owner").order_by("first_name", "last_name")
    ]
    cont_csv = generate_csv_bytes(cont_headers, cont_rows)

    # 3. Deals
    deal_headers = ["Title", "Value (INR)", "Stage", "Contact", "Company", "Owner", "Expected Close Date", "Closed Date", "Created At"]
    deal_rows = [
        [
            d.title, str(d.value), d.stage.name if d.stage else "",
            d.contact.full_name if d.contact else "", d.company.name if d.company else "",
            d.owner.full_name if d.owner else "",
            str(d.expected_close_date) if d.expected_close_date else "",
            str(d.closed_date) if d.closed_date else "",
            d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else ""
        ]
        for d in Deal.objects.filter(organization=org).select_related("stage", "contact", "company", "owner").order_by("-created_at")
    ]
    deal_csv = generate_csv_bytes(deal_headers, deal_rows)

    # 4. Tasks
    task_headers = ["Title", "Type", "Due Date", "Due Time", "Contact", "Deal", "Company", "Assigned To", "Status", "Notes", "Created At"]
    task_rows = [
        [
            t.title, t.get_task_type_display(),
            str(t.due_date) if t.due_date else "",
            t.due_time.strftime("%H:%M") if t.due_time else "",
            t.contact.full_name if t.contact else "",
            t.deal.title if t.deal else "",
            t.company.name if t.company else "",
            t.assigned_to.full_name if t.assigned_to else "",
            t.status, t.notes,
            t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else ""
        ]
        for t in Task.objects.filter(organization=org).select_related("contact", "deal", "company", "assigned_to").order_by("due_date", "due_time")
    ]
    task_csv = generate_csv_bytes(task_headers, task_rows)

    # 5. Notes
    note_headers = ["Contact Name", "Contact Email", "Author", "Note Content", "Created At"]
    note_rows = [
        [
            n.contact.full_name if n.contact else "",
            n.contact.email if n.contact else "",
            n.author.full_name if n.author else "",
            n.content,
            n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else ""
        ]
        for n in ContactNote.objects.filter(organization=org).select_related("contact", "author").order_by("-created_at")
    ]
    note_csv = generate_csv_bytes(note_headers, note_rows)

    # Assemble ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("companies.csv", comp_csv)
        zf.writestr("contacts.csv", cont_csv)
        zf.writestr("deals.csv", deal_csv)
        zf.writestr("tasks.csv", task_csv)
        zf.writestr("notes.csv", note_csv)

    log_audit(
        request,
        "EXPORT",
        target_model="Organization",
        description="Downloaded complete business data archive (ZIP containing 5 CSVs)",
    )

    zip_buffer.seek(0)
    timestamp = timezone.localdate().strftime("%Y%m%d")
    filename = f"kinetiq_{org.slug or 'crm'}_all_data_{timestamp}.zip"

    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
