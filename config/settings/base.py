import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-in-prod-2026")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # SaaS Apps
    "accounts.apps.AccountsConfig",
    "organizations.apps.OrganizationsConfig",
    "crm_core.apps.CrmCoreConfig",
    "payments.apps.PaymentsConfig",
    "assistant.apps.AssistantConfig",
]

MIDDLEWARE = [
    "config.middleware.TrustedProxyMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "organizations.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "payments.middleware.SubscriptionEnforcementMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "crm_core.context_processors.task_reminders",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database Configuration (Defaults to MySQL 8 via environment variables)
DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.mysql")
DB_NAME = os.getenv("DB_NAME", "crm_saas_db")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")

if DB_ENGINE == "django.db.backends.sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": DB_NAME,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email Delivery Configuration
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").replace(" ", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "KinetiQ <noreply@kinetiqcrm.com>")

# PayPal Sandbox Invoicing API v2 (Test Mode Only)
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")

# Reverse Proxy & Client IP
TRUSTED_PROXIES = [ip.strip() for ip in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1").split(",") if ip.strip()]

# Admin URL & Site URL
ADMIN_URL = os.getenv("ADMIN_URL", "portal-admin/").strip("/") + "/"
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")

# Session Idle Timeout (1 hour idle timeout)
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True

# Logging Configuration with File Rotation
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} [{name}:{lineno}] {message}",
            "style": "{",
        },
        "security": {
            "format": "[{asctime}] SECURITY {levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "kinetiq.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "security.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 5,
            "formatter": "security",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console", "security_file", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "kinetiq.security": {
            "handlers": ["console", "security_file", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Kine AI Assistant (Stage 1 Read-Only Chat)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
LLM_API_URL = os.getenv("LLM_API_URL", "")
KINE_USER_DAILY_LIMIT = int(os.getenv("KINE_USER_DAILY_LIMIT", "50"))
KINE_ORG_DAILY_LIMIT = int(os.getenv("KINE_ORG_DAILY_LIMIT", "200"))
KINE_MAX_MESSAGE_LENGTH = int(os.getenv("KINE_MAX_MESSAGE_LENGTH", "500"))
KINE_REQUEST_TIMEOUT = int(os.getenv("KINE_REQUEST_TIMEOUT", "10"))
KINE_HISTORY_MESSAGES_LIMIT = int(os.getenv("KINE_HISTORY_MESSAGES_LIMIT", "12"))
KINE_MAX_REPLY_TOKENS = int(os.getenv("KINE_MAX_REPLY_TOKENS", "400"))


