from django.test import TestCase
from organizations.models import Organization
from organizations.middleware import set_current_organization, clear_current_organization
from crm_core.models import Company, Contact, Deal, Task

class TenantIsolationTestCase(TestCase):
    """
    Automated verification of multi-tenant isolation.
    Proves that data belonging to Business A is physically invisible to Business B.
    """
    def setUp(self):
        clear_current_organization()
        self.org_a = Organization.objects.create(name="Acme Corp")
        self.org_b = Organization.objects.create(name="Globex Inc")

    def tearDown(self):
        clear_current_organization()

    def test_tenant_data_is_strictly_isolated(self):
        # 1. Simulate Organization A context
        set_current_organization(self.org_a)
        company_a = Company.objects.create(name="Acme Client 1")
        contact_a = Contact.objects.create(
            company=company_a,
            first_name="Alice",
            last_name="Smith",
            email="alice@acme.com",
        )
        deal_a = Deal.objects.create(
            title="Acme Big Deal",
            value=10000.00,
            contact=contact_a,
            company=company_a,
        )

        # 2. Simulate Organization B context
        set_current_organization(self.org_b)
        company_b = Company.objects.create(name="Globex Client 1")
        contact_b = Contact.objects.create(
            company=company_b,
            first_name="Bob",
            last_name="Jones",
            email="bob@globex.com",
        )

        # 3. Verify Org B CANNOT see Org A's records
        org_b_companies = list(Company.objects.all())
        self.assertIn(company_b, org_b_companies)
        self.assertNotIn(company_a, org_b_companies)
        self.assertEqual(Company.objects.count(), 1)

        org_b_contacts = list(Contact.objects.all())
        self.assertIn(contact_b, org_b_contacts)
        self.assertNotIn(contact_a, org_b_contacts)
        self.assertEqual(Contact.objects.count(), 1)

        # Org B should see 0 deals (deal_a was created by Org A)
        self.assertEqual(Deal.objects.count(), 0)

        # 4. Switch back to Organization A context
        set_current_organization(self.org_a)
        org_a_companies = list(Company.objects.all())
        self.assertIn(company_a, org_a_companies)
        self.assertNotIn(company_b, org_a_companies)
        self.assertEqual(Company.objects.count(), 1)

    def test_direct_id_query_cross_tenant_returns_empty(self):
        # Create record in Org A
        set_current_organization(self.org_a)
        company_a = Company.objects.create(name="Secret Acme Data")

        # Switch to Org B and attempt to query company_a directly by PK
        set_current_organization(self.org_b)
        leak_attempt = Company.objects.filter(pk=company_a.pk).first()

        # Must return None (impossible to access cross-tenant by ID)
        self.assertIsNone(leak_attempt)

    def test_automatic_tenant_assignment_on_save(self):
        # When an organization context is active, new records automatically bind to it
        set_current_organization(self.org_a)
        company = Company(name="Auto Assigned Co")
        company.save()

        self.assertEqual(company.organization, self.org_a)
