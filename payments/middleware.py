from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


class SubscriptionEnforcementMiddleware:
    """
    Restricts access when a business trial ends or its subscription is cancelled, halted, or expired.
    The business can still log in, but is redirected to the Billing page and cannot use the CRM,
    except for 'Download all my data' in Settings, which stays available to the Owner.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, "organization") and request.user.organization:
            org = request.user.organization

            # If CRM access is blocked (trial ended, cancelled, expired, past_due)
            if not org.can_access_crm:
                path = request.path

                from django.conf import settings
                admin_path = f"/{getattr(settings, 'ADMIN_URL', 'portal-admin/').strip('/')}/"

                # Allowed paths when subscription is inactive
                allowed_prefixes = (
                    "/billing/",
                    "/accounts/logout/",
                    "/health/",
                    admin_path,
                    "/admin/",
                    "/static/",
                    "/media/",
                )

                # Settings & data download remain accessible to the Owner
                is_owner_data_access = (
                    request.user.role == "OWNER" and (
                        path == reverse("settings") or
                        path == reverse("download_all_data")
                    )
                )

                is_allowed = is_owner_data_access or any(path.startswith(prefix) for prefix in allowed_prefixes)

                if not is_allowed:
                    # Provide an informative message once
                    if not request.session.get("subscription_warning_shown"):
                        if request.user.role == "OWNER":
                            messages.warning(
                                request,
                                "Your trial or subscription is inactive. Please subscribe to the Business plan to resume full access."
                            )
                        else:
                            messages.warning(
                                request,
                                "Your organization's subscription is inactive. Please contact your workspace Owner to activate."
                            )
                        request.session["subscription_warning_shown"] = True
                    return redirect("billing")
                else:
                    # Clear warning flag once on billing or allowed page
                    request.session.pop("subscription_warning_shown", None)

        return self.get_response(request)

