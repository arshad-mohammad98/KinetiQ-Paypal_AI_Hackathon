"""
PayPal Invoicing API v2 Module for KinetiQ (Hackathon Edition).
Strictly PayPal SANDBOX only with hard-coded sandbox base URL.
Provides OAuth2 token reuse, invoice number generation, draft creation, sending, and fetching.
"""

import datetime
import decimal
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("kinetiq.paypal")

# Strictly PayPal SANDBOX base URL
SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
DEFAULT_TIMEOUT_SECONDS = 15

# In-memory token cache for OAuth 2.0 access token reuse
_TOKEN_CACHE = {
    "token": None,
    "expires_at": 0,
}


class PayPalError(Exception):
    """Base exception for PayPal operations."""
    pass


class PayPalConfigError(PayPalError):
    """Raised when PayPal client credentials are missing or invalid placeholders."""
    pass


class PayPalAPIError(PayPalError):
    """Raised when a PayPal API call fails or times out."""
    def __init__(self, message, status_code=None, error_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_data = error_data or {}


def get_client_id():
    return (getattr(settings, "PAYPAL_CLIENT_ID", "") or "").strip()


def get_client_secret():
    return (getattr(settings, "PAYPAL_CLIENT_SECRET", "") or "").strip()


def is_paypal_configured():
    """
    Returns True if PayPal sandbox keys are configured and not dummy placeholders.
    """
    cid = get_client_id()
    sec = get_client_secret()
    if not cid or not sec:
        return False
    lower_cid = cid.lower()
    lower_sec = sec.lower()
    placeholders = ("placeholder", "your_paypal", "your_client", "dummy")
    if any(p in lower_cid for p in placeholders) or any(p in lower_sec for p in placeholders):
        return False
    return True


def clear_token_cache():
    """Clears cached token (useful for tests)."""
    global _TOKEN_CACHE
    _TOKEN_CACHE = {"token": None, "expires_at": 0}


def get_access_token():
    """
    Retrieves a valid OAuth2 Bearer access token using client credentials.
    Reuses the cached token until 60 seconds before its expiry.
    Never logs secrets or tokens.
    """
    if not is_paypal_configured():
        raise PayPalConfigError("PayPal sandbox keys not configured, see README")

    now = time.time()
    if _TOKEN_CACHE["token"] and now < (_TOKEN_CACHE["expires_at"] - 60):
        return _TOKEN_CACHE["token"]

    cid = get_client_id()
    sec = get_client_secret()

    url = f"{SANDBOX_BASE_URL}/v1/oauth2/token"
    auth_bytes = f"{cid}:{sec}".encode("utf-8")
    import base64
    auth_header = "Basic " + base64.b64encode(auth_bytes).decode("ascii")

    post_data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=post_data,
        headers={
            "Authorization": auth_header,
            "Accept": "application/json",
            "Accept-Language": "en_US",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            token = data.get("access_token")
            expires_in = int(data.get("expires_in", 32400))
            if not token:
                raise PayPalAPIError("Authentication response missing access token.")
            _TOKEN_CACHE["token"] = token
            _TOKEN_CACHE["expires_at"] = now + expires_in
            return token
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error_description") or err_json.get("message") or str(e)
        except Exception:
            msg = err_body[:200] or str(e)
        raise PayPalAPIError(f"PayPal authentication failed ({e.code}): {msg}", status_code=e.code)
    except urllib.error.URLError as e:
        raise PayPalAPIError(f"Could not reach PayPal sandbox server: {e.reason}")
    except TimeoutError:
        raise PayPalAPIError("Connection to PayPal sandbox timed out.")


def _make_api_request(endpoint, method="GET", json_data=None, access_token=None):
    """
    Executes an authenticated API request to the PayPal Sandbox Invoicing API v2.
    """
    if access_token is None:
        access_token = get_access_token()

    url = f"{SANDBOX_BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    body = None
    if json_data is not None:
        body = json.dumps(json_data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as resp:
            status_code = resp.getcode()
            raw = resp.read().decode("utf-8")
            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    return {"raw": raw}
            return {"status_code": status_code}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            # PayPal errors typically include 'message', 'details', 'name'
            msg = err_json.get("message") or err_json.get("error_description") or err_json.get("name") or str(e)
            details = err_json.get("details")
            if details and isinstance(details, list) and len(details) > 0:
                first_issue = details[0].get("description") or details[0].get("issue")
                if first_issue:
                    msg = f"{msg} ({first_issue})"
        except Exception:
            msg = err_body[:200] or str(e)
        raise PayPalAPIError(f"PayPal API error ({e.code}): {msg}", status_code=e.code)
    except urllib.error.URLError as e:
        raise PayPalAPIError(f"PayPal connection error: {e.reason}")
    except TimeoutError:
        raise PayPalAPIError("PayPal request timed out.")


def generate_next_invoice_number(access_token=None):
    """
    Calls POST /v2/invoicing/generate-next-invoice-number to fetch sequential invoice number.
    """
    try:
        data = _make_api_request(
            "/v2/invoicing/generate-next-invoice-number",
            method="POST",
            json_data={},
            access_token=access_token,
        )
        inv_num = data.get("invoice_number")
        if inv_num:
            return str(inv_num)
    except Exception as e:
        logger.warning("Could not generate invoice number from PayPal API, generating sequential fallback: %s", e)

    return f"INV-{int(time.time())}"


def create_draft_invoice(deal, recipient_email, amount, currency="USD", description="", due_date=None, access_token=None):
    """
    Calls POST /v2/invoicing/invoices to create a draft invoice.
    """
    if access_token is None:
        access_token = get_access_token()

    invoice_number = generate_next_invoice_number(access_token=access_token)
    today_str = timezone.localdate().strftime("%Y-%m-%d")

    val_decimal = decimal.Decimal(str(amount)).quantize(decimal.Decimal("0.01"))
    val_str = f"{val_decimal:.2f}"

    desc = (description or f"Invoice for {deal.title}").strip()[:300]
    org_name = (deal.organization.name if deal.organization else "KinetiQ")[:40]

    contact_name = "Valued Customer"
    if deal.contact:
        contact_name = deal.contact.full_name[:40] or "Valued Customer"

    payment_term = {"term_type": "DUE_ON_DATE_SPECIFIED" if due_date else "DUE_ON_RECEIPT"}
    if due_date:
        if isinstance(due_date, (datetime.date, datetime.datetime)):
            payment_term["due_date"] = due_date.strftime("%Y-%m-%d")
        else:
            payment_term["due_date"] = str(due_date)

    payload = {
        "detail": {
            "invoice_number": invoice_number,
            "invoice_date": today_str,
            "currency_code": currency,
            "note": desc,
            "payment_term": payment_term,
        },
        "invoicer": {
            "name": {
                "given_name": org_name,
            }
        },
        "primary_recipients": [
            {
                "billing_info": {
                    "name": {
                        "given_name": contact_name,
                    },
                    "email_address": recipient_email.strip(),
                }
            }
        ],
        "items": [
            {
                "name": desc,
                "quantity": "1",
                "unit_amount": {
                    "currency_code": currency,
                    "value": val_str,
                },
            }
        ],
        "amount": {
            "currency_code": currency,
            "value": val_str,
            "breakdown": {
                "item_total": {
                    "currency_code": currency,
                    "value": val_str,
                }
            },
        },
    }

    resp = _make_api_request(
        "/v2/invoicing/invoices",
        method="POST",
        json_data=payload,
        access_token=access_token,
    )

    paypal_id = resp.get("id")
    if not paypal_id:
        # Check href in links
        for lk in resp.get("links", []):
            if lk.get("rel") == "self":
                href = lk.get("href", "")
                paypal_id = href.rstrip("/").split("/")[-1]
                break

    if not paypal_id:
        raise PayPalAPIError("PayPal invoice creation succeeded but no invoice ID was returned.")

    return {
        "id": paypal_id,
        "invoice_number": invoice_number,
        "detail": resp.get("detail", {}),
        "status": resp.get("status", "DRAFT"),
    }


def send_invoice(paypal_invoice_id, access_token=None):
    """
    Calls POST /v2/invoicing/invoices/{invoice_id}/send to send the invoice to the recipient.
    """
    return _make_api_request(
        f"/v2/invoicing/invoices/{paypal_invoice_id}/send",
        method="POST",
        json_data={"send_to_recipient": True},
        access_token=access_token,
    )


def fetch_invoice(paypal_invoice_id, access_token=None):
    """
    Calls GET /v2/invoicing/invoices/{invoice_id} to fetch real-time invoice details.
    """
    data = _make_api_request(
        f"/v2/invoicing/invoices/{paypal_invoice_id}",
        method="GET",
        access_token=access_token,
    )

    status = data.get("status", "SENT")
    detail = data.get("detail", {})
    metadata = detail.get("metadata", {})

    payer_link = metadata.get("recipient_view_url") or ""
    if not payer_link:
        for lk in data.get("links", []):
            if lk.get("rel") in ("payer-view", "recipient-view"):
                payer_link = lk.get("href", "")
                break
    if not payer_link:
        # Construct standard sandbox payer URL
        payer_link = f"https://www.sandbox.paypal.com/invoice/p/#{paypal_invoice_id}"

    date_paid = None
    if status in ("PAID", "MARKED_AS_PAID"):
        payments = data.get("payments", {})
        transactions = payments.get("transactions", [])
        if transactions and "payment_date" in transactions[0]:
            try:
                date_paid = datetime.datetime.fromisoformat(transactions[0]["payment_date"].replace("Z", "+00:00"))
            except Exception:
                date_paid = timezone.now()
        else:
            date_paid = timezone.now()

    return {
        "id": data.get("id", paypal_invoice_id),
        "status": status,
        "payer_link": payer_link,
        "date_paid": date_paid,
        "raw": data,
    }

