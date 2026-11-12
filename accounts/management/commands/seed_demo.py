"""
Management command to seed realistic demo data for the PayPal AI Hackathon.
Creates two segregated tenant organizations, users, companies, contacts, deals (including Won deals),
invoices, and tasks for judges to test immediately.
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from organizations.models import Organization
from accounts.models import User
from crm_core.models import Company, Contact, Deal, Stage, Task
from crm_core.signals import create_default_stages_for_org
from payments.models import Invoice


class Command(BaseCommand):
    help = "Seeds demo tenant organizations, accounts, deals, invoices, and tasks for hackathon demonstration."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("--- Seeding KinetiQ Demo Environment ---"))

        # ------------------------------------------------------------------
        # Organization 1: Acme Innovations
        # ------------------------------------------------------------------
        org_a, _ = Organization.objects.update_or_create(
            slug="acme-innovations",
            defaults={
                "name": "Acme Innovations",
                "plan_status": "ACTIVE",
                "trial_ends_at": timezone.now() + timedelta(days=30),
                "max_users": 10,
                "is_active": True,
            },
        )
        create_default_stages_for_org(org_a)
        stage_won_a = Stage.objects.filter(organization=org_a, is_won=True).first()
        stage_proposal_a = Stage.objects.filter(organization=org_a, name="Proposal").first()
        stage_contacted_a = Stage.objects.filter(organization=org_a, name="Contacted").first()

        admin_a, _ = User.objects.get_or_create(
            email="admin@acme.com",
            defaults={
                "organization": org_a,
                "first_name": "Alex",
                "last_name": "Morgan",
                "role": "OWNER",
                "is_email_verified": True,
            },
        )
        admin_a.organization = org_a
        admin_a.role = "OWNER"
        admin_a.is_email_verified = True
        admin_a.set_password("DemoAdmin123!")
        admin_a.save()

        member_a, _ = User.objects.get_or_create(
            email="member@acme.com",
            defaults={
                "organization": org_a,
                "first_name": "Jordan",
                "last_name": "Taylor",
                "role": "MEMBER",
                "is_email_verified": True,
            },
        )
        member_a.organization = org_a
        member_a.role = "MEMBER"
        member_a.is_email_verified = True
        member_a.set_password("DemoMember123!")
        member_a.save()

        # Companies for Org A
        apex_co, _ = Company.objects.update_or_create(
            organization=org_a,
            name="Apex Dynamics Inc",
            defaults={
                "industry": "Software & Technology",
                "phone": "+1 (555) 234-5678",
                "website": "https://apexdynamics.example.com",
                "address": "100 Innovation Way, Suite 400, Austin, TX",
                "created_by": admin_a,
            },
        )

        starlight_co, _ = Company.objects.update_or_create(
            organization=org_a,
            name="Starlight Retailers",
            defaults={
                "industry": "E-Commerce",
                "phone": "+1 (555) 876-5432",
                "website": "https://starlightretail.example.com",
                "address": "250 Market Street, San Francisco, CA",
                "created_by": member_a,
            },
        )

        # Contacts for Org A
        sarah, _ = Contact.objects.update_or_create(
            organization=org_a,
            email="sarah.jenkins@apexdynamics.example.com",
            defaults={
                "company": apex_co,
                "first_name": "Sarah",
                "last_name": "Jenkins",
                "job_title": "Chief Technology Officer",
                "phone": "+1 (555) 234-5679",
                "status": "CUSTOMER",
                "created_by": admin_a,
            },
        )

        elena, _ = Contact.objects.update_or_create(
            organization=org_a,
            email="elena.rostova@apexdynamics.example.com",
            defaults={
                "company": apex_co,
                "first_name": "Elena",
                "last_name": "Rostova",
                "job_title": "Head of Procurement",
                "phone": "+1 (555) 234-5680",
                "status": "CUSTOMER",
                "created_by": admin_a,
            },
        )

        marcus, _ = Contact.objects.update_or_create(
            organization=org_a,
            email="marcus.vance@starlightretail.example.com",
            defaults={
                "company": starlight_co,
                "first_name": "Marcus",
                "last_name": "Vance",
                "job_title": "VP of Operations",
                "phone": "+1 (555) 876-5433",
                "status": "LEAD",
                "created_by": member_a,
            },
        )

        # Deals for Org A
        # Won Deal 1: Already has a Paid Invoice to showcase metrics and invoice badge
        deal_won_invoiced, _ = Deal.objects.update_or_create(
            organization=org_a,
            title="Enterprise Cloud Suite Q4",
            defaults={
                "value": Decimal("12500.00"),
                "stage": stage_won_a,
                "company": apex_co,
                "contact": sarah,
                "owner": admin_a,
                "expected_close_date": timezone.now().date(),
                "closed_date": timezone.now().date(),
            },
        )

        # Won Deal 2: Ready for judge to click "Send PayPal invoice"
        deal_won_ready, _ = Deal.objects.update_or_create(
            organization=org_a,
            title="Custom API & Microservices Architecture",
            defaults={
                "value": Decimal("4800.00"),
                "stage": stage_won_a,
                "company": apex_co,
                "contact": elena,
                "owner": admin_a,
                "expected_close_date": timezone.now().date(),
                "closed_date": timezone.now().date(),
            },
        )

        # Pipeline Active Deals
        deal_proposal, _ = Deal.objects.update_or_create(
            organization=org_a,
            title="E-Commerce Real-time Analytics Engine",
            defaults={
                "value": Decimal("8500.00"),
                "stage": stage_proposal_a,
                "company": starlight_co,
                "contact": marcus,
                "owner": member_a,
                "expected_close_date": timezone.now().date() + timedelta(days=14),
            },
        )

        deal_negotiation, _ = Deal.objects.update_or_create(
            organization=org_a,
            title="24/7 Security & Support SLA",
            defaults={
                "value": Decimal("3200.00"),
                "stage": stage_contacted_a,
                "company": apex_co,
                "contact": sarah,
                "owner": admin_a,
                "expected_close_date": timezone.now().date() + timedelta(days=7),
            },
        )

        # Sample Paid Invoice for Deal 1
        Invoice.objects.update_or_create(
            deal=deal_won_invoiced,
            defaults={
                "organization": org_a,
                "paypal_invoice_id": "INV2-DEMO-SAMPLE-PAID",
                "invoice_number": "0001",
                "amount": Decimal("12500.00"),
                "currency": "USD",
                "status": "PAID",
                "recipient_email": sarah.email,
                "due_date": timezone.now().date() + timedelta(days=15),
                "payer_link": "https://www.sandbox.paypal.com/invoice/p/#DEMO-PAID",
                "created_by": admin_a,
                "date_paid": timezone.now() - timedelta(days=1),
            },
        )

        # Tasks for Org A
        Task.objects.update_or_create(
            organization=org_a,
            title="Send onboarding guide and API access keys",
            defaults={
                "notes": "Onboard Apex Dynamics engineering team following Enterprise Cloud Suite purchase.",
                "due_date": timezone.now().date() + timedelta(days=2),
                "task_type": "TODO",
                "is_completed": False,
                "assigned_to": admin_a,
                "created_by": admin_a,
                "deal": deal_won_invoiced,
                "contact": sarah,
                "company": apex_co,
            },
        )

        Task.objects.update_or_create(
            organization=org_a,
            title="Present revised proposal to Marcus Vance",
            defaults={
                "notes": "Review analytics engine proposal figures and hosting options.",
                "due_date": timezone.now().date() + timedelta(days=5),
                "task_type": "MEETING",
                "is_completed": False,
                "assigned_to": member_a,
                "created_by": admin_a,
                "deal": deal_proposal,
                "contact": marcus,
                "company": starlight_co,
            },
        )

        # ------------------------------------------------------------------
        # Organization 2: Beta Logistics (Strict Tenant Isolation Test)
        # ------------------------------------------------------------------
        org_b, _ = Organization.objects.update_or_create(
            slug="beta-logistics",
            defaults={
                "name": "Beta Logistics",
                "plan_status": "ACTIVE",
                "trial_ends_at": timezone.now() + timedelta(days=30),
                "max_users": 5,
                "is_active": True,
            },
        )
        create_default_stages_for_org(org_b)
        stage_contacted_b = Stage.objects.filter(organization=org_b, name="Contacted").first()

        owner_b, _ = User.objects.get_or_create(
            email="owner@betalogistics.com",
            defaults={
                "organization": org_b,
                "first_name": "Brooke",
                "last_name": "Evans",
                "role": "OWNER",
                "is_email_verified": True,
            },
        )
        owner_b.organization = org_b
        owner_b.role = "OWNER"
        owner_b.is_email_verified = True
        owner_b.set_password("DemoBeta123!")
        owner_b.save()

        omni_co, _ = Company.objects.update_or_create(
            organization=org_b,
            name="Omni Freight Worldwide",
            defaults={
                "industry": "Transportation & Logistics",
                "phone": "+1 (555) 432-1098",
                "website": "https://omnifreight.example.com",
                "address": "500 Harbor Boulevard, Seattle, WA",
                "created_by": owner_b,
            },
        )

        david, _ = Contact.objects.update_or_create(
            organization=org_b,
            email="david@omnifreight.example.com",
            defaults={
                "company": omni_co,
                "first_name": "David",
                "last_name": "Miller",
                "job_title": "Director of Fleet Operations",
                "phone": "+1 (555) 432-1099",
                "status": "LEAD",
                "created_by": owner_b,
            },
        )

        Deal.objects.update_or_create(
            organization=org_b,
            title="Fleet GPS & Dispatch Optimization",
            defaults={
                "value": Decimal("18500.00"),
                "stage": stage_contacted_b,
                "company": omni_co,
                "contact": david,
                "owner": owner_b,
                "expected_close_date": timezone.now().date() + timedelta(days=20),
            },
        )

        self.stdout.write(self.style.SUCCESS("[SUCCESS] Demo database successfully seeded!\n"))
        self.stdout.write(self.style.WARNING("================ DEMO LOGIN CREDENTIALS ================"))
        self.stdout.write(self.style.NOTICE("1. Acme Innovations (Primary Demo Tenant):"))
        self.stdout.write("   - Owner / Admin Login: admin@acme.com / DemoAdmin123!")
        self.stdout.write("     * Has Won Deals with PayPal invoice actions & metrics")
        self.stdout.write("   - Team Member Login:   member@acme.com / DemoMember123!")
        self.stdout.write("     * Scoped permissions (cannot send invoices)\n")
        self.stdout.write(self.style.NOTICE("2. Beta Logistics (Tenant Isolation Check):"))
        self.stdout.write("   - Owner Login:         owner@betalogistics.com / DemoBeta123!")
        self.stdout.write("     * Cannot see or access Acme Innovations deals, invoices, or contacts\n")
        self.stdout.write(self.style.WARNING("========================================================\n"))
