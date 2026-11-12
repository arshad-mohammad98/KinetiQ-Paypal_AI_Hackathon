import os
import subprocess
import sys
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class ProductionSecurityHardeningTestCase(TestCase):
    """
    Comprehensive test suite verifying production settings audit, security headers,
    safe admin relocation, error pages, trusted proxy IP resolution, and health check.
    """

    def setUp(self):
        self.valid_prod_env = {
            "DJANGO_SECRET_KEY": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6A7B8C9D0E1F2",
            "ALLOWED_HOSTS": "app.kinetiqcrm.com",
            "SITE_URL": "https://app.kinetiqcrm.com",
            "DB_NAME": "crm_saas_db",
            "DB_USER": "kinetiq_app",
            "DB_PASSWORD": "SecureProductionPassword123!",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "3306",
            "ADMIN_URL": "secure-admin-portal",
        }

    # ==========================================================================
    # 1. Production Settings Audit & Startup Refusal Checks
    # ==========================================================================

    def test_prod_settings_refuses_missing_secret_key(self):
        """App refuses to start in prod if DJANGO_SECRET_KEY is missing."""
        env = dict(self.valid_prod_env)
        del env["DJANGO_SECRET_KEY"]
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                import importlib
                import config.settings.prod as prod
                importlib.reload(prod)

    def test_prod_settings_refuses_dev_secret_key(self):
        """App refuses to start in prod if DJANGO_SECRET_KEY is a known dev key."""
        dev_keys = [
            "django-insecure-dev-key-change-in-prod-2026",
            "django-insecure-crm-saas-dev-secret-key-398457293847529348572039",
            "django-insecure-short",
            "short-secret-key-under-50-chars",
        ]
        for key in dev_keys:
            env = dict(self.valid_prod_env, DJANGO_SECRET_KEY=key)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ImproperlyConfigured, msg=f"Should refuse dev key: {key}"):
                    import importlib
                    import config.settings.prod as prod
                    importlib.reload(prod)

    def test_prod_settings_refuses_missing_or_wildcard_allowed_hosts(self):
        """App refuses to start in prod if ALLOWED_HOSTS is missing or contains '*'."""
        for invalid_hosts in ["", "  ", "*", "app.com,*"]:
            env = dict(self.valid_prod_env, ALLOWED_HOSTS=invalid_hosts)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ImproperlyConfigured):
                    import importlib
                    import config.settings.prod as prod
                    importlib.reload(prod)

    def test_prod_settings_refuses_missing_or_non_https_site_url(self):
        """App refuses to start in prod if SITE_URL is missing or does not use HTTPS."""
        for invalid_url in ["", "http://app.kinetiqcrm.com", "ftp://app.com"]:
            env = dict(self.valid_prod_env, SITE_URL=invalid_url)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ImproperlyConfigured):
                    import importlib
                    import config.settings.prod as prod
                    importlib.reload(prod)

    def test_prod_settings_refuses_root_db_user_or_missing_db_vars(self):
        """App refuses to start in prod if DB_USER is root or required DB vars are omitted."""
        # 1. Refuses root DB user
        env_root = dict(self.valid_prod_env, DB_USER="root")
        with patch.dict(os.environ, env_root, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                import importlib
                import config.settings.prod as prod
                importlib.reload(prod)

        # 2. Refuses missing password
        env_no_pass = dict(self.valid_prod_env, DB_PASSWORD="")
        with patch.dict(os.environ, env_no_pass, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                import importlib
                import config.settings.prod as prod
                importlib.reload(prod)

    def test_prod_settings_refuses_default_admin_url(self):
        """App refuses to start in prod if ADMIN_URL is default 'admin'."""
        for bad_admin in ["", "admin", "admin/", "/admin/"]:
            env = dict(self.valid_prod_env, ADMIN_URL=bad_admin)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ImproperlyConfigured):
                    import importlib
                    import config.settings.prod as prod
                    importlib.reload(prod)

    def test_prod_settings_security_flags(self):
        """When valid prod env is provided, all production security flags are True."""
        with patch.dict(os.environ, self.valid_prod_env, clear=True):
            import importlib
            import config.settings.prod as prod
            importlib.reload(prod)

            self.assertFalse(prod.DEBUG)
            self.assertTrue(prod.SECURE_SSL_REDIRECT)
            self.assertTrue(prod.SESSION_COOKIE_SECURE)
            self.assertTrue(prod.CSRF_COOKIE_SECURE)
            self.assertTrue(prod.SESSION_COOKIE_HTTPONLY)
            self.assertTrue(prod.CSRF_COOKIE_HTTPONLY)
            self.assertTrue(prod.SECURE_CONTENT_TYPE_NOSNIFF)
            self.assertEqual(prod.X_FRAME_OPTIONS, "DENY")
            self.assertEqual(prod.SECURE_REFERRER_POLICY, "same-origin")
            self.assertEqual(prod.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))
            self.assertEqual(prod.SECURE_HSTS_SECONDS, 3600)
            self.assertTrue(prod.SECURE_HSTS_INCLUDE_SUBDOMAINS)
            self.assertEqual(prod.SESSION_COOKIE_AGE, 3600)
            self.assertTrue(prod.SESSION_SAVE_EVERY_REQUEST)

    # ==========================================================================
    # 2. Django Deployment Check (check --deploy)
    # ==========================================================================

    def test_django_deploy_check_reports_zero_warnings(self):
        """Django's deployment check run with prod settings reports no warnings."""
        env = os.environ.copy()
        env.update(self.valid_prod_env)
        cmd = [
            sys.executable,
            "manage.py",
            "check",
            "--deploy",
            "--settings=config.settings.prod",
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(
            res.returncode,
            0,
            f"check --deploy failed with return code {res.returncode}:\nStdout: {res.stdout}\nStderr: {res.stderr}",
        )
        self.assertIn("System check identified no issues", res.stdout + res.stderr)

    # ==========================================================================
    # 3. Safe Admin Relocation & Superuser-Only Access
    # ==========================================================================

    def test_old_admin_url_returns_404(self):
        """The old /admin/ URL strictly returns 404."""
        resp = self.client.get("/admin/")
        self.assertEqual(resp.status_code, 404)

        resp_sub = self.client.get("/admin/login/")
        self.assertEqual(resp_sub.status_code, 404)

    def test_custom_admin_url_is_accessible(self):
        """The custom admin URL set in settings is reachable."""
        admin_url = f"/{settings.ADMIN_URL.strip('/')}/"
        resp = self.client.get(admin_url)
        # Should either render admin login or redirect to login
        self.assertIn(resp.status_code, (200, 302))

    def test_admin_is_superuser_only(self):
        """Staff members without superuser status are denied access to the admin."""
        # Create non-superuser staff member
        staff_user = User.objects.create_user(
            email="staff_test@example.com",
            password="StaffPassword123!",
            is_staff=True,
            is_superuser=False,
            is_email_verified=True,
        )
        self.client.login(email="staff_test@example.com", password="StaffPassword123!")
        admin_url = f"/{settings.ADMIN_URL.strip('/')}/"
        resp = self.client.get(admin_url)
        # Standard Django admin shows login form with not-authorized message or redirects
        self.assertNotEqual(resp.status_code, 500)
        # In Django AdminSite, has_permission returns False for non-superuser
        from django.contrib import admin
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get(admin_url)
        req.user = staff_user
        self.assertFalse(admin.site.has_permission(req))

    def test_admin_allows_actual_superuser(self):
        """Superuser has permission to access admin."""
        super_user = User.objects.create_superuser(
            email="super_test@example.com",
            password="SuperPassword123!",
        )
        from django.contrib import admin
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get(f"/{settings.ADMIN_URL.strip('/')}/")
        req.user = super_user
        self.assertTrue(admin.site.has_permission(req))

    # ==========================================================================
    # 4. Error Pages Show No Technical Details
    # ==========================================================================

    def test_custom_404_page(self):
        """404 page renders friendly KinetiQ design with zero technical details."""
        resp = self.client.get("/non-existent-url-that-triggers-404/")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "Page Not Found", status_code=404)
        self.assertContains(resp, "KinetiQ", status_code=404)
        # Ensure no tracebacks, internal paths, or python error details
        self.assertNotContains(resp, "Traceback", status_code=404)
        self.assertNotContains(resp, "django.core", status_code=404)
        self.assertNotContains(resp, "C:\\", status_code=404)
        self.assertNotContains(resp, "/Users/", status_code=404)

    def test_custom_403_page(self):
        """403 page renders friendly KinetiQ design with zero technical details."""
        from config.views import custom_403
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get("/restricted-path/")
        resp = custom_403(req)
        self.assertEqual(resp.status_code, 403)
        content = resp.content.decode("utf-8")
        self.assertIn("Access Denied", content)
        self.assertIn("KinetiQ", content)
        self.assertNotIn("Traceback", content)
        self.assertNotIn("PermissionDenied:", content)

    def test_custom_500_page(self):
        """500 page renders friendly KinetiQ design with zero technical details."""
        from config.views import custom_500
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get("/broken-path/")
        resp = custom_500(req)
        self.assertEqual(resp.status_code, 500)
        content = resp.content.decode("utf-8")
        self.assertIn("Something Went Wrong", content)
        self.assertIn("KinetiQ", content)
        self.assertNotIn("Traceback", content)
        self.assertNotIn("Exception", content)
        self.assertNotIn("crm_saas_db", content)

    # ==========================================================================
    # 5. Trusted Proxy Middleware & Client IP Spoof Protection
    # ==========================================================================

    def test_trusted_proxy_resolves_real_client_ip(self):
        """Behind a trusted proxy (127.0.0.1), client IP comes from X-Forwarded-For."""
        resp = self.client.get(
            reverse("home"),
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_FORWARDED_FOR="198.51.100.42, 127.0.0.1",
        )
        self.assertEqual(resp.status_code, 200)
        # Test directly via middleware
        from config.middleware import TrustedProxyMiddleware
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get("/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="198.51.100.42, 127.0.0.1")
        middleware = TrustedProxyMiddleware(lambda r: r)
        middleware(req)
        self.assertEqual(req.META["REMOTE_ADDR"], "198.51.100.42")

    def test_untrusted_direct_connection_cannot_spoof_ip(self):
        """Direct connection from untrusted IP cannot fake its IP using X-Forwarded-For."""
        from config.middleware import TrustedProxyMiddleware
        from django.test import RequestFactory
        factory = RequestFactory()
        # Direct untrusted connection sending spoofed X-Forwarded-For
        req = factory.get("/", REMOTE_ADDR="198.51.100.99", HTTP_X_FORWARDED_FOR="8.8.8.8")
        middleware = TrustedProxyMiddleware(lambda r: r)
        middleware(req)
        # REMOTE_ADDR remains unchanged!
        self.assertEqual(req.META["REMOTE_ADDR"], "198.51.100.99")

    # ==========================================================================
    # 6. Health Check Endpoint (/health/)
    # ==========================================================================

    def test_health_check_returns_ok_when_database_reachable(self):
        """Health check returns 200 'ok' when database is reachable."""
        resp = self.client.get(reverse("health_check"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode("utf-8").strip(), "ok")
        self.assertEqual(resp["Content-Type"], "text/plain; charset=utf-8")

    @patch("config.views.connection.cursor")
    def test_health_check_fails_safely_when_database_unreachable(self, mock_cursor):
        """Health check returns 503 'unavailable' with zero leaked details when database fails."""
        mock_cursor.side_effect = DatabaseError("Connection refused: 127.0.0.1:3306")
        resp = self.client.get(reverse("health_check"))
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.content.decode("utf-8").strip(), "unavailable")
        # Absolutely no database credentials, host, or error strings exposed
        self.assertNotContains(resp, "Connection refused", status_code=503)
        self.assertNotContains(resp, "127.0.0.1", status_code=503)
        self.assertNotContains(resp, "DatabaseError", status_code=503)

    # ==========================================================================
    # 7. Logging & Security Events Audit
    # ==========================================================================

    def test_failed_login_logs_security_event_without_password(self):
        """Failed login attempts are logged to the security log without recording the password."""
        secret_guess = "SuperSecretPasswordDoNotLog123!"
        target_email = "target_user@example.com"
        with self.assertLogs("kinetiq.security", level="WARNING") as cm:
            resp = self.client.post(
                reverse("login"),
                {"email": target_email, "password": secret_guess},
                REMOTE_ADDR="198.51.100.77",
            )
        self.assertEqual(resp.status_code, 200)
        log_output = "\n".join(cm.output)
        self.assertIn("Failed login attempt for user 'target_user@example.com' from IP 198.51.100.77", log_output)
        # Ensure password is NEVER logged
        self.assertNotIn(secret_guess, log_output)

    def test_logging_rotation_configuration(self):
        """Logging configuration uses RotatingFileHandler with 5MB maxBytes and 5 backup count."""
        from logging.handlers import RotatingFileHandler
        import logging
        root_logger = logging.getLogger("kinetiq.security")
        handlers = root_logger.handlers or logging.getLogger().handlers
        rotating_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
        self.assertTrue(len(rotating_handlers) > 0, "At least one RotatingFileHandler should be configured.")
        for handler in rotating_handlers:
            self.assertEqual(handler.maxBytes, 5 * 1024 * 1024)
            self.assertEqual(handler.backupCount, 5)
