# KinetiQ System Architecture & Security Design

This document details the architectural foundation of KinetiQ, focusing on multi-tenant data segregation, the AI safety confirmation pipeline, and PayPal Invoicing lifecycle verification.

---

## 1. High-Level Architecture Overview

KinetiQ is structured around a modular, multi-tenant Django backend connected to a shared MySQL 8 database, exposing responsive, mobile-first views and REST endpoints.

```
+--------------------------------------------------------------------------------+
|                             Browser / Client (PWA)                             |
|             (Bootstrap 5.3 UI, Offcanvas Drawer, Responsive Cards, Chart.js)   |
+--------------------------------------------------------------------------------+
                                       │
                               HTTPS Requests
                                       ▼
+────────────────────────────────────────────────────────────────────────────────+
|                       Django Middleware & Routing                              |
|   • Session & CSRF Security Middleware                                         |
|   • Rate Limiting (django-ratelimit)                                            |
|   • Organization Tenant Middleware (Scopes current user -> Tenant Context)     |
+────────────────────────────────────────────────────────────────────────────────+
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
+──────────────────────+    +──────────────────────+    +──────────────────────+
| crm_core & accounts  |    | payments (PayPal v2) |    |   assistant (Kine)   |
| • Companies/Contacts |    | • OAuth2 Token Cache |    | • Tenant Scoped Tools|
| • Deal Pipeline (Won)|    | • Invoice Generation |    | • Prompt Injection   |
| • Tasks & AuditLog   |    | • Send & Refresh Sync|    |   Guardrails         |
+──────────────────────+    +──────────────────────+    +──────────────────────+
        │                              │                              │
        └──────────────────────────────┼──────────────────────────────┘
                                       ▼
+────────────────────────────────────────────────────────────────────────────────+
|              Automatic Multi-Tenant Data Separation Engine                     |
|           • Abstract Base: TenantModel(organization=FK)                        |
|           • Query Engine: TenantManager & TenantQuerySet                       |
+────────────────────────────────────────────────────────────────────────────────+
                                       ▼
+────────────────────────────────────────────────────────────────────────────────+
|                             MySQL 8 Storage                                    |
|       All tables scoped by organization_id with strict foreign key cascading   |
+────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Multi-Tenant Data Separation (Strict Isolation)

All client businesses share a single database while guaranteeing complete mathematical isolation between tenants:

1. **`TenantModel` Foundation:** Every business-specific entity (`Company`, `Contact`, `Deal`, `Stage`, `Task`, `Invoice`, `AuditLog`) inherits from the abstract `TenantModel` base class:
   ```python
   class TenantModel(models.Model):
       organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
       objects = TenantManager()
       class Meta:
           abstract = True
   ```
2. **`TenantManager` & `TenantQuerySet`:** All standard ORM queries automatically filter by the tenant context of the currently executing user (`.filter(organization=request.user.organization)`).
3. **Controller Guardrails:** Detail and update views resolve objects using explicit compound lookups:
   `get_object_or_404(Model, id=pk, organization=request.user.organization)`
   Even if an attacker manually tampers with URL IDs (e.g., accessing `/invoices/42/refresh/` belonging to another business), Django returns an immediate `404 Not Found` and logs the security violation to `AuditLog`.
4. **Role Hierarchy:**
   - **Owner / Admin:** Can manage team members, access company-wide metrics, export data, and generate/send PayPal invoices.
   - **Member:** Scoped to viewing and managing assigned records; blocked from destructive deletes and invoice creation.

---

## 3. Kine AI Copilot: Safety & Human-in-the-Loop Confirmation

Kine interacts with CRM data through a defensive, multi-tier pipeline:

1. **Read-Only Inspection Tools:**
   - Tools (`search_contacts`, `search_deals`, `get_dashboard_totals`, `search_invoices`) execute strictly within the requesting user's tenant boundary and permission role.
   - Member queries for deals execute `.filter(owner=request.user)`; owner queries execute `.filter(organization=org)`.
2. **Prompt Injection & Untrusted Data Quarantine:**
   - User-generated CRM fields (e.g., contact notes, job titles) returned by tools are wrapped inside `<untrusted_crm_data>` delimiters with strict system prompts commanding the LLM to ignore embedded system instructions or override attempts.
3. **Human-in-the-Loop Action Confirmation:**
   - Kine is strictly prohibited from executing mutations (such as creating deals, deleting contacts, or sending invoices) autonomously.
   - When an action is requested, Kine formats a structured **Action Preview Card** displaying:
     - Target action & affected record details
     - Exact prefilled parameters (e.g., Invoice Amount: \$4,800 USD, Recipient: `client@example.com`)
     - An interactive **"Confirm & Execute"** button requiring a physical click and CSRF-validated POST request from the user.

---

## 4. PayPal Sandbox Invoicing & Event Verification

KinetiQ adopts a deterministic API polling and verification model:

1. **Hard-Coded Sandbox Base URL:** All HTTP traffic is locked to `https://api-m.sandbox.paypal.com`. No live credentials or endpoints can be triggered.
2. **OAuth 2.0 Access Token Management:** Tokens are acquired using client credentials and cached in-memory with expiration safety margins (reusing valid tokens and auto-refreshing upon expiry).
3. **Sequential Invoice Generation (`POST /v2/invoicing/generate-next-invoice-number`):** KinetiQ retrieves the official next invoice number from PayPal rather than guessing.
4. **Draft Creation & Immediate Dispatch:**
   - A draft invoice is posted to `/v2/invoicing/invoices` with itemized descriptions and due dates.
   - The invoice is immediately dispatched via `/v2/invoicing/invoices/{id}/send`.
   - The returned `payer_view_url` is stored locally in the `Invoice` record.
5. **Double-Submission Prevention:** Invoicing is gated exclusively to Won deals. A unique constraint and transactional checks prevent multiple active invoices on the same deal.
6. **Real-Time Verification via Status Polling:**
   - When the user clicks **"Refresh status"**, KinetiQ makes a authenticated `GET /v2/invoicing/invoices/{id}` call.
   - The verified status (`SENT`, `PAID`, `MARKED_AS_PAID`) and payment timestamps are parsed from the response payload and updated atomically.
   - This eliminates the complexity and attack surfaces of public webhook receivers while providing instantaneous, reliable verification.

