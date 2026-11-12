from .base import *

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Development Email: uses EMAIL_BACKEND from .env if defined, else defaults to DevEmailBackend
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "accounts.email_backend.DevEmailBackend")
EMAIL_FILE_PATH = BASE_DIR / "dev_emails"
