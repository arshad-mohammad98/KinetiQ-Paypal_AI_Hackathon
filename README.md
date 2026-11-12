# KinetiQ — AI-Powered Multi-Tenant CRM with PayPal Invoicing

KinetiQ is a modern, multi-tenant B2B Customer Relationship Management (CRM) platform designed for fast-growing sales organizations. It equips sales teams with collaborative deal pipelines, real-time analytics, and Kine, an intelligent AI sales copilot. By directly bridging closed deals with PayPal Invoicing API v2, KinetiQ empowers businesses to turn won opportunities into collected revenue seamlessly within one unified interface.

---

## Key Features

- **Multi-Tenant Data Isolation:** Strict database-level organization segregation via `TenantModel` and automated middleware—preventing any cross-business data visibility or IDOR vulnerabilities.
- **Visual Deals Pipeline & Kanban:** Drag-and-drop opportunity tracking across stages (*Lead*, *Contacted*, *Proposal*, *Negotiation*, *Won*, *Lost*), with mobile card views and quick-stage modals.
- **Centralized PayPal Sandbox Invoicing:** 
  - Generate and send real PayPal sandbox invoices directly from Won deals in a single click.
  - Live PayPal status synchronization (*SENT*, *PAID*, *MARKED_AS_PAID*) via on-demand polling.
  - Dedicated Invoices management page with search, status filtering, and mobile card views.
  - Real-time revenue analytics dashboard displaying Total Invoiced, Paid & Collected, and Awaiting Payment metrics per currency.
- **Kine AI Copilot:**
  - Fast, context-aware sales assistant for instant business queries ("What deals did we close this month?", "Show me Sarah's contact info").
  - Server-enforced role and tenant scoping: team members only see their own assigned deals, while owners view company-wide data.
  - Safe-action workflow: destructive or financial actions require explicit user confirmation via an interactive preview card before execution.
- **Mobile-First & Touch-Friendly:** Responsive Bootstrap 5.3 UI engineered for desktop, tablet, and mobile screens.
- **Enterprise Security & Audit Trail:** Rate-limited authentication, HTTPS security headers, session protections, and an immutable `AuditLog` tracking all critical actions.

---

## How PayPal Invoicing is Central to KinetiQ

Rather than treating payments as a detached external step, KinetiQ places PayPal Invoicing at the core of the B2B sales cycle:

1. **One-Click Invoicing on Won Deals:** When a deal reaches the **Won** stage, owners and admins are presented with a "Send PayPal invoice" action. The form pre-fills the deal amount, currency, and buyer contact email, generates the next sequential invoice number through PayPal's v2 API, creates a draft, and dispatches the live invoice. Double-submission locks ensure only one active invoice exists per deal.
2. **On-Demand Status Synchronization:** Each invoiced deal features a PayPal details panel displaying the current invoice badge, direct link to the buyer's PayPal checkout page, and a "Refresh status" button that polls PayPal API v2 to capture payment confirmations and timestamps immediately.
3. **Executive Revenue Dashboard:** The executive dashboard features dedicated PayPal revenue metric cards—**Total Invoiced**, **Paid & Collected**, and **Awaiting Payment**—grouped by currency, giving founders and sales leaders an immediate view of outstanding cash flow and finalized revenue.

---

## How Kine and the AI Work

Kine is KinetiQ's built-in conversational AI assistant, powered by Gemini 1.5 Flash (or OpenAI GPT-4o-mini):

- **Read-Only Context Introspection:** Kine interacts with the CRM using deterministic, read-only internal tools (`search_contacts`, `search_companies`, `search_deals`, `get_dashboard_totals`, `search_invoices`). Every tool strictly inherits the authenticated user's organization scope and permission tier.
- **Anti-Prompt-Injection Safeguards:** All customer-provided text returned by tools is wrapped in untrusted data delimiters and accompanied by defensive instructions that instruct the model to ignore any embedded system override attempts.
- **Interactive Action Confirmation:** If a user requests an operational modification, Kine does not mutate data directly in chat. Instead, Kine constructs a structured, pending action card (e.g., preparing a PayPal invoice or updating a deal stage) requiring the user to review the prefilled parameters and click an explicit **"Confirm & Execute"** button in the UI.
- **Graceful Offline Degradation:** If no AI key is configured, Kine cleanly informs the user: `"Kine needs an AI key, see README"`, ensuring the application remains completely functional without crashing.

