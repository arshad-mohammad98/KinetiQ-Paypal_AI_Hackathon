import os
import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from organizations.models import Organization
from .models import TeamInvitation
from .utils import send_verification_email

User = get_user_model()

class UserAccountSystemTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_signup_creates_separate_business_each_time(self):
        res1 = self.client.post(reverse("signup"), {
            "business_name": "Apex Consulting",
            "first_name": "Alice",
            "last_name": "Adams",
            "email": "alice@apex.com",
            "password": "StrongPassword123!",
        })
        self.assertEqual(res1.status_code, 302)

        res2 = self.client.post(reverse("signup"), {
            "business_name": "Beacon Retail",
            "first_name": "Bob",
            "last_name": "Brown",
            "email": "bob@beacon.com",
            "password": "StrongPassword123!",
        })
        self.assertEqual(res2.status_code, 302)

        self.assertEqual(Organization.objects.count(), 2)
        org1 = Organization.objects.get(name="Apex Consulting")
        org2 = Organization.objects.get(name="Beacon Retail")
        self.assertNotEqual(org1.id, org2.id)

        user1 = User.objects.get(email="alice@apex.com")
        user2 = User.objects.get(email="bob@beacon.com")
        self.assertEqual(user1.organization, org1)
        self.assertEqual(user2.organization, org2)
        self.assertEqual(user1.role, "OWNER")
        self.assertEqual(user2.role, "OWNER")

    def test_unverified_user_cannot_enter_app(self):
        org = Organization.objects.create(name="Delta Corp")
        user = User.objects.create_user(
            email="charlie@delta.com",
            password="StrongPassword123!",
            first_name="Charlie",
            last_name="Davis",
            organization=org,
            role="OWNER",
            is_email_verified=False,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("verification_sent"))

    def test_check_email_page_never_contains_verification_url_or_token(self):
        # Register user
        self.client.post(reverse("signup"), {
            "business_name": "Security Corp",
            "first_name": "Sam",
            "last_name": "Sec",
            "email": "sam@security.com",
            "password": "StrongPassword123!",
        })
        response = self.client.get(reverse("verification_sent"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # Ensure NO verification URLs, tokens, or dev shortcuts are on the web page
        self.assertNotIn("verify-email", content)
        self.assertNotIn("Local Dev", content)
        self.assertNotIn("Activation Link", content)
        self.assertNotIn("Dev Quick Link", content)

    def test_emailed_link_verifies_account(self):
        # Clear outbox
        mail.outbox = []

        # Signup via form to trigger email
        self.client.post(reverse("signup"), {
            "business_name": "Verify Corp",
            "first_name": "Victor",
            "last_name": "Vane",
            "email": "victor@verify.com",
            "password": "StrongPassword123!",
        })

        # Ensure email was generated in outbox
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body

        # Extract verify URL from email text
        match = re.search(r"(http://[^\s]+/accounts/verify-email/[^\s]+)", email_body)
        self.assertIsNotNone(match, "Verification URL not found in email body.")
        verify_url = match.group(1)

        # Visit the emailed verification link
        verify_response = self.client.get(verify_url)
        self.assertRedirects(verify_response, reverse("dashboard"))

        # Verify database account is now verified
        user = User.objects.get(email="victor@verify.com")
        self.assertTrue(user.is_email_verified)

    def test_production_settings_do_not_use_dev_email_setup(self):
        import importlib
        mock_prod_env = {
            "DJANGO_SECRET_KEY": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6A7B8C9D0E1F2",
            "ALLOWED_HOSTS": "app.kinetiqcrm.com",
            "SITE_URL": "https://app.kinetiqcrm.com",
            "DB_NAME": "crm_saas_db",
            "DB_USER": "kinetiq_app",
            "DB_PASSWORD": "SecureProductionPassword123!",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "3306",
            "ADMIN_URL": "portal-admin",
        }
        with patch.dict(os.environ, mock_prod_env):
            import config.settings.prod as prod_settings
            importlib.reload(prod_settings)
            self.assertFalse(prod_settings.DEBUG)
            self.assertEqual(
                prod_settings.EMAIL_BACKEND,
                "django.core.mail.backends.smtp.EmailBackend"
            )
            self.assertNotEqual(
                prod_settings.EMAIL_BACKEND,
                "accounts.email_backend.DevEmailBackend"
            )

    def test_resend_verification_rate_limiting(self):
        cache.clear()
        org = Organization.objects.create(name="Rate Limit Corp")
        user = User.objects.create_user(
            email="rate@corp.com",
            password="StrongPassword123!",
            first_name="Ray",
            last_name="Limit",
            organization=org,
            role="OWNER",
            is_email_verified=False,
        )
        self.client.force_login(user)

        # 3 allowed attempts per minute
        for _ in range(3):
            res = self.client.get(reverse("resend_verification"))
            self.assertEqual(res.status_code, 302)

        # 4th attempt must be throttled
        throttled_res = self.client.get(reverse("resend_verification"), follow=True)
        self.assertContains(throttled_res, "Too many resend attempts")

    def test_cross_business_invite_isolation(self):
        org_a = Organization.objects.create(name="Business A")
        user_a = User.objects.create_user(
            email="owner_a@biz-a.com",
            password="StrongPassword123!",
            first_name="Owner",
            last_name="A",
            organization=org_a,
            role="OWNER",
            is_email_verified=True,
        )
        invite_a = TeamInvitation.objects.create(
            organization=org_a,
            email="invitee@biz-a.com",
            role="MEMBER",
            invited_by=user_a,
        )

        org_b = Organization.objects.create(name="Business B")
        user_b = User.objects.create_user(
            email="owner_b@biz-b.com",
            password="StrongPassword123!",
            first_name="Owner",
            last_name="B",
            organization=org_b,
            role="OWNER",
            is_email_verified=True,
        )

        self.client.force_login(user_b)
        response = self.client.get(reverse("team_list"))
        self.assertNotContains(response, "invitee@biz-a.com")

    def test_expired_invite_is_rejected(self):
        org = Organization.objects.create(name="Echo Corp")
        invite = TeamInvitation.objects.create(
            organization=org,
            email="latecomer@echo.com",
            role="MEMBER",
        )
        invite.expires_at = timezone.now() - timedelta(days=1)
        invite.save()

        response = self.client.get(reverse("accept_invite", kwargs={"token": invite.token}))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "expired", status_code=400)

    def test_login_rate_limiting_works(self):
        cache.clear()
        for _ in range(5):
            res = self.client.post(reverse("login"), {
                "email": "wrong@example.com",
                "password": "WrongPassword1!",
            })
            self.assertEqual(res.status_code, 200)

        throttled_res = self.client.post(reverse("login"), {
            "email": "wrong@example.com",
            "password": "WrongPassword1!",
        })
        self.assertEqual(throttled_res.status_code, 429)
        self.assertContains(throttled_res, "Too many login attempts", status_code=429)

    def test_send_test_email_command(self):
        """send_test_email management command dispatches test email successfully."""
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("send_test_email", "verify@example.com", stdout=out)
        output_str = out.getvalue()
        self.assertIn("Test email successfully delivered to verify@example.com", output_str)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["verify@example.com"])
        self.assertIn("[KinetiQ] Test Email Delivery", mail.outbox[0].subject)

    def test_seed_demo_command(self):
        """seed_demo management command provisions demo tenants, users, and won deals."""
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("seed_demo", stdout=out)
        output_str = out.getvalue()
        self.assertIn("Demo database successfully seeded", output_str)
        self.assertIn("admin@acme.com", output_str)
        self.assertTrue(Organization.objects.filter(slug="acme-innovations").exists())
        self.assertTrue(User.objects.filter(email="admin@acme.com").exists())

    def test_no_old_product_name_remains(self):
        for url_name in ["home", "login", "signup"]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "KinetiQ")
            self.assertNotContains(response, "Pulse")

        template_dir = settings.BASE_DIR / "templates"
        for template_file in template_dir.rglob("*.html"):
            content = template_file.read_text(encoding="utf-8")
            self.assertNotIn("Pulse", content, f"Found old name 'Pulse' in {template_file.name}")
            self.assertNotIn("CRM SaaS", content, f"Found old name 'CRM SaaS' in {template_file.name}")
