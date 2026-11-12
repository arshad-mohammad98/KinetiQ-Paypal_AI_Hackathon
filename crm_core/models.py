from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from organizations.models import TenantModel

class Company(TenantModel):
    name = models.CharField(max_length=150)
    industry = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_companies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Contact(TenantModel):
    STATUS_CHOICES = [
        ("LEAD", "Lead"),
        ("CUSTOMER", "Customer"),
        ("INACTIVE", "Inactive"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contacts",
    )
    first_name = models.CharField(max_length=75)
    last_name = models.CharField(max_length=75, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="LEAD", db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_contacts",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_contacts",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class ContactNote(TenantModel):
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="contact_notes",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note on {self.contact.full_name} by {self.author} at {self.created_at}"


class Stage(TenantModel):
    name = models.CharField(max_length=50)
    order = models.PositiveIntegerField(default=0)
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Deal(TenantModel):
    title = models.CharField(max_length=200)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    stage = models.ForeignKey(
        Stage,
        on_delete=models.PROTECT,
        related_name="deals",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="deals",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deals",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_deals",
    )
    expected_close_date = models.DateField(null=True, blank=True)
    closed_date = models.DateField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if not self.contact_id:
            raise ValidationError({"contact": "Contact is required."})
        if self.contact_id and self.organization_id:
            if self.contact.organization_id != self.organization_id:
                raise ValidationError({"contact": "A deal can only use a contact from its own business."})
        if self.stage_id and self.organization_id:
            if self.stage.organization_id != self.organization_id:
                raise ValidationError({"stage": "A deal can only use stages from its own business."})
        if self.owner_id and self.organization_id:
            if self.owner.organization_id != self.organization_id:
                raise ValidationError({"owner": "A deal can only be assigned to a team member in its own business."})

    def save(self, *args, **kwargs):
        # Auto-assign initial stage if not provided
        if not self.stage_id:
            org = getattr(self, "organization", None)
            if not org and hasattr(self, "organization_id") and self.organization_id:
                org = self.organization_id
            if not org:
                from organizations.middleware import get_current_organization
                org = get_current_organization()
            if org:
                first_stage = Stage.all_objects.filter(organization=org).order_by("order").first()
                if first_stage:
                    self.stage = first_stage

        # The company is taken from the contact if present
        if self.contact_id:
            if hasattr(self, "contact") and self.contact:
                self.company = self.contact.company
            else:
                contact = Contact.all_objects.filter(pk=self.contact_id).first()
                if contact:
                    self.company = contact.company

        # Won and Lost stages record the date the deal was closed
        # Moving a deal to Won or Lost sets the closed date and moving it back clears it
        if self.stage_id:
            stage = self.stage if hasattr(self, "stage") and self.stage else Stage.all_objects.filter(pk=self.stage_id).first()
            if stage:
                is_won_or_lost = (
                    getattr(stage, "is_won", False)
                    or getattr(stage, "is_lost", False)
                    or stage.name.lower() in ["won", "lost"]
                )
                if is_won_or_lost:
                    if not self.closed_date:
                        self.closed_date = timezone.now().date()
                else:
                    self.closed_date = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} (${self.value})"


class Task(TenantModel):
    TYPE_CHOICES = [
        ("CALL", "Call"),
        ("MEETING", "Meeting"),
        ("EMAIL", "Email"),
        ("TODO", "To-do"),
    ]

    title = models.CharField(max_length=200)
    task_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="TODO")
    due_date = models.DateField(null=True, blank=True, db_index=True)
    due_time = models.TimeField(null=True, blank=True)
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    deal = models.ForeignKey(
        Deal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tasks",
    )
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "due_time", "-created_at"]

    @property
    def description(self):
        return self.notes

    @property
    def status(self):
        return "COMPLETED" if self.is_completed else "PENDING"

    @property
    def is_overdue(self):
        if self.is_completed or not self.due_date:
            return False
        return self.due_date < timezone.localdate()

    @property
    def is_due_today(self):
        if self.is_completed or not self.due_date:
            return False
        return self.due_date == timezone.localdate()

    def clean(self):
        super().clean()
        if self.contact_id and self.organization_id:
            if self.contact.organization_id != self.organization_id:
                raise ValidationError({"contact": "A task can only link to contacts from its own business."})
        if self.deal_id and self.organization_id:
            if self.deal.organization_id != self.organization_id:
                raise ValidationError({"deal": "A task can only link to deals from its own business."})
        if self.assigned_to_id and self.organization_id:
            if self.assigned_to.organization_id != self.organization_id:
                raise ValidationError({"assigned_to": "A task can only be assigned to a team member in its own business."})

    def save(self, *args, **kwargs):
        # If a task is linked to a deal, its contact is taken from the deal
        if self.deal_id:
            if hasattr(self, "deal") and self.deal and self.deal.contact_id:
                self.contact = self.deal.contact
            else:
                deal = Deal.all_objects.filter(pk=self.deal_id).first()
                if deal and deal.contact_id:
                    self.contact = deal.contact

        # Company is taken from contact or deal
        if self.contact_id:
            if hasattr(self, "contact") and self.contact:
                self.company = self.contact.company
            else:
                contact = Contact.all_objects.filter(pk=self.contact_id).first()
                if contact:
                    self.company = contact.company
        elif self.deal_id:
            if hasattr(self, "deal") and self.deal:
                self.company = self.deal.company
            else:
                deal = Deal.all_objects.filter(pk=self.deal_id).first()
                if deal:
                    self.company = deal.company
        else:
            self.company = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_task_type_display()})"


class AuditLog(TenantModel):
    ACTION_CHOICES = [
        ("LOGIN", "User Login"),
        ("LOGOUT", "User Logout"),
        ("CREATE", "Record Created"),
        ("UPDATE", "Record Updated"),
        ("MOVE", "Record Moved Stage"),
        ("COMPLETE", "Task Completed"),
        ("DELETE", "Record Deleted"),
        ("EXPORT", "Data Exported"),
        ("IMPORT", "Data Imported"),
        ("INVITE", "Team Member Invited"),
        ("SUBSCRIPTION", "Subscription Changed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_model = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def human_sentence(self):
        user_name = self.user.full_name if self.user else "System"
        if self.description:
            desc = self.description.strip()
            # If description already starts with a verb, e.g. "Created task 'xyz'" -> "Alice Owner created task 'xyz'"
            if desc and desc[0].isupper() and not desc.startswith("CRM"):
                return f"{user_name} {desc[0].lower() + desc[1:]}"
            return f"{user_name}: {desc}"
        action_map = {
            "LOGIN": "logged in",
            "LOGOUT": "logged out",
            "CREATE": f"created a {self.target_model.lower() if self.target_model else 'record'}",
            "UPDATE": f"updated a {self.target_model.lower() if self.target_model else 'record'}",
            "MOVE": f"moved a {self.target_model.lower() if self.target_model else 'deal'}",
            "COMPLETE": "completed a task",
            "DELETE": f"deleted a {self.target_model.lower() if self.target_model else 'record'}",
            "EXPORT": f"exported {self.target_model.lower() if self.target_model else 'data'}",
            "IMPORT": f"imported {self.target_model.lower() if self.target_model else 'data'}",
            "SUBSCRIPTION": "updated subscription status",
            "INVITE": "invited a team member",
        }
        action_text = action_map.get(self.action_type, f"performed {self.action_type}")
        return f"{user_name} {action_text}"

    def __str__(self):
        return f"[{self.action_type}] {self.target_model} by {self.user} at {self.created_at}"
