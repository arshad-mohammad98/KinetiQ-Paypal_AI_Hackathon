import logging
from django.conf import settings

security_logger = logging.getLogger("kinetiq.security")


class TrustedProxyMiddleware:
    """
    Middleware that securely determines the genuine client IP when running
    behind a trusted reverse proxy (such as Nginx).

    Security Protection:
    - Only trusts X-Forwarded-For / X-Real-IP if REMOTE_ADDR originates from
      a configured trusted proxy (e.g. 127.0.0.1, ::1).
    - If a direct connection arrives with spoofed X-Forwarded-For headers,
      those headers are strictly ignored, protecting login rate limiting
      and audit logs from IP evasion/spoofing attacks.
    - When behind trusted proxies, extracts the rightmost untrusted IP address
      from the X-Forwarded-For chain.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        remote_addr = request.META.get("REMOTE_ADDR", "").strip()
        trusted_proxies = getattr(settings, "TRUSTED_PROXIES", ["127.0.0.1", "::1"])

        if remote_addr in trusted_proxies:
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                # Comma-separated list of IPs: client, proxy1, proxy2
                ips = [ip.strip() for ip in x_forwarded_for.split(",") if ip.strip()]
                # Find the rightmost IP that is not a trusted proxy
                client_ip = remote_addr
                for candidate in reversed(ips):
                    if candidate not in trusted_proxies:
                        client_ip = candidate
                        break
                request.META["REMOTE_ADDR"] = client_ip
            elif "HTTP_X_REAL_IP" in request.META:
                real_ip = request.META["HTTP_X_REAL_IP"].strip()
                if real_ip:
                    request.META["REMOTE_ADDR"] = real_ip

        return self.get_response(request)

