import datetime
import decimal
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from crm_core.models import Company, Contact, Deal, Stage
from organizations.models import Organization
from payments.models import Invoice
from payments.paypal import (
    PayPalAPIError,
    PayPalConfigError,
    clear_token_cache,
)

User = get_user_model()


class PayPalInvoicingTestCase(TestCase):
    def setUp(self):
        clear_token_cache()

        # Business A
        self.org_a = Organization.objects.create(
            name="Apex Lab",
            slug="apex-lab",
            plan_status="trial",
            trial_ends_at=timezone.now() + datetime.timedelta(days=14),
        )
        self.owner_a = User.objects.create_user(
            email="owner_a@apexlab.com",
            password="Password123!",
            first_name="Alice",
            last_name="Owner",
            organization=self.org_a,
            role="OWNER",
            is_email_verified=True,
        )
        self.admin_a = User.objects.create_user(
            email="admin_a@apexlab.com",
            password="Password123!",
            first_name="Alan",
            last_name="Admin",
            organization=self.org_a,
            role="ADMIN",
            is_email_verified=True,
        )
        self.member_a = User.objects.create_user(
            email="member_a@apexlab.com",
            password="Password123!",
            first_name="Mike",
            last_name="Member",
            organization=self.org_a,
            role="MEMBER",
            is_email_verified=True,
        )

        # Business B (for cross-tenant checks)
        self.org_b = Organization.objects.create(
            name="Bravo Corp",
            slug="bravo-corp",
            plan_status="trial",
            trial_ends_at=timezone.now() + datetime.timedelta(days=14),
        )
        self.owner_b = User.objects.create_user(
            email="owner_b@bravocorp.com",
            password="Password123!",
            first_name="Bob",
            last_name="Owner",
            organization=self.org_b,
            role="OWNER",
            is_email_verified=True,
        )

        # Stages for Org A
        self.stage_lead = Stage.objects.create(
            organization=self.org_a,
            name="Lead",
            order=1,
            is_won=False,
            is_lost=False,
        )
        self.stage_won = Stage.objects.create(
            organization=self.org_a,
            name="Won",
            order=2,
            is_won=True,
            is_lost=False,
        )

        # Contact and Deals for Org A
        self.contact_a = Contact.objects.create(
            organization=self.org_a,
            first_name="John",
            last_name="Doe",
            email="buyer@sandbox.paypal.com",
        )
        self.deal_won = Deal.objects.create(
            organization=self.org_a,
            title="Enterprise Cloud Contract",
            value=decimal.Decimal("1500.00"),
            stage=self.stage_won,
            contact=self.contact_a,
            owner=self.owner_a,
        )
        self.deal_open = Deal.objects.create(
            organization=self.org_a,
            title="Discovery Pilot",
            value=decimal.Decimal("500.00"),
            stage=self.stage_lead,
            contact=self.contact_a,
            owner=self.owner_a,
        )

        self.client_a = Client()
        self.client_a.login(email="owner_a@apexlab.com", password="Password123!")

        self.client_b = Client()
        self.client_b.login(email="owner_b@bravocorp.com", password="Password123!")

        self.client_member = Client()
        self.client_member.login(email="member_a@apexlab.com", password="Password123!")

    @patch("payments.paypal.get_access_token", return_value="mock_access_token_123")
    @patch("payments.paypal.create_draft_invoice")
    @patch("payments.paypal.send_invoice")
    @patch("payments.paypal.fetch_invoice")
    @patch("payments.paypal.is_paypal_configured", return_value=True)
    def test_invoice_create_and_send_success(self, mock_cfg, mock_fetch, mock_send, mock_draft, mock_token):
        """Owner can successfully create and send a PayPal invoice for a Won deal."""
        mock_draft.return_value = {
            "id": "INV2-TEST-1234",
            "invoice_number": "INV-00101",
            "status": "DRAFT",
        }
        mock_send.return_value = {"status": "SENT"}
        mock_fetch.return_value = {
            "id": "INV2-TEST-1234",
            "status": "SENT",
            "payer_link": "https://www.sandbox.paypal.com/invoice/p/#TEST1234",
            "date_paid": None,
        }

        url = reverse("invoice_send", kwargs={"deal_id": self.deal_won.pk})
        resp = self.client_a.post(url, {
            "recipient_email": "buyer@sandbox.paypal.com",
            "amount": "1500.00",
            "currency": "USD",
            "description": "Enterprise Cloud Contract",
            "days_due": "7",
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Invoice.objects.filter(deal=self.deal_won, paypal_invoice_id="INV2-TEST-1234").exists())
        inv = Invoice.objects.get(deal=self.deal_won)
        self.assertEqual(inv.status, "SENT")
        self.assertEqual(inv.amount, decimal.Decimal("1500.00"))
        self.assertEqual(inv.payer_link, "https://www.sandbox.paypal.com/invoice/p/#TEST1234")

    @patch("payments.paypal.is_paypal_configured", return_value=True)
    def test_invoice_only_for_won_deals(self, mock_cfg):
        """Attempting to invoice an open deal is rejected."""
        url = reverse("invoice_send", kwargs={"deal_id": self.deal_open.pk})
        resp = self.client_a.post(url, {
            "recipient_email": "buyer@sandbox.paypal.com",
            "amount": "500.00",
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "PayPal invoices can only be generated for deals in the &#x27;Won&#x27; stage.")
        self.assertFalse(Invoice.objects.filter(deal=self.deal_open).exists())

    @patch("payments.paypal.is_paypal_configured", return_value=True)
    def test_second_active_invoice_blocked(self, mock_cfg):
        """A second active invoice for the same deal is blocked."""
        Invoice.objects.create(
            organization=self.org_a,
            deal=self.deal_won,
            paypal_invoice_id="INV2-FIRST-1111",
            invoice_number="INV-0001",
            amount=decimal.Decimal("1500.00"),
            currency="USD",
            status="SENT",
            recipient_email="buyer@sandbox.paypal.com",
            created_by=self.owner_a,
        )

        url = reverse("invoice_send", kwargs={"deal_id": self.deal_won.pk})
        resp = self.client_a.post(url, {
            "recipient_email": "buyer@sandbox.paypal.com",
            "amount": "1500.00",
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "An active invoice (#INV-0001) already exists")
        self.assertEqual(Invoice.objects.filter(deal=self.deal_won).count(), 1)

    @patch("payments.paypal.is_paypal_configured", return_value=True)
    def test_member_cannot_send(self, mock_cfg):
        """Members cannot create or send invoices."""
        url = reverse("invoice_send", kwargs={"deal_id": self.deal_won.pk})
        resp = self.client_member.post(url, {
            "recipient_email": "buyer@sandbox.paypal.com",
            "amount": "1500.00",
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Only workspace Owners and Admins can create and send PayPal invoices.")
        self.assertFalse(Invoice.objects.filter(deal=self.deal_won).exists())

    def test_business_b_cannot_see_or_refresh_business_a_invoices(self):
        """Business B cannot view, access, or refresh Business A's invoices."""
        inv_a = Invoice.objects.create(
            organization=self.org_a,
            deal=self.deal_won,
            paypal_invoice_id="INV2-ORGA-9999",
            invoice_number="INV-0099",
            amount=decimal.Decimal("1500.00"),
            currency="USD",
            status="SENT",
            recipient_email="buyer@sandbox.paypal.com",
            created_by=self.owner_a,
        )

        # Business B attempts to refresh Business A's invoice
        refresh_url = reverse("invoice_refresh", kwargs={"invoice_id": inv_a.pk})
        resp = self.client_b.post(refresh_url)
        self.assertEqual(resp.status_code, 404)

        # Invoices list for Business B shows 0 invoices
        list_url = reverse("invoice_list")
        resp_list = self.client_b.get(list_url)
        self.assertNotContains(resp_list, "INV-0099")

    @patch("payments.paypal.fetch_invoice")
    @patch("payments.paypal.is_paypal_configured", return_value=True)
    def test_refresh_updates_status_from_paypal_data(self, mock_cfg, mock_fetch):
        """Refreshing an invoice updates its status and date_paid from PayPal."""
        now_time = timezone.now()
        mock_fetch.return_value = {
            "id": "INV2-TEST-REFRESH",
            "status": "PAID",
            "payer_link": "https://www.sandbox.paypal.com/invoice/p/#PAID123",
            "date_paid": now_time,
        }

        inv = Invoice.objects.create(
            organization=self.org_a,
            deal=self.deal_won,
            paypal_invoice_id="INV2-TEST-REFRESH",
            invoice_number="INV-0077",
            amount=decimal.Decimal("1500.00"),
            currency="USD",
            status="SENT",
            recipient_email="buyer@sandbox.paypal.com",
            created_by=self.owner_a,
        )

        refresh_url = reverse("invoice_refresh", kwargs={"invoice_id": inv.pk})
        resp = self.client_a.post(refresh_url, follow=True)
        self.assertEqual(resp.status_code, 200)

        inv.refresh_from_db()
        self.assertEqual(inv.status, "PAID")
        self.assertIsNotNone(inv.date_paid)
        self.assertEqual(inv.payer_link, "https://www.sandbox.paypal.com/invoice/p/#PAID123")

    def test_dashboard_totals_correct(self):
        """Dashboard displays correct aggregated invoiced, paid, and awaiting totals."""
        Invoice.objects.create(
            organization=self.org_a,
            deal=self.deal_won,
            paypal_invoice_id="INV2-PAID-1",
            invoice_number="INV-0001",
            amount=decimal.Decimal("1000.00"),
            currency="USD",
            status="PAID",
            recipient_email="buyer1@test.com",
            created_by=self.owner_a,
        )
        deal_won_2 = Deal.objects.create(
            organization=self.org_a,
            title="Second Contract",
            value=decimal.Decimal("500.00"),
            stage=self.stage_won,
            contact=self.contact_a,
            owner=self.owner_a,
        )
        Invoice.objects.create(
            organization=self.org_a,
            deal=deal_won_2,
            paypal_invoice_id="INV2-PEND-2",
            invoice_number="INV-0002",
            amount=decimal.Decimal("500.00"),
            currency="USD",
            status="SENT",
            recipient_email="buyer2@test.com",
            created_by=self.owner_a,
        )

        resp = self.client_a.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["invoices_total_amount"], decimal.Decimal("1500.00"))
        self.assertEqual(resp.context["invoices_paid_amount"], decimal.Decimal("1000.00"))
        self.assertEqual(resp.context["invoices_awaiting_amount"], decimal.Decimal("500.00"))
        self.assertEqual(resp.context["invoices_total_count"], 2)

    @patch("payments.paypal.is_paypal_configured", return_value=False)
    def test_missing_paypal_keys_handled_gracefully(self, mock_cfg):
        """Without configured PayPal keys, invoice button displays fallback and post fails calmly."""
        deal_url = reverse("deal_update", kwargs={"pk": self.deal_won.pk})
        resp = self.client_a.get(deal_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "PayPal sandbox keys not configured, see README")

        # Post attempt fails gracefully
        send_url = reverse("invoice_send", kwargs={"deal_id": self.deal_won.pk})
        post_resp = self.client_a.post(send_url, {
            "recipient_email": "buyer@test.com",
            "amount": "1500.00",
        }, follow=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertContains(post_resp, "PayPal sandbox keys not configured, see README")
        self.assertFalse(Invoice.objects.filter(deal=self.deal_won).exists())

    @patch("payments.paypal.get_access_token", return_value="mock_token")
    @patch("payments.paypal.create_draft_invoice", side_effect=PayPalAPIError("Sandbox service unavailable", status_code=503))
    @patch("payments.paypal.is_paypal_configured", return_value=True)
    def test_paypal_error_leaves_no_half_saved_invoice(self, mock_cfg, mock_draft, mock_token):
        """PayPal API errors show a calm message and leave no half-saved invoice in DB."""
        send_url = reverse("invoice_send", kwargs={"deal_id": self.deal_won.pk})
        resp = self.client_a.post(send_url, {
            "recipient_email": "buyer@test.com",
            "amount": "1500.00",
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sandbox service unavailable")
        self.assertFalse(Invoice.objects.filter(deal=self.deal_won).exists())

    @patch("assistant.services.is_llm_configured", return_value=False)
    def test_missing_ai_key_handled(self, mock_llm_cfg):
        """Without an AI key, Kine replies 'Kine needs an AI key, see README'."""
        chat_url = reverse("assistant_chat")
        resp = self.client_a.post(
            chat_url,
            data=b'{"message": "What are my sales numbers?"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("Kine needs an AI key, see README", data.get("reply"))

    def test_billing_page_shows_trial_status(self):
        """Billing page renders organization trial status without Razorpay buttons."""
        resp = self.client_a.get(reverse("billing"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "14-Day Free Trial")
        self.assertNotContains(resp, "checkout.razorpay.com")
        self.assertNotContains(resp, "startSubscriptionBtn")
