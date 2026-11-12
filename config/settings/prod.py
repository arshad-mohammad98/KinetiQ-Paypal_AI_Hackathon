import os
from django.core.exceptions import ImproperlyConfigured
from .base import *

DEBUG = False

# ==============================================================================
# PRODUCTION ENVIRONMENT AUDIT & STRICT STARTUP CHECKS
# ==============================================================================

# 1. SECRET_KEY Audit
DEV_SECRET_KEYS = {
    "django-insecure-dev-key-change-in-prod-2026",
    "django-insecure-crm-saas-dev-secret-key-398457293847529348572039",
}

raw_secret = os.getenv("DJANGO_SECRET_KEY", "").strip()
if not raw_secret:
    raise ImproperlyConfigured("In production, DJANGO_SECRET_KEY must be set in .env.")
if raw_secret in DEV_SECRET_KEYS or raw_secret.startswith("django-insecure-") or len(raw_secret) < 50:
    raise ImproperlyConfigured(
        "In production, DJANGO_SECRET_KEY must not use a development key or insecure default (min 50 chars required)."
    )
SECRET_KEY = raw_secret

# 2. ALLOWED_HOSTS Audit
raw_hosts = os.getenv("ALLOWED_HOSTS", "").strip()
if not raw_hosts:
    raise ImproperlyConfigured("In production, ALLOWED_HOSTS must be explicitly defined in .env.")

ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("In production, ALLOWED_HOSTS cannot be empty or contain wildcard '*'.")

# 3. SITE_URL Audit
raw_site_url = os.getenv("SITE_URL", "").strip()
if not raw_site_url:
    raise ImproperlyConfigured("In production, SITE_URL must be explicitly defined in .env.")
if not raw_site_url.startswith("https://"):
    raise ImproperlyConfigured("In production, SITE_URL must use HTTPS (e.g. https://app.kinetiqcrm.com).")
SITE_URL = raw_site_url

# 4. Database Settings Audit
for db_var in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"):
    val = os.getenv(db_var, "").strip()
    if not val:
        raise ImproperlyConfigured(f"In production, database variable '{db_var}' must be set in .env.")

if os.getenv("DB_USER", "").strip() == "root":
    raise ImproperlyConfigured("In production, DB_USER must be a restricted database user, never 'root'.")

if os.getenv("DB_ENGINE", "").strip() == "django.db.backends.sqlite3":
    raise ImproperlyConfigured("In production, SQLite is forbidden. Use MySQL 8 via django.db.backends.mysql.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ["DB_PORT"],
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# 5. ADMIN_URL Audit
raw_admin_url = os.getenv("ADMIN_URL", "").strip().strip("/")
if not raw_admin_url or raw_admin_url.lower() == "admin":
    raise ImproperlyConfigured(
        "In production, ADMIN_URL must be set in .env to a secret custom path (not default 'admin')."
    )
ADMIN_URL = f"{raw_admin_url}/"

# ==============================================================================
# SECURITY HEADERS, HTTPS REDIRECT & COOKIES
# ==============================================================================

# HTTPS Enforcement & Redirect
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cookies
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# HTTP Strict Transport Security (HSTS) - Starts with sensible short duration (1 hour)
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Content Security & Framing
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# Session Idle Timeout
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True

# ==============================================================================
# PRODUCTION EMAIL (Strictly SMTP)
# ==============================================================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "KinetiQ <noreply@kinetiqcrm.com>")
