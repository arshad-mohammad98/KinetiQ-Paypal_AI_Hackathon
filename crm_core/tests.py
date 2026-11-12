import csv
import io
import zipfile
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from organizations.models import Organization
from .models import Company, Contact, ContactNote, AuditLog, Stage, Deal, Task

User = get_user_model()


class MultiTenantCRMTestCase(TestCase):
    def setUp(self):
        # 1. Create Organization A with Owner, Admin, and Member
        self.org_a = Organization.objects.create(name="Acme Corp", slug="acme-corp")
        self.owner_a = User.objects.create_user(
            email="owner_a@acme.com",
            password="Password123!",
            first_name="Alice",
            last_name="Owner",
            organization=self.org_a,
            role="OWNER",
            is_email_verified=True,
        )
        self.admin_a = User.objects.create_user(
            email="admin_a@acme.com",
            password="Password123!",
            first_name="Alan",
            last_name="Admin",
            organization=self.org_a,
            role="ADMIN",
            is_email_verified=True,
        )
        self.member_a = User.objects.create_user(
            email="member_a@acme.com",
            password="Password123!",
            first_name="Mike",
            last_name="Member",
            organization=self.org_a,
            role="MEMBER",
            is_email_verified=True,
        )

        # 2. Create Organization B with Owner
        self.org_b = Organization.objects.create(name="Beta LLC", slug="beta-llc")
        self.owner_b = User.objects.create_user(
            email="owner_b@beta.com",
            password="Password123!",
            first_name="Bob",
            last_name="Beta",
            organization=self.org_b,
            role="OWNER",
            is_email_verified=True,
        )

        # 3. Create sample companies & contacts
        self.comp_a = Company.objects.create(
            organization=self.org_a,
            name="Alpha Client",
            industry="Software",
            city="New York",
            phone="111-222-3333",
            created_by=self.owner_a,
        )
        self.comp_b = Company.objects.create(
            organization=self.org_b,
            name="Alpha Client",  # Same name in Org B to test search isolation
            industry="Healthcare",
            city="Chicago",
            phone="999-888-7777",
            created_by=self.owner_b,
        )

        self.contact_a = Contact.objects.create(
            organization=self.org_a,
            company=self.comp_a,
            first_name="John",
            last_name="Doe",
            email="john@alphaclient.com",
            phone="111-555-0101",
            job_title="Director",
            status="LEAD",
            owner=self.member_a,
            created_by=self.owner_a,
        )
        self.contact_b = Contact.objects.create(
            organization=self.org_b,
            company=self.comp_b,
            first_name="Jane",
            last_name="Smith",
            email="jane@betaclient.com",
            phone="999-555-0202",
            job_title="Manager",
            status="LEAD",
            owner=self.owner_b,
            created_by=self.owner_b,
        )

        # 4. Stages created automatically by signal on Organization creation
        self.stage_a_new = Stage.all_objects.get(organization=self.org_a, name="New")
        self.stage_a_contacted = Stage.all_objects.get(organization=self.org_a, name="Contacted")
        self.stage_a_proposal = Stage.all_objects.get(organization=self.org_a, name="Proposal")
        self.stage_a_won = Stage.all_objects.get(organization=self.org_a, name="Won")
        self.stage_a_lost = Stage.all_objects.get(organization=self.org_a, name="Lost")

        self.stage_b_new = Stage.all_objects.get(organization=self.org_b, name="New")
        self.stage_b_won = Stage.all_objects.get(organization=self.org_b, name="Won")

        # 5. Sample deal in Org A
        self.deal_a = Deal.objects.create(
            organization=self.org_a,
            title="Acme License Deal",
            value=Decimal("50000.00"),
            contact=self.contact_a,
            stage=self.stage_a_new,
            owner=self.member_a,
        )

        self.deal_b = Deal.objects.create(
            organization=self.org_b,
            title="Beta Deal",
            value=Decimal("10000.00"),
            contact=self.contact_b,
            stage=self.stage_b_new,
            owner=self.owner_b,
        )

        # 6. Sample task in Org A
        self.task_a = Task.objects.create(
            organization=self.org_a,
            title="Call John regarding contract",
            task_type="CALL",
            due_date=timezone.localdate(),
            contact=self.contact_a,
            deal=self.deal_a,
            assigned_to=self.member_a,
            created_by=self.owner_a,
        )

        # Setup Clients
        self.client_a = Client()
        self.client_a.force_login(self.owner_a)

        self.client_b = Client()
        self.client_b.force_login(self.owner_b)

        self.client_member = Client()
        self.client_member.force_login(self.member_a)

    # ==========================================================================
    # DATA SEPARATION & IDOR PREVENTION TESTS
    # ==========================================================================

    def test_business_b_cannot_view_business_a_company_by_url(self):
        """Organization B accessing Organization A's company URL gets 404."""
        response = self.client_b.get(reverse("company_detail", kwargs={"pk": self.comp_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_business_b_cannot_edit_business_a_company_by_url(self):
        """Organization B attempting to edit Organization A's company gets 404."""
        response = self.client_b.post(
            reverse("company_update", kwargs={"pk": self.comp_a.pk}),
            {"name": "Hacked Company", "city": "London"},
        )
        self.assertEqual(response.status_code, 404)
        self.comp_a.refresh_from_db()
        self.assertEqual(self.comp_a.name, "Alpha Client")

    def test_business_b_cannot_delete_business_a_company_by_url(self):
        """Organization B attempting to delete Organization A's company gets 404."""
        response = self.client_b.post(reverse("company_delete", kwargs={"pk": self.comp_a.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Company.objects.filter(pk=self.comp_a.pk).exists())

    def test_business_b_cannot_view_business_a_contact_by_url(self):
        """Organization B accessing Organization A's contact URL gets 404."""
        response = self.client_b.get(reverse("contact_detail", kwargs={"pk": self.contact_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_business_b_cannot_edit_business_a_contact_by_url(self):
        """Organization B attempting to edit Organization A's contact gets 404."""
        response = self.client_b.post(
            reverse("contact_update", kwargs={"pk": self.contact_a.pk}),
            {"first_name": "Hacked", "email": "hacked@acme.com", "status": "LEAD"},
        )
        self.assertEqual(response.status_code, 404)
        self.contact_a.refresh_from_db()
        self.assertEqual(self.contact_a.first_name, "John")

    def test_business_b_cannot_delete_business_a_contact_by_url(self):
        """Organization B attempting to delete Organization A's contact gets 404."""
        response = self.client_b.post(reverse("contact_delete", kwargs={"pk": self.contact_a.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Contact.objects.filter(pk=self.contact_a.pk).exists())

    # ==========================================================================
    # ROLE PERMISSIONS TESTS
    # ==========================================================================

    def test_member_cannot_delete_company(self):
        """A team Member cannot delete a company (gets redirected and company is retained)."""
        response = self.client_member.post(reverse("company_delete", kwargs={"pk": self.comp_a.pk}))
        self.assertEqual(response.status_code, 302)  # Redirected away
        self.assertTrue(Company.objects.filter(pk=self.comp_a.pk).exists())

    def test_member_cannot_delete_contact(self):
        """A team Member cannot delete a contact (gets redirected and contact is retained)."""
        response = self.client_member.post(reverse("contact_delete", kwargs={"pk": self.contact_a.pk}))
        self.assertEqual(response.status_code, 302)  # Redirected away
        self.assertTrue(Contact.objects.filter(pk=self.contact_a.pk).exists())

    def test_owner_and_admin_can_delete_company_and_contact(self):
        """Owner and Admin can successfully delete records with audit logging."""
        # Owner deletes contact_a
        resp_del_contact = self.client_a.post(reverse("contact_delete", kwargs={"pk": self.contact_a.pk}))
        self.assertRedirects(resp_del_contact, reverse("contact_list"))
        self.assertFalse(Contact.objects.filter(pk=self.contact_a.pk).exists())

        # Admin deletes comp_a
        client_admin = Client()
        client_admin.force_login(self.admin_a)
        resp_del_comp = client_admin.post(reverse("company_delete", kwargs={"pk": self.comp_a.pk}))
        self.assertRedirects(resp_del_comp, reverse("company_list"))
        self.assertFalse(Company.objects.filter(pk=self.comp_a.pk).exists())

    def test_member_can_create_and_edit_records(self):
        """Member role can create and edit both companies and contacts."""
        # Member creates company
        resp_create = self.client_member.post(
            reverse("company_create"),
            {"name": "Member Company", "city": "Boston"},
            follow=True,
        )
        self.assertEqual(resp_create.status_code, 200)
        new_comp = Company.objects.get(name="Member Company")
        self.assertEqual(new_comp.organization, self.org_a)

        # Member edits company
        resp_edit = self.client_member.post(
            reverse("company_update", kwargs={"pk": new_comp.pk}),
            {"name": "Member Company Updated", "city": "Cambridge"},
            follow=True,
        )
        self.assertEqual(resp_edit.status_code, 200)
        new_comp.refresh_from_db()
        self.assertEqual(new_comp.name, "Member Company Updated")

    # ==========================================================================
    # SEARCH & FILTER ISOLATION TESTS
    # ==========================================================================

    def test_search_and_filters_return_only_own_business_records(self):
        """Searching for 'Alpha Client' in Org A returns only Org A's company, never Org B's."""
        response = self.client_a.get(reverse("company_list"), {"q": "Alpha Client"})
        self.assertEqual(response.status_code, 200)
        companies_returned = list(response.context["page_obj"])
        self.assertIn(self.comp_a, companies_returned)
        self.assertNotIn(self.comp_b, companies_returned)

        # Similarly in Org B
        response_b = self.client_b.get(reverse("company_list"), {"q": "Alpha Client"})
        self.assertEqual(response_b.status_code, 200)
        companies_returned_b = list(response_b.context["page_obj"])
        self.assertIn(self.comp_b, companies_returned_b)
        self.assertNotIn(self.comp_a, companies_returned_b)

    def test_contact_filters_are_strictly_scoped(self):
        """Filtering contacts by status and company isolates data to the user's organization."""
        response = self.client_a.get(
            reverse("contact_list"),
            {"status": "LEAD", "company": str(self.comp_a.pk)},
        )
        self.assertEqual(response.status_code, 200)
        contacts = list(response.context["page_obj"])
        self.assertIn(self.contact_a, contacts)
        self.assertNotIn(self.contact_b, contacts)

    # ==========================================================================
    # CROSS-TENANT RELATIONSHIP INTEGRITY TESTS
    # ==========================================================================

    def test_contact_cannot_be_linked_to_company_in_another_business(self):
        """A contact in Org A cannot be linked to a company in Org B."""
        # Attempt to link Contact in Org A to comp_b (Org B)
        response = self.client_a.post(
            reverse("contact_create"),
            {
                "first_name": "Intruder",
                "email": "intruder@acme.com",
                "company": self.comp_b.pk,  # From Org B!
                "status": "LEAD",
            },
        )
        # Form should be invalid and not redirect
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contact.objects.filter(email="intruder@acme.com").exists())

    # ==========================================================================
    # DUPLICATE EMAIL WARNING (NON-BLOCKING) TESTS
    # ==========================================================================

    def test_duplicate_email_warns_without_blocking(self):
        """Adding another contact with the same email in the same business warns but saves."""
        response = self.client_a.post(
            reverse("contact_create"),
            {
                "first_name": "Johnny",
                "last_name": "Duplicate",
                "email": self.contact_a.email,  # Same email as contact_a
                "status": "LEAD",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        # Verify contact was saved successfully
        duplicate_contact = Contact.objects.filter(first_name="Johnny", email=self.contact_a.email).first()
        self.assertIsNotNone(duplicate_contact)

        # Verify warning message was emitted
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("already has the email" in msg for msg in messages))

    # ==========================================================================
    # NOTES TIMELINE & AUDIT LOG TESTS
    # ==========================================================================

    def test_contact_notes_timeline(self):
        """Users can add notes, which appear newest first with author name."""
        # Add note 1
        self.client_a.post(
            reverse("contact_detail", kwargs={"pk": self.contact_a.pk}),
            {"content": "Initial introductory phone call."},
        )
        # Add note 2
        self.client_a.post(
            reverse("contact_detail", kwargs={"pk": self.contact_a.pk}),
            {"content": "Followed up with enterprise proposal."},
        )

        # Fetch detail page
        response = self.client_a.get(reverse("contact_detail", kwargs={"pk": self.contact_a.pk}))
        notes = list(response.context["notes"])
        self.assertEqual(len(notes), 2)
        # Newest first
        self.assertEqual(notes[0].content, "Followed up with enterprise proposal.")
        self.assertEqual(notes[0].author, self.owner_a)
        self.assertEqual(notes[1].content, "Initial introductory phone call.")

    def test_audit_log_records_create_update_delete(self):
        """AuditLog table records who performed each action."""
        # 1. Create company
        self.client_a.post(
            reverse("company_create"),
            {"name": "Audit Test Corp", "city": "Denver"},
        )
        corp = Company.objects.get(name="Audit Test Corp")
        log_create = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="CREATE",
            target_model="Company",
            target_id=str(corp.pk),
        ).first()
        self.assertIsNotNone(log_create)
        self.assertEqual(log_create.user, self.owner_a)

        # 2. Update company
        self.client_a.post(
            reverse("company_update", kwargs={"pk": corp.pk}),
            {"name": "Audit Test Corp Updated"},
        )
        log_update = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="UPDATE",
            target_model="Company",
            target_id=str(corp.pk),
        ).first()
        self.assertIsNotNone(log_update)

        # 3. Delete company
        self.client_a.post(reverse("company_delete", kwargs={"pk": corp.pk}))
        log_delete = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="DELETE",
            target_model="Company",
            target_id=str(corp.pk),
        ).first()
        self.assertIsNotNone(log_delete)

    # ==========================================================================
    # DEALS PIPELINE & STAGES TESTS
    # ==========================================================================

    def test_default_stages_created_in_order_for_new_organization(self):
        """When an organization is created, it automatically receives the 5 default stages in order."""
        new_org = Organization.objects.create(name="Gamma Enterprises", slug="gamma-ent")
        stages = list(Stage.all_objects.filter(organization=new_org).order_by("order"))
        self.assertEqual(len(stages), 5)
        stage_names = [s.name for s in stages]
        self.assertEqual(stage_names, ["New", "Contacted", "Proposal", "Won", "Lost"])
        self.assertEqual([s.order for s in stages], [1, 2, 3, 4, 5])
        self.assertTrue(stages[3].is_won)
        self.assertTrue(stages[4].is_lost)

    def test_business_b_cannot_view_business_a_deal_by_url(self):
        """Organization B accessing Organization A's deal URL gets 404."""
        response = self.client_b.get(reverse("deal_update", kwargs={"pk": self.deal_a.pk}))
        self.assertEqual(response.status_code, 404)

        response_detail = self.client_b.get(reverse("deal_detail", kwargs={"pk": self.deal_a.pk}))
        self.assertEqual(response_detail.status_code, 404)

    def test_business_b_cannot_edit_business_a_deal_by_url(self):
        """Organization B attempting to edit Organization A's deal gets 404."""
        response = self.client_b.post(
            reverse("deal_update", kwargs={"pk": self.deal_a.pk}),
            {
                "title": "Hacked Title",
                "value": "999999.00",
                "contact": self.contact_b.pk,
                "stage": self.stage_b_new.pk,
            },
        )
        self.assertEqual(response.status_code, 404)
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.title, "Acme License Deal")

    def test_business_b_cannot_move_business_a_deal_by_move_request(self):
        """Organization B attempting to move Organization A's deal gets 404."""
        response = self.client_b.post(
            reverse("deal_move", kwargs={"pk": self.deal_a.pk}),
            {"stage_id": self.stage_b_won.pk},
        )
        self.assertEqual(response.status_code, 404)
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.stage, self.stage_a_new)

    def test_business_b_cannot_delete_business_a_deal_by_url(self):
        """Organization B attempting to delete Organization A's deal gets 404."""
        response = self.client_b.post(reverse("deal_delete", kwargs={"pk": self.deal_a.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Deal.objects.filter(pk=self.deal_a.pk).exists())

    def test_business_a_cannot_move_deal_to_stage_in_another_business(self):
        """Organization A attempting to move deal to a stage in Organization B gets 404."""
        response = self.client_a.post(
            reverse("deal_move", kwargs={"pk": self.deal_a.pk}),
            {"stage_id": self.stage_b_won.pk},  # Belongs to Org B!
        )
        self.assertEqual(response.status_code, 404)
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.stage, self.stage_a_new)

    def test_deal_can_only_use_contact_and_stages_from_own_business(self):
        """A deal cannot be created using contacts or stages from another business."""
        # 1. Attempt using contact from Org B
        resp_bad_contact = self.client_a.post(
            reverse("deal_create"),
            {
                "title": "Cross Tenant Contact Deal",
                "value": "10000.00",
                "contact": self.contact_b.pk,  # From Org B
                "stage": self.stage_a_new.pk,
            },
        )
        self.assertEqual(resp_bad_contact.status_code, 200)
        self.assertFalse(Deal.objects.filter(title="Cross Tenant Contact Deal").exists())

        # 2. Attempt using stage from Org B
        resp_bad_stage = self.client_a.post(
            reverse("deal_create"),
            {
                "title": "Cross Tenant Stage Deal",
                "value": "10000.00",
                "contact": self.contact_a.pk,
                "stage": self.stage_b_new.pk,  # From Org B
            },
        )
        self.assertEqual(resp_bad_stage.status_code, 200)
        self.assertFalse(Deal.objects.filter(title="Cross Tenant Stage Deal").exists())

    def test_deal_company_taken_from_contact(self):
        """When a deal is created or saved, its company is automatically populated from the contact."""
        resp = self.client_a.post(
            reverse("deal_create"),
            {
                "title": "Enterprise Expansion",
                "value": "85000.00",
                "contact": self.contact_a.pk,
                "stage": self.stage_a_new.pk,
                "owner": self.owner_a.pk,
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        created_deal = Deal.objects.get(title="Enterprise Expansion")
        self.assertEqual(created_deal.company, self.comp_a)

    def test_moving_deal_to_won_or_lost_sets_closed_date_and_moving_back_clears_it(self):
        """Moving a deal to Won or Lost sets the closed date, and moving it back clears it."""
        today = timezone.now().date()
        self.assertIsNone(self.deal_a.closed_date)

        # 1. Move to Won -> closed_date is set
        self.client_a.post(
            reverse("deal_move", kwargs={"pk": self.deal_a.pk}),
            {"stage_id": self.stage_a_won.pk},
        )
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.stage, self.stage_a_won)
        self.assertEqual(self.deal_a.closed_date, today)

        # 2. Move back to Proposal -> closed_date is cleared
        self.client_a.post(
            reverse("deal_move", kwargs={"pk": self.deal_a.pk}),
            {"stage_id": self.stage_a_proposal.pk},
        )
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.stage, self.stage_a_proposal)
        self.assertIsNone(self.deal_a.closed_date)

        # 3. Move to Lost -> closed_date is set
        self.client_a.post(
            reverse("deal_move", kwargs={"pk": self.deal_a.pk}),
            {"stage_id": self.stage_a_lost.pk},
        )
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.stage, self.stage_a_lost)
        self.assertEqual(self.deal_a.closed_date, today)

        # 4. Move back to New -> closed_date is cleared
        self.client_a.post(
            reverse("deal_move", kwargs={"pk": self.deal_a.pk}),
            {"stage_id": self.stage_a_new.pk},
        )
        self.deal_a.refresh_from_db()
        self.assertEqual(self.deal_a.stage, self.stage_a_new)
        self.assertIsNone(self.deal_a.closed_date)

    def test_member_cannot_delete_deal(self):
        """A team Member cannot delete a deal (redirected and retained)."""
        response = self.client_member.post(reverse("deal_delete", kwargs={"pk": self.deal_a.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Deal.objects.filter(pk=self.deal_a.pk).exists())

    def test_owner_and_admin_can_delete_deal_with_confirmation_and_audit(self):
        """Owner and Admin can delete deals with audit logging."""
        # 1. Admin deletes deal_a
        client_admin = Client()
        client_admin.force_login(self.admin_a)
        resp_del = client_admin.post(reverse("deal_delete", kwargs={"pk": self.deal_a.pk}))
        self.assertRedirects(resp_del, reverse("deal_board"))
        self.assertFalse(Deal.objects.filter(pk=self.deal_a.pk).exists())

        # Verify AuditLog recorded deletion
        del_log = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="DELETE",
            target_model="Deal",
            target_id=str(self.deal_a.pk),
        ).first()
        self.assertIsNotNone(del_log)
        self.assertEqual(del_log.user, self.admin_a)

    def test_column_totals_and_counts_are_correct(self):
        """Each pipeline column accurately reports deal count and total rupee value."""
        # Setup specific deals:
        # self.deal_a is in 'New' with value 50,000.00
        # Add another in 'New' with value 25,000.00
        deal_new_2 = Deal.objects.create(
            organization=self.org_a,
            title="Deal New 2",
            value=Decimal("25000.00"),
            contact=self.contact_a,
            stage=self.stage_a_new,
        )
        # Add deal in 'Proposal' with value 100,000.00
        deal_prop = Deal.objects.create(
            organization=self.org_a,
            title="Deal Proposal",
            value=Decimal("100000.00"),
            contact=self.contact_a,
            stage=self.stage_a_proposal,
        )
        # Add deal in 'Won' with value 200,000.00
        deal_won = Deal.objects.create(
            organization=self.org_a,
            title="Deal Won",
            value=Decimal("200000.00"),
            contact=self.contact_a,
            stage=self.stage_a_won,
        )

        response = self.client_a.get(reverse("deal_board"))
        self.assertEqual(response.status_code, 200)

        columns_by_name = {col["stage"].name: col for col in response.context["columns"]}

        # Check 'New' column: 2 deals, total 75,000.00
        self.assertEqual(columns_by_name["New"]["count"], 2)
        self.assertEqual(columns_by_name["New"]["total_value"], Decimal("75000.00"))

        # Check 'Proposal' column: 1 deal, total 100,000.00
        self.assertEqual(columns_by_name["Proposal"]["count"], 1)
        self.assertEqual(columns_by_name["Proposal"]["total_value"], Decimal("100000.00"))

        # Check 'Won' column: 1 deal, total 200,000.00
        self.assertEqual(columns_by_name["Won"]["count"], 1)
        self.assertEqual(columns_by_name["Won"]["total_value"], Decimal("200000.00"))

        # Check 'Lost' column: 0 deals, total 0.00
        self.assertEqual(columns_by_name["Lost"]["count"], 0)
        self.assertEqual(columns_by_name["Lost"]["total_value"], Decimal("0.00"))

        # Check top of board metrics: open pipeline = 75,000 + 100,000 = 175,000.00
        self.assertEqual(response.context["total_open_pipeline_value"], Decimal("175000.00"))
        # Won this month = 1
        self.assertEqual(response.context["won_this_month"], 1)

    def test_owner_filter_on_pipeline_board(self):
        """Filtering by owner only displays deals owned by that team member."""
        # Create unassigned deal
        unassigned_deal = Deal.objects.create(
            organization=self.org_a,
            title="Unassigned Deal",
            value=Decimal("30000.00"),
            contact=self.contact_a,
            stage=self.stage_a_new,
            owner=None,
        )

        # Filter by member_a (who owns deal_a)
        resp_filtered = self.client_a.get(reverse("deal_board"), {"owner": str(self.member_a.pk)})
        self.assertEqual(resp_filtered.status_code, 200)
        col_new = next(c for c in resp_filtered.context["columns"] if c["stage"].name == "New")
        self.assertIn(self.deal_a, col_new["deals"])
        self.assertNotIn(unassigned_deal, col_new["deals"])

        # Filter by unassigned
        resp_unassigned = self.client_a.get(reverse("deal_board"), {"owner": "unassigned"})
        self.assertEqual(resp_unassigned.status_code, 200)
        col_new_un = next(c for c in resp_unassigned.context["columns"] if c["stage"].name == "New")
        self.assertIn(unassigned_deal, col_new_un["deals"])
        self.assertNotIn(self.deal_a, col_new_un["deals"])

    def test_contact_page_shows_deals_and_add_deal_button(self):
        """Contact detail page shows associated deals and an Add Deal button pre-selecting the contact."""
        response = self.client_a.get(reverse("contact_detail", kwargs={"pk": self.contact_a.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.deal_a, list(response.context["deals"]))
        self.assertContains(response, self.deal_a.title)
        self.assertContains(response, f"contact_id={self.contact_a.pk}")

    def test_audit_log_records_deal_lifecycle(self):
        """AuditLog records who created, edited, moved, and deleted each deal."""
        # 1. CREATE
        resp_create = self.client_a.post(
            reverse("deal_create"),
            {
                "title": "Audit Deal Lifecycle",
                "value": "45000.00",
                "contact": self.contact_a.pk,
                "stage": self.stage_a_new.pk,
            },
        )
        deal = Deal.objects.get(title="Audit Deal Lifecycle")
        log_create = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="CREATE",
            target_model="Deal",
            target_id=str(deal.pk),
        ).first()
        self.assertIsNotNone(log_create)
        self.assertEqual(log_create.user, self.owner_a)

        # 2. UPDATE (Edit)
        self.client_a.post(
            reverse("deal_update", kwargs={"pk": deal.pk}),
            {
                "title": "Audit Deal Lifecycle Renamed",
                "value": "55000.00",
                "contact": self.contact_a.pk,
                "stage": self.stage_a_new.pk,
            },
        )
        log_update = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="UPDATE",
            target_model="Deal",
            target_id=str(deal.pk),
        ).first()
        self.assertIsNotNone(log_update)
        self.assertEqual(log_update.user, self.owner_a)

        # 3. MOVE
        self.client_a.post(
            reverse("deal_move", kwargs={"pk": deal.pk}),
            {"stage_id": self.stage_a_contacted.pk},
        )
        log_move = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="MOVE",
            target_model="Deal",
            target_id=str(deal.pk),
        ).first()
        self.assertIsNotNone(log_move)
        self.assertEqual(log_move.user, self.owner_a)

        # 4. DELETE
        self.client_a.post(reverse("deal_delete", kwargs={"pk": deal.pk}))
        log_delete = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="DELETE",
            target_model="Deal",
            target_id=str(deal.pk),
        ).first()
        self.assertIsNotNone(log_delete)
        self.assertEqual(log_delete.user, self.owner_a)

    # ==========================================================================
    # TASKS & REMINDERS TESTS
    # ==========================================================================

    def test_business_b_cannot_view_business_a_task_by_url(self):
        """Organization B accessing Organization A's task edit URL gets 404."""
        response = self.client_b.get(reverse("task_update", kwargs={"pk": self.task_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_business_b_cannot_edit_business_a_task_by_url(self):
        """Organization B attempting to edit Organization A's task gets 404."""
        response = self.client_b.post(
            reverse("task_update", kwargs={"pk": self.task_a.pk}),
            {
                "title": "Hacked Task",
                "task_type": "CALL",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.task_a.refresh_from_db()
        self.assertEqual(self.task_a.title, "Call John regarding contract")

    def test_business_b_cannot_complete_business_a_task_by_url(self):
        """Organization B attempting to complete Organization A's task gets 404."""
        response = self.client_b.post(reverse("task_toggle_done", kwargs={"pk": self.task_a.pk}))
        self.assertEqual(response.status_code, 404)
        self.task_a.refresh_from_db()
        self.assertFalse(self.task_a.is_completed)

    def test_business_b_cannot_delete_business_a_task_by_url(self):
        """Organization B attempting to delete Organization A's task gets 404."""
        response = self.client_b.post(reverse("task_delete", kwargs={"pk": self.task_a.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.task_a.pk).exists())

    def test_task_can_only_link_to_records_from_own_business(self):
        """A task cannot link to contacts, deals, or team members from another business."""
        # 1. Attempt linking to contact_b (from Org B)
        resp_bad_contact = self.client_a.post(
            reverse("task_create"),
            {
                "title": "Bad Contact Task",
                "task_type": "CALL",
                "contact": self.contact_b.pk,  # From Org B
            },
        )
        self.assertEqual(resp_bad_contact.status_code, 200)
        self.assertFalse(Task.objects.filter(title="Bad Contact Task").exists())

        # 2. Attempt linking to deal_b (from Org B)
        resp_bad_deal = self.client_a.post(
            reverse("task_create"),
            {
                "title": "Bad Deal Task",
                "task_type": "MEETING",
                "deal": self.deal_b.pk,  # From Org B
            },
        )
        self.assertEqual(resp_bad_deal.status_code, 200)
        self.assertFalse(Task.objects.filter(title="Bad Deal Task").exists())

        # 3. Attempt assigning to owner_b (from Org B)
        resp_bad_user = self.client_a.post(
            reverse("task_create"),
            {
                "title": "Bad Assignee Task",
                "task_type": "EMAIL",
                "assigned_to": self.owner_b.pk,  # From Org B
            },
        )
        self.assertEqual(resp_bad_user.status_code, 200)
        self.assertFalse(Task.objects.filter(title="Bad Assignee Task").exists())

    def test_task_linked_to_deal_takes_contact_from_deal(self):
        """If a task is linked to a deal, its contact is automatically populated from the deal."""
        resp = self.client_a.post(
            reverse("task_create"),
            {
                "title": "Deal Task With Auto Contact",
                "task_type": "TODO",
                "deal": self.deal_a.pk,
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        created_task = Task.objects.get(title="Deal Task With Auto Contact")
        self.assertEqual(created_task.contact, self.deal_a.contact)
        self.assertEqual(created_task.company, self.deal_a.company)

    def test_member_cannot_edit_tasks_assigned_to_others(self):
        """A Member cannot edit tasks assigned to others (unless created by them)."""
        # Task assigned to owner_a and created by owner_a
        admin_task = Task.objects.create(
            organization=self.org_a,
            title="Owner Secret Task",
            task_type="TODO",
            assigned_to=self.owner_a,
            created_by=self.owner_a,
        )
        resp = self.client_member.post(
            reverse("task_update", kwargs={"pk": admin_task.pk}),
            {"title": "Member Altered Task", "task_type": "TODO"},
        )
        # Denied and redirected
        self.assertEqual(resp.status_code, 302)
        admin_task.refresh_from_db()
        self.assertEqual(admin_task.title, "Owner Secret Task")

    def test_member_can_edit_and_complete_tasks_assigned_to_or_created_by_them(self):
        """A Member can edit and complete tasks assigned to them or created by them."""
        # 1. Member edits task_a (which is assigned to member_a)
        resp_edit = self.client_member.post(
            reverse("task_update", kwargs={"pk": self.task_a.pk}),
            {
                "title": "Call John regarding updated terms",
                "task_type": "CALL",
                "assigned_to": self.member_a.pk,
            },
            follow=True,
        )
        self.assertEqual(resp_edit.status_code, 200)
        self.task_a.refresh_from_db()
        self.assertEqual(self.task_a.title, "Call John regarding updated terms")
        self.assertEqual(self.task_a.assigned_to, self.member_a)

        # 2. Member completes task_a (assigned to them)
        resp_done = self.client_member.post(
            reverse("task_toggle_done", kwargs={"pk": self.task_a.pk}),
            follow=True,
        )
        self.assertEqual(resp_done.status_code, 200)
        self.task_a.refresh_from_db()
        self.assertTrue(self.task_a.is_completed)
        self.assertEqual(self.task_a.completed_by, self.member_a)

        # 3. Member completes a task created by them (even if unassigned)
        member_created_task = Task.objects.create(
            organization=self.org_a,
            title="Member Created Task",
            task_type="TODO",
            created_by=self.member_a,
            assigned_to=None,
        )
        resp_done_2 = self.client_member.post(
            reverse("task_toggle_done", kwargs={"pk": member_created_task.pk}),
            follow=True,
        )
        self.assertEqual(resp_done_2.status_code, 200)
        member_created_task.refresh_from_db()
        self.assertTrue(member_created_task.is_completed)

    def test_member_cannot_delete_task(self):
        """A Member cannot delete a task (gets redirected and task is retained)."""
        response = self.client_member.post(reverse("task_delete", kwargs={"pk": self.task_a.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(pk=self.task_a.pk).exists())

    def test_owner_and_admin_can_delete_task_with_confirmation_and_audit(self):
        """Owner and Admin can delete tasks with audit logging."""
        client_admin = Client()
        client_admin.force_login(self.admin_a)
        resp_del = client_admin.post(reverse("task_delete", kwargs={"pk": self.task_a.pk}))
        self.assertRedirects(resp_del, reverse("task_list"))
        self.assertFalse(Task.objects.filter(pk=self.task_a.pk).exists())

        # Verify AuditLog
        del_log = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="DELETE",
            target_model="Task",
            target_id=str(self.task_a.pk),
        ).first()
        self.assertIsNotNone(del_log)
        self.assertEqual(del_log.user, self.admin_a)

    def test_overdue_and_today_filters_and_menu_badge_count(self):
        """Tests overdue and today filtering and verifies context processor menu badge count."""
        import datetime
        today = timezone.localdate()
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)

        # 1. Overdue task assigned to member_a
        t_overdue = Task.objects.create(
            organization=self.org_a,
            title="Overdue Client Followup",
            task_type="CALL",
            due_date=yesterday,
            assigned_to=self.member_a,
            is_completed=False,
        )

        # 2. Today task assigned to member_a (self.task_a is also due today!)
        # So member_a has t_overdue (1) + task_a (1) = 2 overdue/today tasks

        # 3. Upcoming task assigned to member_a
        t_upcoming = Task.objects.create(
            organization=self.org_a,
            title="Upcoming Meeting",
            task_type="MEETING",
            due_date=tomorrow,
            assigned_to=self.member_a,
            is_completed=False,
        )

        # 4. Completed task due yesterday (should NOT be overdue or in badge!)
        t_done = Task.objects.create(
            organization=self.org_a,
            title="Done Yesterday Task",
            task_type="EMAIL",
            due_date=yesterday,
            assigned_to=self.member_a,
            is_completed=True,
        )

        # 5. Overdue task assigned to owner_a (should NOT be in member_a's menu badge)
        t_owner_overdue = Task.objects.create(
            organization=self.org_a,
            title="Owner Overdue Task",
            task_type="CALL",
            due_date=yesterday,
            assigned_to=self.owner_a,
            is_completed=False,
        )

        # Check menu badge count for member_a: t_overdue + task_a = 2
        resp_member = self.client_member.get(reverse("task_list"))
        self.assertEqual(resp_member.status_code, 200)
        self.assertEqual(resp_member.context["my_reminders_count"], 2)

        # Test 'overdue' tab: should include t_overdue, not t_done or task_a
        resp_overdue = self.client_a.get(reverse("task_list"), {"tab": "overdue"})
        self.assertEqual(resp_overdue.status_code, 200)
        overdue_tasks = list(resp_overdue.context["page_obj"])
        self.assertIn(t_overdue, overdue_tasks)
        self.assertIn(t_owner_overdue, overdue_tasks)
        self.assertNotIn(t_done, overdue_tasks)
        self.assertNotIn(self.task_a, overdue_tasks)

        # Test 'today' tab: should include task_a
        resp_today = self.client_a.get(reverse("task_list"), {"tab": "today"})
        self.assertEqual(resp_today.status_code, 200)
        today_tasks = list(resp_today.context["page_obj"])
        self.assertIn(self.task_a, today_tasks)
        self.assertNotIn(t_overdue, today_tasks)

    def test_marking_done_and_undoing(self):
        """Marking done marks task complete with audit logging, and undoing restores it."""
        self.assertFalse(self.task_a.is_completed)

        # 1. Mark Done
        self.client_a.post(reverse("task_toggle_done", kwargs={"pk": self.task_a.pk}))
        self.task_a.refresh_from_db()
        self.assertTrue(self.task_a.is_completed)
        self.assertEqual(self.task_a.completed_by, self.owner_a)

        log_done = AuditLog.objects.filter(
            organization=self.org_a,
            action_type="COMPLETE",
            target_model="Task",
            target_id=str(self.task_a.pk),
        ).first()
        self.assertIsNotNone(log_done)

        # 2. Undo
        self.client_a.post(reverse("task_toggle_done", kwargs={"pk": self.task_a.pk}))
        self.task_a.refresh_from_db()
        self.assertFalse(self.task_a.is_completed)
        self.assertIsNone(self.task_a.completed_by)

    def test_contact_and_deal_pages_show_tasks_and_add_task_button(self):
        """Contact and Deal pages show associated tasks and include an Add Task button."""
        # Contact page
        resp_contact = self.client_a.get(reverse("contact_detail", kwargs={"pk": self.contact_a.pk}))
        self.assertEqual(resp_contact.status_code, 200)
        self.assertIn(self.task_a, list(resp_contact.context["tasks"]))
        self.assertContains(resp_contact, f"contact_id={self.contact_a.pk}")

        # Deal edit page
        resp_deal = self.client_a.get(reverse("deal_update", kwargs={"pk": self.deal_a.pk}))
        self.assertEqual(resp_deal.status_code, 200)
        self.assertIn(self.task_a, list(resp_deal.context["tasks"]))
        self.assertContains(resp_deal, f"deal_id={self.deal_a.pk}")

    def test_welcome_page_today_box_shows_overdue_and_today_tasks(self):
        """The Welcome dashboard includes the 'Today' box listing overdue and due-today tasks."""
        response = self.client_member.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        today_tasks = list(response.context["today_and_overdue_tasks"])
        self.assertIn(self.task_a, today_tasks)
        self.assertContains(response, "todayRemindersBox")
        self.assertContains(response, self.task_a.title)

    # ==========================================================================
    # DASHBOARD MODULE TESTS
    # ==========================================================================

    def test_dashboard_numbers_are_correct_for_known_test_data(self):
        """The dashboard summary cards and charts calculate correct numbers for known test data."""
        import datetime
        today = timezone.localdate()
        yesterday = today - datetime.timedelta(days=1)

        # 1. Contacts: self.contact_a already exists (LEAD). Add a CUSTOMER contact.
        contact_customer = Contact.objects.create(
            organization=self.org_a,
            first_name="Alice",
            last_name="Customer",
            email="alice@customer.com",
            status="CUSTOMER",
        )

        # 2. Deals:
        # self.deal_a is in 'New' stage with value 50,000.00
        # Add a deal in 'Proposal' stage with value 100,000.00
        deal_proposal = Deal.objects.create(
            organization=self.org_a,
            title="Proposal Deal",
            value=Decimal("100000.00"),
            contact=self.contact_a,
            stage=self.stage_a_proposal,
            owner=self.owner_a,
        )
        # Add a deal in 'Won' stage with value 200,000.00 closed today
        deal_won = Deal.objects.create(
            organization=self.org_a,
            title="Won Deal",
            value=Decimal("200000.00"),
            contact=self.contact_a,
            stage=self.stage_a_won,
            owner=self.owner_a,
            closed_date=today,
        )
        # Add a deal in 'Lost' stage with value 30,000.00
        deal_lost = Deal.objects.create(
            organization=self.org_a,
            title="Lost Deal",
            value=Decimal("30000.00"),
            contact=self.contact_a,
            stage=self.stage_a_lost,
            owner=self.owner_a,
            closed_date=today,
        )

        # 3. Tasks:
        # self.task_a is due today (due_date=today, is_completed=False)
        # Add an overdue task:
        task_overdue = Task.objects.create(
            organization=self.org_a,
            title="Overdue Audit Task",
            task_type="CALL",
            due_date=yesterday,
            is_completed=False,
            assigned_to=self.owner_a,
        )

        response = self.client_a.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

        # Verify Contacts: 2 total (contact_a + contact_customer), 2 new this month
        self.assertEqual(response.context["total_contacts_count"], 2)
        self.assertEqual(response.context["new_contacts_count"], 2)

        # Verify Open Pipeline: deal_a (50,000) + deal_proposal (100,000) = 150,000.00
        self.assertEqual(response.context["open_deals_count"], 2)
        self.assertEqual(response.context["total_open_pipeline_value"], Decimal("150000.00"))

        # Verify Deals Won: deal_won (1 deal, value 200,000.00)
        self.assertEqual(response.context["deals_won_count"], 1)
        self.assertEqual(response.context["deals_won_value"], Decimal("200000.00"))

        # Verify Tasks: 1 due today (task_a for client_a / org), 1 overdue (task_overdue)
        self.assertEqual(response.context["tasks_due_today_count"], 1)
        self.assertEqual(response.context["tasks_overdue_count"], 1)

        # Verify Chart Data
        self.assertIn("New", response.context["pipeline_chart_labels"])
        self.assertIn("Proposal", response.context["pipeline_chart_labels"])
        self.assertTrue(response.context["pipeline_has_data"])
        self.assertTrue(response.context["contacts_has_data"])
        self.assertEqual(response.context["contacts_status_values"], [1, 1, 0])  # 1 Lead, 1 Customer, 0 Inactive

    def test_business_b_data_never_appears_in_business_a_dashboard(self):
        """Organization B's deals, contacts, and tasks never appear in Organization A's dashboard."""
        today = timezone.localdate()

        # Org B creates massive won deal
        deal_won_b = Deal.objects.create(
            organization=self.org_b,
            title="Mega Org B Deal",
            value=Decimal("999999.00"),
            contact=self.contact_b,
            stage=self.stage_b_won,
            owner=self.owner_b,
            closed_date=today,
        )
        # Org B creates open deal
        deal_open_b = Deal.objects.create(
            organization=self.org_b,
            title="Open Org B Deal",
            value=Decimal("500000.00"),
            contact=self.contact_b,
            stage=self.stage_b_new,
            owner=self.owner_b,
        )

        # Org A visits dashboard
        response_a = self.client_a.get(reverse("dashboard"))
        self.assertEqual(response_a.status_code, 200)

        # Org A should only see self.contact_a (1 contact)
        self.assertEqual(response_a.context["total_contacts_count"], 1)
        # Org A open deals should only be self.deal_a (50,000.00)
        self.assertEqual(response_a.context["open_deals_count"], 1)
        self.assertEqual(response_a.context["total_open_pipeline_value"], Decimal("50000.00"))
        # Org A won deals should be 0 (deal_won_b must NOT appear)
        self.assertEqual(response_a.context["deals_won_count"], 0)
        self.assertEqual(response_a.context["deals_won_value"], Decimal("0.00"))

        # Org B visits dashboard: deal_b (10,000.00) + deal_open_b (500,000.00) = 510,000.00
        response_b = self.client_b.get(reverse("dashboard"))
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_b.context["deals_won_count"], 1)
        self.assertEqual(response_b.context["deals_won_value"], Decimal("999999.00"))
        self.assertEqual(response_b.context["total_open_pipeline_value"], Decimal("510000.00"))

    def test_member_sees_only_their_own_deal_and_task_numbers(self):
        """A Member sees only their own numbers for deals and tasks, and the business-wide contact count."""
        today = timezone.localdate()

        # Create another deal owned by owner_a (not member_a)
        deal_owner = Deal.objects.create(
            organization=self.org_a,
            title="Owner Secret Deal",
            value=Decimal("80000.00"),
            contact=self.contact_a,
            stage=self.stage_a_new,
            owner=self.owner_a,
        )
        # Create a won deal owned by owner_a
        deal_owner_won = Deal.objects.create(
            organization=self.org_a,
            title="Owner Won Deal",
            value=Decimal("120000.00"),
            contact=self.contact_a,
            stage=self.stage_a_won,
            owner=self.owner_a,
            closed_date=today,
        )
        # Create a task assigned to owner_a
        task_owner = Task.objects.create(
            organization=self.org_a,
            title="Owner Task Due Today",
            task_type="EMAIL",
            due_date=today,
            assigned_to=self.owner_a,
            is_completed=False,
        )

        # member_a logs in
        response_member = self.client_member.get(reverse("dashboard"))
        self.assertEqual(response_member.status_code, 200)

        # 1. Contacts count is business-wide (1 contact in Org A)
        self.assertEqual(response_member.context["total_contacts_count"], 1)

        # 2. Deals: Member only sees self.deal_a (value 50,000.00)
        self.assertEqual(response_member.context["open_deals_count"], 1)
        self.assertEqual(response_member.context["total_open_pipeline_value"], Decimal("50000.00"))

        # 3. Won deals: Member owns 0 won deals
        self.assertEqual(response_member.context["deals_won_count"], 0)
        self.assertEqual(response_member.context["deals_won_value"], Decimal("0.00"))

        # 4. Tasks: Member only sees self.task_a (assigned to member_a)
        self.assertEqual(response_member.context["tasks_due_today_count"], 1)

    def test_date_filters_change_results_correctly(self):
        """The date filters (this_month, last_30_days, last_6_months) update the cards and charts correctly."""
        import datetime
        today = timezone.localdate()

        # Deal won today (within this_month, last_30_days, and last_6_months)
        deal_won_today = Deal.objects.create(
            organization=self.org_a,
            title="Won Today Deal",
            value=Decimal("50000.00"),
            contact=self.contact_a,
            stage=self.stage_a_won,
            owner=self.owner_a,
            closed_date=today,
        )

        # Deal won 45 days ago (NOT in this_month, NOT in last_30_days, but IN last_6_months)
        date_45_days_ago = today - datetime.timedelta(days=45)
        deal_won_45_days = Deal.objects.create(
            organization=self.org_a,
            title="Won 45 Days Ago Deal",
            value=Decimal("75000.00"),
            contact=self.contact_a,
            stage=self.stage_a_won,
            owner=self.owner_a,
            closed_date=date_45_days_ago,
        )

        # 1. Test "this_month"
        resp_month = self.client_a.get(reverse("dashboard"), {"period": "this_month"})
        self.assertEqual(resp_month.status_code, 200)
        self.assertEqual(resp_month.context["deals_won_count"], 1)
        self.assertEqual(resp_month.context["deals_won_value"], Decimal("50000.00"))

        # 2. Test "last_30_days"
        resp_30d = self.client_a.get(reverse("dashboard"), {"period": "last_30_days"})
        self.assertEqual(resp_30d.status_code, 200)
        self.assertEqual(resp_30d.context["deals_won_count"], 1)
        self.assertEqual(resp_30d.context["deals_won_value"], Decimal("50000.00"))

        # 3. Test "last_6_months" -> should include BOTH won deals!
        resp_6m = self.client_a.get(reverse("dashboard"), {"period": "last_6_months"})
        self.assertEqual(resp_6m.status_code, 200)
        self.assertEqual(resp_6m.context["deals_won_count"], 2)
        self.assertEqual(resp_6m.context["deals_won_value"], Decimal("125000.00"))

    def test_dashboard_loads_with_empty_business(self):
        """The dashboard loads cleanly with 0 errors and friendly empty states when a business has no data."""
        # Create empty Organization C
        org_c = Organization.objects.create(name="Gamma Startup", slug="gamma-startup")
        owner_c = User.objects.create_user(
            email="owner_c@gamma.com",
            password="Password123!",
            first_name="Grace",
            last_name="Gamma",
            organization=org_c,
            role="OWNER",
            is_email_verified=True,
        )

        client_c = Client()
        client_c.force_login(owner_c)

        response = client_c.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

        # Check all metrics are 0 / Decimal("0.00")
        self.assertEqual(response.context["total_contacts_count"], 0)
        self.assertEqual(response.context["new_contacts_count"], 0)
        self.assertEqual(response.context["open_deals_count"], 0)
        self.assertEqual(response.context["total_open_pipeline_value"], Decimal("0.00"))
        self.assertEqual(response.context["deals_won_count"], 0)
        self.assertEqual(response.context["deals_won_value"], Decimal("0.00"))
        self.assertEqual(response.context["tasks_overdue_count"], 0)
        self.assertEqual(response.context["tasks_due_today_count"], 0)

        # Check friendly empty states
        self.assertFalse(response.context["pipeline_has_data"])
        self.assertFalse(response.context["won_has_data"])
        self.assertFalse(response.context["contacts_has_data"])
        self.assertContains(response, "Add your first deal to see your pipeline")
        self.assertContains(response, "No contacts added yet")
        self.assertContains(response, "No activity recorded yet")

    # ==========================================================================
    # IMPORT & EXPORT MODULE TESTS
    # ==========================================================================

    def test_valid_file_imports_correctly(self):
        """A valid CSV file for companies and contacts imports cleanly with UTF-8 / BOM."""
        # 1. Company Import with BOM
        bom_utf8 = b"\xef\xbb\xbfname,industry,website,city,phone\nAcme South,Logistics,https://south.acme.com,Chennai,+91 9988776655\nAcme North,Manufacturing,https://north.acme.com,Delhi,+91 9988776644\n"
        company_file = SimpleUploadedFile("companies.csv", bom_utf8, content_type="text/csv")
        resp_comp = self.client_a.post(reverse("company_import"), {"file": company_file})
        self.assertEqual(resp_comp.status_code, 200)
        self.assertEqual(resp_comp.context["imported_count"], 2)
        self.assertEqual(resp_comp.context["skipped_count"], 0)
        self.assertEqual(resp_comp.context["failed_count"], 0)
        self.assertTrue(Company.objects.filter(organization=self.org_a, name="Acme South").exists())
        self.assertTrue(Company.objects.filter(organization=self.org_a, name="Acme North").exists())

        # 2. Contact Import (owner should be importing user, status defaults or parses)
        contacts_csv = "name,email,phone,job_title,company,status\nPriya Patel,priya@acmesouth.com,9988112233,Lead Architect,Acme South,Customer\nVikram Singh,vikram@acmenorth.com,9988112244,Quality Lead,Acme North,Lead\n"
        contact_file = SimpleUploadedFile("contacts.csv", contacts_csv.encode("utf-8"), content_type="text/csv")
        resp_cont = self.client_a.post(reverse("contact_import"), {"file": contact_file})
        self.assertEqual(resp_cont.status_code, 200)
        self.assertEqual(resp_cont.context["imported_count"], 2)
        self.assertEqual(resp_cont.context["skipped_count"], 0)
        self.assertEqual(resp_cont.context["failed_count"], 0)

        priya = Contact.objects.get(organization=self.org_a, email="priya@acmesouth.com")
        self.assertEqual(priya.first_name, "Priya")
        self.assertEqual(priya.last_name, "Patel")
        self.assertEqual(priya.owner, self.owner_a)
        self.assertEqual(priya.status, "CUSTOMER")
        self.assertEqual(priya.company.name, "Acme South")

    def test_import_skips_duplicates(self):
        """Rows whose email exists (contacts) or name exists (companies) are safely skipped."""
        # self.comp_a has name "Alpha Client"
        comp_csv = "name,industry,website,city,phone\nAlpha Client,Updated Industry,https://alpha.com,New York,111\nBrand New Co,Finance,,Mumbai,222\n"
        resp_comp = self.client_a.post(
            reverse("company_import"),
            {"file": SimpleUploadedFile("comps.csv", comp_csv.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp_comp.status_code, 200)
        self.assertEqual(resp_comp.context["imported_count"], 1)
        self.assertEqual(resp_comp.context["skipped_count"], 1)

        # self.comp_a should NOT have been overwritten
        self.comp_a.refresh_from_db()
        self.assertEqual(self.comp_a.industry, "Software")

        # self.contact_a has email "john@alphaclient.com"
        cont_csv = "name,email,phone,job_title,company,status\nJohn Doe Duplicate,john@alphaclient.com,999,CEO,Alpha Client,Lead\nNew User,newuser@alpha.com,888,COO,Alpha Client,Lead\n"
        resp_cont = self.client_a.post(
            reverse("contact_import"),
            {"file": SimpleUploadedFile("conts.csv", cont_csv.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp_cont.status_code, 200)
        self.assertEqual(resp_cont.context["imported_count"], 1)
        self.assertEqual(resp_cont.context["skipped_count"], 1)

    def test_invalid_rows_reported_with_row_numbers(self):
        """Invalid rows (missing name, bad email, bad status) report row numbers and offer downloadable failed CSV."""
        # Row 1 is header
        # Row 2 is valid
        # Row 3 is missing name
        # Row 4 has invalid email
        # Row 5 has invalid status
        cont_csv = (
            "name,email,phone,job_title,company,status\n"
            "Good Contact,good@example.com,111,VP,Alpha Client,Lead\n"
            ",missingname@example.com,222,Dev,Alpha Client,Lead\n"
            "Bad Email Contact,not-an-email-at-all,333,Dev,Alpha Client,Lead\n"
            "Bad Status Contact,badstatus@example.com,444,Dev,Alpha Client,SuperVIPStatus\n"
        )
        resp = self.client_a.post(
            reverse("contact_import"),
            {"file": SimpleUploadedFile("invalid.csv", cont_csv.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["imported_count"], 1)
        self.assertEqual(resp.context["failed_count"], 3)

        failures = resp.context["failures"]
        failure_rows = [f["row"] for f in failures]
        self.assertEqual(failure_rows, [3, 4, 5])
        self.assertIn("name is required", failures[0]["reason"].lower())
        self.assertIn("invalid email", failures[1]["reason"].lower())
        self.assertIn("invalid status", failures[2]["reason"].lower())

        # Test downloading the failed rows CSV
        resp_failed_csv = self.client_a.get(reverse("contact_import_failed_csv"))
        self.assertEqual(resp_failed_csv.status_code, 200)
        failed_csv_content = b"".join(resp_failed_csv.streaming_content).decode("utf-8")
        self.assertIn("Contact name is required.", failed_csv_content)
        self.assertIn("Invalid email format", failed_csv_content)
        self.assertIn("Invalid status", failed_csv_content)
        self.assertIn(",3\r\n", failed_csv_content)

    def test_company_in_another_business_never_matched_or_modified(self):
        """A company in another business is never matched or modified during contact import."""
        # Org B has comp_b named "Alpha Client" with industry "Healthcare"
        self.assertEqual(self.comp_b.organization, self.org_b)
        self.assertEqual(self.comp_b.industry, "Healthcare")

        # Org A imports a contact with company "Unique Org B Enterprise"
        # First, ensure Org B has a company named "Unique Org B Enterprise"
        unique_comp_b = Company.objects.create(
            organization=self.org_b,
            name="Unique Org B Enterprise",
            industry="Robotics",
            city="Tokyo",
        )

        cont_csv = "name,email,phone,job_title,company,status\nKenji Sato,kenji@unique.com,12345,CTO,Unique Org B Enterprise,Lead\n"
        resp = self.client_a.post(
            reverse("contact_import"),
            {"file": SimpleUploadedFile("cont_cross.csv", cont_csv.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["imported_count"], 1)

        # 1. unique_comp_b in Org B must NOT be touched or modified
        unique_comp_b.refresh_from_db()
        self.assertEqual(unique_comp_b.organization, self.org_b)
        self.assertEqual(unique_comp_b.contacts.count(), 0)

        # 2. A brand-new company must have been created in Org A with the same name
        org_a_comp = Company.objects.get(organization=self.org_a, name="Unique Org B Enterprise")
        self.assertNotEqual(org_a_comp.pk, unique_comp_b.pk)

        # 3. The contact belongs to Org A and links to org_a_comp
        contact = Contact.objects.get(organization=self.org_a, email="kenji@unique.com")
        self.assertEqual(contact.company, org_a_comp)

    def test_member_cannot_import_or_export(self):
        """A team Member cannot import or export any data (redirected or forbidden)."""
        # Imports
        self.assertEqual(self.client_member.get(reverse("company_import")).status_code, 302)
        self.assertEqual(self.client_member.get(reverse("contact_import")).status_code, 302)

        # Exports
        self.assertEqual(self.client_member.get(reverse("company_export")).status_code, 302)
        self.assertEqual(self.client_member.get(reverse("contact_export")).status_code, 302)
        self.assertEqual(self.client_member.get(reverse("deal_export")).status_code, 302)
        self.assertEqual(self.client_member.get(reverse("task_export")).status_code, 302)

        # Settings & Full Download
        self.assertEqual(self.client_member.get(reverse("settings")).status_code, 302)
        resp_down = self.client_member.get(reverse("download_all_data"))
        self.assertEqual(resp_down.status_code, 403)

    def test_oversized_or_non_csv_file_rejected(self):
        """Files that are not .csv or larger than 2 MB are rejected with friendly messages."""
        # 1. Non-CSV file (.xlsx)
        excel_file = SimpleUploadedFile("contacts.xlsx", b"dummy excel content", content_type="application/vnd.ms-excel")
        resp_bad_ext = self.client_a.post(reverse("contact_import"), {"file": excel_file})
        self.assertEqual(resp_bad_ext.status_code, 200)
        self.assertContains(resp_bad_ext, "Only .csv files are accepted")

        # 2. Oversized file (> 2 MB)
        big_content = b"a" * (2 * 1024 * 1024 + 100)
        big_file = SimpleUploadedFile("oversized.csv", big_content, content_type="text/csv")
        resp_big = self.client_a.post(reverse("company_import"), {"file": big_file})
        self.assertEqual(resp_big.status_code, 200)
        self.assertContains(resp_big, "File exceeds the 2 MB limit")

    def test_exported_cells_starting_with_formula_prefixes_are_neutralised(self):
        """Cells starting with =, +, -, @ are prefixed with ' on export and sanitized on import."""
        # 1. Test neutralization on import
        bad_csv = "name,industry,website,city,phone\n=cmd|'/C calc'!A0,+SUM(1+1),https://safe.com,-CityName,@AtCompany\n"
        self.client_a.post(
            reverse("company_import"),
            {"file": SimpleUploadedFile("formula.csv", bad_csv.encode("utf-8"), content_type="text/csv")},
        )
        saved_comp = Company.objects.get(organization=self.org_a, city="'-CityName")
        self.assertTrue(saved_comp.name.startswith("'="))
        self.assertTrue(saved_comp.industry.startswith("'+"))
        self.assertTrue(saved_comp.city.startswith("'-"))

        # 2. Test neutralization on export
        Contact.objects.create(
            organization=self.org_a,
            first_name="=FormulaUser",
            last_name="+PlusUser",
            email="formula@test.com",
            job_title="@JobTitle",
        )
        resp_export = self.client_a.get(reverse("contact_export"))
        self.assertEqual(resp_export.status_code, 200)
        csv_text = b"".join(resp_export.streaming_content).decode("utf-8")
        self.assertIn("'=FormulaUser", csv_text)
        self.assertIn("'+PlusUser", csv_text)
        self.assertIn("'@JobTitle", csv_text)

    def test_full_data_zip_contains_only_owners_business_data(self):
        """The 'Download all my data' ZIP contains only the owner's organization data across all models."""
        resp = self.client_a.get(reverse("download_all_data"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")

        # Read zip archive
        zip_file = zipfile.ZipFile(io.BytesIO(resp.content))
        file_list = zip_file.namelist()
        self.assertEqual(set(file_list), {"companies.csv", "contacts.csv", "deals.csv", "tasks.csv", "notes.csv"})

        # Contacts CSV must have Org A contacts, not Org B
        contacts_csv = zip_file.read("contacts.csv").decode("utf-8-sig")
        self.assertIn(self.contact_a.email, contacts_csv)
        self.assertNotIn(self.contact_b.email, contacts_csv)

        # Deals CSV must have Org A deals, not Org B
        deals_csv = zip_file.read("deals.csv").decode("utf-8-sig")
        self.assertIn(self.deal_a.title, deals_csv)
        self.assertNotIn(self.deal_b.title, deals_csv)

        # Admin cannot access download_all_data (Owner only)
        client_admin = Client()
        client_admin.force_login(self.admin_a)
        resp_admin = client_admin.get(reverse("download_all_data"))
        self.assertEqual(resp_admin.status_code, 403)

    def test_failed_import_leaves_no_partial_data(self):
        """A crash or unhandled exception during an import transaction leaves zero partial data."""
        # Initial company count in Org A
        init_comp_count = Company.objects.filter(organization=self.org_a).count()

        # CSV with 2 rows. We simulate a crash during row 2 saving
        comp_csv = "name,industry,website,city,phone\nTemp Co 1,Fin,https://temp1.com,Delhi,111\nTemp Co 2,Fin,https://temp2.com,Delhi,222\n"

        original_create = Company.objects.create

        def fail_on_second_create(*args, **kwargs):
            if kwargs.get("name") == "Temp Co 2":
                raise RuntimeError("Simulated database failure mid-import!")
            return original_create(*args, **kwargs)

        with patch.object(Company.objects, "create", side_effect=fail_on_second_create):
            resp = self.client_a.post(
                reverse("company_import"),
                {"file": SimpleUploadedFile("crash.csv", comp_csv.encode("utf-8"), content_type="text/csv")},
            )
            # Friendly error shown
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Import process failed")

        # Verify atomic rollback: Temp Co 1 was NOT committed!
        self.assertEqual(Company.objects.filter(organization=self.org_a).count(), init_comp_count)
        self.assertFalse(Company.objects.filter(organization=self.org_a, name="Temp Co 1").exists())




