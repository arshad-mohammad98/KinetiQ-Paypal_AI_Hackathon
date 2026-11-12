from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Sends a test email to verify that Django email sending and SMTP settings are functioning properly."

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            nargs="?",
            type=str,
            help="Destination email address to send the test message to.",
        )

    def handle(self, *args, **options):
        recipient = options.get("recipient")
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "KinetiQ <noreply@kinetiqcrm.com>")

        if not recipient:
            # Fallback to default from email address
            recipient = from_email
            if "<" in recipient and ">" in recipient:
                recipient = recipient.split("<")[1].split(">")[0].strip()

        backend = getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
        host = getattr(settings, "EMAIL_HOST", "N/A")
        port = getattr(settings, "EMAIL_PORT", "N/A")

        self.stdout.write(self.style.NOTICE("=================================================="))
        self.stdout.write(self.style.NOTICE(" KinetiQ Email Verification Diagnostic"))
        self.stdout.write(self.style.NOTICE("=================================================="))
        self.stdout.write(f"Active Backend: {backend}")
        self.stdout.write(f"SMTP Host:      {host}:{port}")
        self.stdout.write(f"From Address:   {from_email}")
        self.stdout.write(f"Recipient:      {recipient}")
        self.stdout.write("--------------------------------------------------")
        self.stdout.write("Dispatching test email...")

        subject = "[KinetiQ] Test Email Delivery"
        body = (
            f"Hello,\n\n"
            f"This is a test message from KinetiQ to verify that your email subsystem\n"
            f"is operating properly.\n\n"
            f"Timestamp:   {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Backend:     {backend}\n"
            f"Sender:      {from_email}\n"
            f"Recipient:   {recipient}\n\n"
            f"If you received this email, your SMTP configuration is verified and functioning!\n\n"
            f"— The KinetiQ Team\n"
        )

        try:
            sent_count = send_mail(
                subject=subject,
                message=body,
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
            )
            if sent_count > 0:
                self.stdout.write(self.style.SUCCESS(f"\n[SUCCESS] Test email successfully delivered to {recipient}!"))
            else:
                self.stdout.write(self.style.WARNING(f"\n[WARNING] send_mail returned 0 messages sent."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"\n[ERROR] Failed to send test email: {exc}\n"))
            self.stdout.write(self.style.NOTICE(
                "Troubleshooting steps:\n"
                "1. Verify EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD in your .env.\n"
                "2. For SendGrid: EMAIL_HOST_USER must be 'apikey' and PASSWORD is the SendGrid API Key (starts with SG.).\n"
                "3. For Gmail / Google Workspace: Ensure an 'App Password' is used with 2FA enabled.\n"
                "4. Check firewall / ISP: Verify outbound traffic on port 587 (or 465) is permitted.\n"
            ))
            raise

