import os
import sys
from datetime import datetime
from django.conf import settings
from django.core.mail.backends.filebased import EmailBackend as FileEmailBackend

class DevEmailBackend(FileEmailBackend):
    """
    Development email backend:
    1. Writes each outgoing email to the 'dev_emails' folder as a .txt file.
    2. Prints the email content directly to the development terminal console.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("file_path", str(settings.BASE_DIR / "dev_emails"))
        super().__init__(*args, **kwargs)
        os.makedirs(self.file_path, exist_ok=True)
        self._seq = 0

    def _get_filename(self):
        """
        Creates clean, timestamp-prefixed filenames: YYYYMMDD_HHMMSS_<seq>.txt
        Making the newest files easy to locate and inspect.
        """
        self._seq += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.file_path, f"{timestamp}_{self._seq}.txt")

    def send_messages(self, email_messages):
        count = super().send_messages(email_messages)
        for message in email_messages:
            recipients = ", ".join(message.to)
            sys.stdout.write(
                f"\n==================== [DEV EMAIL OUTBOX] ====================\n"
                f"To: {recipients}\n"
                f"Subject: {message.subject}\n"
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Saved to: dev_emails/\n"
                f"------------------------------------------------------------\n"
                f"{message.body}\n"
                f"============================================================\n\n"
            )
            sys.stdout.flush()
        return count