---

## What Was Built During the Hackathon

> [!NOTE]
> Project work for this submission was initiated on **31 October 2026**, well after the official hackathon start date of 1 October 2026.

During the hackathon, the following core modules were architected and implemented:
1. **PayPal Invoicing API v2 Integration (`payments/paypal.py`):**
   - OAuth 2.0 client credentials token management with automatic in-memory cache and expiry reuse.
   - Sequential invoice number generation (`POST /v2/invoicing/generate-next-invoice-number`).
   - Draft invoice creation with itemized line items and due dates (`POST /v2/invoicing/invoices`).
   - Immediate invoice dispatching (`POST /v2/invoicing/invoices/{id}/send`).
   - Live status fetching and parsing (`GET /v2/invoicing/invoices/{id}`).
   - Comprehensive error handling and 15-second network timeouts on all external requests using Python standard library `urllib` (zero external HTTP dependencies).
2. **PayPal Data Models & Multi-Tenant Views (`payments/models.py`, `payments/views.py`):**
   - Tenant-scoped `Invoice` model linking deals to PayPal invoice IDs, status, recipient, due dates, payment links, and paid timestamps.
   - Dedicated `/invoices/` list view with search, status filters, and responsive mobile cards.
   - Won-deal PayPal invoice modal with prefilled data, confirmation checks, and double-submission protection.
   - Instant "Refresh Status" endpoint updating local deal metrics from PayPal's real-time state.
3. **Executive Dashboard Payment Metrics (`accounts/views.py`, `templates/accounts/dashboard.html`):**
   - Three high-visibility KPI cards for Total Invoiced, Paid & Collected, and Awaiting Payment.
4. **Kine AI Copilot PayPal Tool Integration (`assistant/tools.py`):**
   - Added `search_invoices` tool to allow Kine to answer natural language questions about invoice status, paid dates, and outstanding balances.
   - Updated dashboard calculation tools to incorporate live invoiced totals.
5. **Automated Test Suite & Mocking (`payments/tests.py`, `assistant/tests.py`):**
   - 11 dedicated PayPal integration tests covering token reuse, invoice creation, status refresh, tenant isolation, permissions, and timeout handling with 100% mocked offline calls.
   - Complete 124-test regression suite verifying zero cross-tenant leakage.
6. **One-Command Docker Demo Environment & `seed_demo` CLI:**
   - Automated MySQL 8 + Django container orchestration with migrations and rich demo tenant data provisioning.

---

## Setup & Running KinetiQ

You can run KinetiQ using **Docker** (recommended for evaluation) or **Manual Setup**.

### Option A: Docker Setup (One Start Command)

Requirements: Docker Desktop installed and running.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/arshad-mohammad98/KinetiQ-Paypal_AI_Hackathon.git
   cd KinetiQ-Paypal_AI_Hackathon
   ```
2. **Configure Environment Variables (Optional for Sandbox & AI):**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Add your PayPal Sandbox credentials and Gemini/OpenAI API key to `.env` (the app will still run smoothly without them using demo fallbacks).
3. **Start the complete stack:**
   ```bash
   docker compose up --build
   ```
   *This automatically starts MySQL 8, applies database migrations, runs `seed_demo`, and launches KinetiQ on `http://127.0.0.1:8000/`.*

---

### Option B: Manual Local Setup

Requirements: Python 3.12+ and MySQL 8 (or SQLite fallback).

1. **Clone the repository:**
   ```bash
   git clone https://github.com/arshad-mohammad98/KinetiQ-Paypal_AI_Hackathon.git
   cd KinetiQ-Paypal_AI_Hackathon
   ```
2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # Linux/macOS:
   source venv/bin/activate
   # Windows:
   .\venv\Scripts\activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure your `.env` file:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your database credentials, PayPal sandbox credentials, and AI key.
5. **Run migrations and seed demo data:**
   ```bash
   python manage.py migrate
   python manage.py seed_demo
   ```
6. **Start the development server:**
   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```
   Open your browser and navigate to `http://127.0.0.1:8000/`.

---

## Demo Login Credentials

The `seed_demo` command automatically provisions two fully populated, segregated business organizations:

### 1. Acme Innovations (Primary Demo Tenant)
- **Owner / Admin Login:**
  - **Email:** `admin@acme.com`
  - **Password:** `DemoAdmin123!`
  - **Features to explore:** Won deals with "Send PayPal invoice" button, Invoice details panel with "Refresh status", Invoices list page, and full executive dashboard metrics.
