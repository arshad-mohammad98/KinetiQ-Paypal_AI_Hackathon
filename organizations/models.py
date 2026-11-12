from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from .middleware import get_current_organization

class Organization(models.Model):
    PLAN_CHOICES = [
        ("trial", "14-Day Free Trial"),
        ("active", "Active Paid Plan"),
        ("past_due", "Past Due"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
        # Legacy uppercase choices for backward compatibility
        ("TRIAL", "14-Day Free Trial"),
        ("ACTIVE", "Active Paid Plan"),
        ("EXPIRED", "Expired Trial / Past Due"),
        ("CANCELLED", "Cancelled"),
    ]

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    plan_status = models.CharField(max_length=20, choices=PLAN_CHOICES, default="trial")
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    razorpay_customer_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_subscription_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    max_users = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "org"
            candidate = base_slug
            counter = 1
            while Organization.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate

        if not self.trial_ends_at:
            self.trial_ends_at = timezone.now() + timedelta(days=14)

        super().save(*args, **kwargs)

    @property
    def subscription_state(self):
        """
        Returns normalized lowercase subscription state:
        'trial', 'active', 'past_due', 'cancelled', or 'expired'.
        """
        st = (self.plan_status or "trial").lower()
        if st in ("trial",) and self.trial_ends_at and timezone.now() >= self.trial_ends_at and not self.razorpay_subscription_id:
            return "expired"
        return st

    @property
    def is_trial_active(self):
        return self.subscription_state == "trial" and self.trial_ends_at and timezone.now() < self.trial_ends_at

    @property
    def days_left_in_trial(self):
        if self.trial_ends_at and self.is_trial_active:
            remaining = (self.trial_ends_at - timezone.now()).days
            return max(0, remaining)
        return 0

    @property
    def can_access_crm(self):
        """
        After the trial ends, or if the subscription is cancelled, halted, or expired,
        the business can still log in but is sent to the Billing page and cannot use the CRM,
        except for 'Download all my data' in Settings, which stays available to the Owner.
        """
        st = self.subscription_state
        if st == "active":
            return True
        if st == "trial":
            return bool(self.trial_ends_at and timezone.now() < self.trial_ends_at)
        return False

    def __str__(self):
        return self.name


class TenantQuerySet(models.QuerySet):
    """
    Ensures queries automatically filter by the currently active organization.
    """
    def filter_by_current_tenant(self):
        current_org = get_current_organization()
        if current_org is not None:
            return self.filter(organization=current_org)
        return self

    def for_organization(self, organization):
        return self.filter(organization=organization)

    def all_organizations(self):
        return super().all()


class TenantManager(models.Manager):
    """
    Model manager that enforces tenant isolation at the ORM layer.
    """
    def get_queryset(self):
        current_org = get_current_organization()
        qs = TenantQuerySet(self.model, using=self._db)
        if current_org is not None:
            return qs.filter(organization=current_org)
        return qs

    def for_organization(self, organization):
        return TenantQuerySet(self.model, using=self._db).filter(organization=organization)

    def all_organizations(self):
        return TenantQuerySet(self.model, using=self._db)


class TenantModel(models.Model):
    """
    Abstract base class for all business models. Enforces organization_id
    and automatic query scoping.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not hasattr(self, "organization") or self.organization_id is None:
            current_org = get_current_organization()
            if current_org:
                self.organization = current_org
        super().save(*args, **kwargs)
