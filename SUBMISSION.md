# KinetiQ — Devpost Hackathon Submission

---

## 1. Project Overview & Features

### Short Pitch
KinetiQ is an AI-powered, multi-tenant B2B CRM that directly bridges closed sales deals with PayPal Invoicing API v2, empowering sales teams to turn won opportunities into collected revenue with one-click sandbox invoicing and real-time payment tracking.

### Features and Functionality
- **Multi-Tenant SaaS Foundation:** Built from the ground up for strict business data separation. Multiple organizations can sign up and invite team members, while custom `TenantModel` logic and tenant middleware guarantee that Business A can never view, query, or modify Business B's data—even by altering URL parameters or identifiers.
- **Visual Deals Pipeline & Kanban Board:** Intuitive sales pipeline allowing teams to track deals across stages (*Lead*, *Contacted*, *Proposal*, *Negotiation*, *Won*, *Lost*), with desktop drag-and-drop, mobile cards, and quick-move modals.
- **Centralized PayPal Sandbox Invoicing:**
  - **Won Deal Invoicing:** When an opportunity reaches the Won stage, Owners and Admins can create and send an official PayPal sandbox invoice with a single click. The form pre-fills the customer's email, deal amount, currency, and payment terms, with double-submission prevention guaranteeing only one active invoice per deal.
  - **Live Status Polling & Sync:** Each invoiced deal features a PayPal details card showing current status badges (*SENT*, *PAID*, *MARKED_AS_PAID*), the direct PayPal checkout link, and a "Refresh status" button that polls PayPal's Invoicing API v2 in real-time to capture completed payments and timestamps.
  - **Invoices Hub:** A dedicated `/invoices/` section with status filtering, search by recipient or number, and responsive mobile card views.
  - **Executive Revenue Dashboard:** Three dedicated metrics cards—**Total Invoiced**, **Paid & Collected**, and **Awaiting Payment**—broken down by currency, providing clear visibility into collected cash flow.
- **Kine — AI Sales Assistant Copilot:**
  - Built-in conversational AI assistant accessible directly from the CRM navigation.
  - Interacts with CRM records using deterministic, read-only internal tools (`search_contacts`, `search_companies`, `search_deals`, `get_dashboard_totals`, `search_invoices`).
  - Strict role-based scoping: team members see only their assigned deals, while owners see company-wide totals.
  - Anti-prompt-injection delimiters: untrusted customer data is tagged with defensive boundaries to neutralize prompt injection exploits.
  - Safe confirmation workflow: operations require an interactive preview card with an explicit "Confirm" click before execution.
  - Offline-safe: if no AI key is configured, Kine responds with `"Kine needs an AI key, see README"` without crashing.
- **Mobile-First Responsive Experience:** Built on Bootstrap 5.3 with clean Inter typography, responsive card transformations for tables on mobile screens, and a 44px minimum touch target size.
- **Enterprise Security & Audit Logging:** Features rate-limited authentication, CSRF validation, secure session cookie options, and an immutable `AuditLog` capturing logins, invoice actions, data exports, and deletions.

---

## 2. Explanation of Tools & Technologies Used

- **Python 3.12+ & Django 5.x:** The core backend framework, chosen for its mature ORM, robust session security, built-in CSRF defenses, form handling, and test harness.
- **MySQL 8:** Relational database providing transactional integrity and strict foreign key relationships across tenants, companies, contacts, deals, tasks, and invoices.
- **Bootstrap 5.3 & Bootstrap Icons:** Mobile-first responsive UI framework styled with custom CSS (Slate Navy & Vibrant Indigo theme) providing touch-friendly controls and responsive table-to-card transformations.
- **Chart.js:** Client-side charting library rendering interactive sales pipeline funnel charts, revenue velocity trends, and stage breakdown visualizations.
- **PayPal Invoicing API v2 (Sandbox):** Hard-coded to `https://api-m.sandbox.paypal.com`. Implemented with Python's standard library `urllib` for maximum reliability and zero external dependencies:
  - Client credentials OAuth 2.0 token caching and reuse
  - Automatic invoice number generation (`POST /v2/invoicing/generate-next-invoice-number`)
  - Draft invoice creation with line items (`POST /v2/invoicing/invoices`)
  - Instant invoice dispatching (`POST /v2/invoicing/invoices/{id}/send`)
  - Real-time invoice status verification (`GET /v2/invoicing/invoices/{id}`)
  - 15-second network timeouts and error recovery on every external network call
- **Google Gemini 3.1 Flash-Lite / OpenAI GPT-4o-mini:** Powers the Kine AI sales assistant with custom system prompts, context grounding, and function calling.
- **Google Antigravity:** The agentic development environment used to accelerate architectural design, automated test authoring, PayPal API integration, refactoring, and verification throughout the hackathon.
- **Docker & Docker Compose:** Multi-container orchestration provisioning MySQL 8 and the Django application with automatic migrations and demo seeding in a single command.

---

## 3. What Was Built During the Hackathon

> [!NOTE]
> Project development for this hackathon edition was commenced on **31 October 2026** (after the hackathon start date of 1 October 2026).

The following was constructed during the hackathon period:
1. **Complete PayPal Invoicing Module (`payments/`):**
   - Implemented `payments/paypal.py` covering token lifecycle, next invoice number generation, draft creation, sending, and status fetching with strict timeouts.
   - Built the `Invoice(TenantModel)` database model with deal linkage, PayPal invoice ID, status, amount, currency, payer link, and paid timestamp.
   - Built views for `/invoices/` list, `/deals/<id>/invoice/send/` creation, `/invoices/<id>/refresh/` status synchronization, and billing status display.
   - Built responsive HTML templates with invoice action modals, payment badges, and refresh controls.
2. **Executive Dashboard Revenue KPI Cards:**
   - Designed and integrated 3 PayPal revenue cards (Total Invoiced, Paid & Collected, Awaiting Payment) dynamically aggregated by currency.
3. **Kine AI Copilot Invoicing Capability:**
   - Added the `search_invoices` tool to `assistant/tools.py` enabling Kine to query invoice statuses and amounts.
   - Enforced missing key guardrails (`"Kine needs an AI key, see README"`).
4. **Comprehensive Automated Test Suites:**
   - 11 dedicated PayPal integration tests in `payments/tests.py` testing draft creation, sending, refresh polling, role restrictions (Members blocked from sending), double-submission prevention, and cross-tenant isolation.
   - Unit tests for missing API keys in both payments and assistant modules.
   - Total test suite expanded to 124 passing automated tests with 100% offline mocking.
5. **Hackathon Packaging & Seeding:**
   - Built `seed_demo` management command to provision two realistic, segregated tenant organizations (Acme Innovations and Beta Logistics) with users, won deals, and invoices.
   - Built `Dockerfile`, `docker-compose.yml`, and `docker-entrypoint.sh` for one-command evaluation.