- **Team Member Login:**
  - **Email:** `member@acme.com`
  - **Password:** `DemoMember123!`
  - **Features to explore:** Role-based permission scoping (can view deals and status, but invoice creation is restricted to Owner/Admin).

### 2. Beta Logistics (Strict Tenant Isolation Verification)
- **Owner Login:**
  - **Email:** `owner@betalogistics.com`
  - **Password:** `DemoBeta123!`
  - **Features to explore:** Shows complete data isolation; zero access to Acme Innovations deals, contacts, or invoices even if URL IDs are manually changed.

---

## PayPal Sandbox Setup & Testing Guide

Follow these simple steps to obtain sandbox credentials and test live invoice sending and payment:

### 1. Create a Free PayPal Developer Account & Sandbox App
1. Go to the [PayPal Developer Portal](https://developer.paypal.com/) and log in with your PayPal account.
2. Navigate to **Dashboard > Apps & Credentials**.
3. Ensure the toggle is set to **Sandbox**.
4. Click **Create App**, give it a name (e.g., `KinetiQ Invoicing Demo`), and select **Merchant** as the app type.
5. Copy your **Client ID** and **Secret**.

### 2. Configure the Keys in KinetiQ
Add the keys to your `.env` file:
```env
PAYPAL_CLIENT_ID=your_sandbox_client_id_here
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret_here
```
*(Note: If keys are omitted, the "Send PayPal invoice" button will safely display "PayPal sandbox keys not configured, see README" without throwing any exceptions).*

### 3. Identify Sandbox Accounts
In the PayPal Developer dashboard, go to **Testing Tools > Sandbox Accounts**:
- **Business Account (Seller):** Automatically linked to your sandbox app credentials.
- **Personal Account (Buyer):** Note the sandbox buyer email (e.g., `buyer-test@personal.example.com`) and default password.

### 4. End-to-End Test Workflow
1. Log in to KinetiQ as `admin@acme.com` (`DemoAdmin123!`).
2. Go to **Deals** and select the Won deal: **"Custom API & Microservices Architecture"**.
3. Under the **PayPal Sandbox Invoicing** section, click **Send PayPal invoice**.
4. In the modal, ensure the recipient email matches your sandbox Personal buyer email, check the confirmation checkbox, and click **Create & Send Invoice**.
5. Once sent, the invoice details panel appears with a **PAID / SENT** badge and a **View PayPal Invoice (Payer Link)**.
6. Click the payer link (or open it in an Incognito window) to load `https://www.sandbox.paypal.com/invoice/p/...`.
7. Log in with your sandbox **Personal buyer account** and complete the test payment.
8. Return to KinetiQ, open the deal, and click **Refresh status**.
9. KinetiQ polls the PayPal API, updates the status badge to **PAID**, records the paid timestamp, and increments your **Paid & Collected** dashboard cards!

---

## AI Assistant Configuration

Kine supports Google Gemini and OpenAI models. To enable live conversational AI:

In `.env`:
```env
# For Google Gemini (Recommended):
LLM_API_KEY=AIzaSy...your_gemini_key_here
LLM_MODEL=gemini-3.1-flash-lite

# Or for OpenAI:
LLM_API_KEY=sk-...your_openai_key_here
LLM_MODEL=gpt-4o-mini
```

---

## Tools & Technologies Used

- **Backend:** Python 3.12+, Django 5.x, MySQL 8
- **Payment Engine:** PayPal Invoicing API v2 (Sandbox mode, token caching, draft creation, dispatch, polling)
- **AI Engine:** Google Gemini 1.5 Flash / OpenAI GPT-4o-mini with custom multi-tenant function calling
- **Frontend:** Bootstrap 5.3, Inter typography, Bootstrap Icons, Chart.js for data visualization
- **Security:** Django CSRF protection, django-ratelimit, HTTPS cookie configurations, and custom audit logger
- **Dev & Deployment:** Docker, Docker Compose, Antigravity AI Agentic Assistant for accelerated development
- **Testing:** Django automated TestCase suite with 100% offline mocked API testing (124 tests passing)

---

## License

This project is licensed under the MIT License - see the [LICENSE](file:///LICENSE) file for details.  
Copyright (c) 2026 Mohammad Arshad.
