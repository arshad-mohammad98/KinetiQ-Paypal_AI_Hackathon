# Project Brief: Kinetiq - Multi-Tenant SaaS CRM

## 1. Executive Summary & SaaS Architecture Goal
Build Kinetiq, a commercial, multi-tenant Software-as-a-Service (SaaS) Customer Relationship Management (CRM) platform. Multiple independent businesses (organizations) will sign up, invite team members, and manage their sales operations across desktops, tablets, and mobile devices.

### Core Architecture Principles:
1. **Multi-Tenancy with Strict Isolation:** All businesses share a single MySQL 8 database. Every tenant table contains an `organization_id`. Data isolation is enforced automatically at the foundational database layer—preventing data leaks or IDOR (Insecure Direct Object Reference) vulnerabilities even if a user manipulates URL parameters.
2. **Mobile-First & Touch-Friendly:** Responsive Bootstrap 5 UI optimized for phone screens (minimum 44px touch targets, mobile table-to-card transformations, and touch-supported deals pipeline).
3. **Progressive Web App (PWA):** Installable directly to mobile home screens and desktop apps with a web app manifest and lightweight service worker.
4. **Production-Grade Security:** Hardened settings, HTTPS-enforced cookies, rate-limited auth endpoints, strict password rules, and centralized audit logging.

---

## 2. Technology Stack
* **Backend:** Python 3 + Django 5.x
* **Database:** MySQL 8.x (credentials stored strictly in `.env`; zero credentials committed to code)
* **Configuration:** Modular settings (`config/settings/base.py`, `dev.py`, `prod.py`) using `python-dotenv`
* **Frontend:** Bootstrap 5.3 + Vanilla CSS (modern Slate Navy & Indigo theme, responsive micro-interactions)
* **Mobile & PWA:** Web App Manifest (`manifest.json`), service worker, touch gestures, and mobile card transforms
* **Typography & Icons:** Google Font ('Inter') & Bootstrap Icons
* **Data Visualization:** Chart.js (interactive sales velocity, stage funnels, and revenue trends)
* **Testing:** Pytest-Django / Django TestCase automated multi-tenancy isolation test suite

---

## 3. Multi-Business SaaS Model & Automatic Data Separation

### A. Centralized Data Isolation Engine
To ensure a developer cannot accidentally expose Business A's data to Business B:
* **`TenantModel` (Abstract Base Model):** Every business-specific model inherits from `TenantModel`, which includes:
  * `organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="%(class)ss")`
* **`TenantManager` & `TenantQuerySet`:** Overrides `.get_queryset()` to automatically filter queries by the authenticated user's `organization`.
* **Request Organization Middleware:** Resolves `request.user.organization` on every incoming authenticated request and attaches it to thread-local or request scope.
* **Controller/View Layer Guard:** URL lookups enforce organization ownership:
  `get_object_or_404(Model, id=pk, organization=request.user.organization)`
* Even if an attacker enters `https://crm.app/deals/999/edit/` where `999` belongs to another business, the query returns a strict `404 Not Found`.

### B. Automated Cross-Tenant Security Tests
A dedicated automated test suite (`tests/test_tenant_isolation.py`) tests the following before deployment:
* Business A cannot query, view, edit, or delete Business B's contacts, companies, deals, or tasks.
* Direct URL parameter tampering across organizations triggers `404 Not Found`.
* CSV exports from Business A never contain Business B's records.
* Bulk CSV imports in Business A are strictly assigned to Business A's `organization_id`.

---

## 4. Signup, Team Roles & Subscription Lifecycle

### A. Self-Service Signup
* Any business owner can sign up with:
  * **Business Name** (creates the `Organization` record)
  * **Owner Name, Email, Password** (creates the primary `User` record)
* Automatic **14-day free trial** assigned upon registration (`trial_ends_at = now() + 14 days`).
* Verification email sent with a secure, time-limited activation token.

### B. Subscription & Plan Status
* Each `Organization` contains:
  * `plan_status`: `TRIAL`, `ACTIVE`, `EXPIRED`, `CANCELLED`
  * `trial_ends_at`: Timestamp marking trial expiry
  * `max_users`: Configurable user seat limit
* When `trial_ends_at` passes and no active plan is set, the application presents a friendly subscription banner (payment gateway integration ready for future phase).

### C. Team Roles & Invitations
* **Roles:**
  * **Owner:** Full system access, invite/remove users, change organization details, export all data, delete business account.
  * **Admin:** Manage team members, import/export data, manage all CRM records, view full dashboard analytics.
  * **Member:** View and manage assigned contacts, companies, deals, tasks, and personal pipeline.
* **Team Invites:** Owner/Admin sends an email invitation. The recipient clicks a unique invite token to join the existing organization without creating a duplicate business.
* **Account Recovery:** Secure password reset workflow with one-time expiring links.

---

## 5. Mobile-First Responsive Experience & PWA

### A. Mobile-First Layout
* **Touch-Friendly Navigation:** Collapsible mobile offcanvas drawer, minimum touch targets of 44px × 44px.
* **Table-to-Card Responsive Transformation:**
  * On desktop/tablet (`>= 768px`): Clean, scannable data tables with sortable columns.
  * On mobile (`< 768px`): Tables automatically transform into sleek, touchable card lists (showing key details, quick-action call/email buttons, and status tags) to eliminate clumsy horizontal scrolling.

### B. Touch-Friendly Deals Pipeline Board
* Kanban-style board categorized by sales stages (*Lead*, *Contacted*, *Proposal*, *Negotiation*, *Won*, *Lost*).
* Desktop: Smooth drag-and-drop between columns.
* Mobile/Tablet: Touch-friendly card drag + explicit **"Move Stage" button/modal** on each card as a failsafe for fast, single-thumb phone navigation.

### C. Progressive Web App (PWA) Capabilities
* **`manifest.json`:** Defines app name, standalone display mode, theme color (`#0F172A`), background color (`#F8FAFC`), and responsive icon set (192x192, 512x512).
* **Service Worker:** Caches application shell (CSS, fonts, JS, logo) for instantaneous loading on mobile connections and provides custom offline fallback pages.
* **Installable:** Prompts mobile and desktop browsers with an "Install App / Add to Home Screen" option.

---

## 6. Security & Audit Logging

### A. Hardened Security Standards
* **HTTPS & Cookies:** `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`, `SESSION_COOKIE_HTTPONLY = True`, `SECURE_BROWSER_XSS_FILTER = True`, `SECURE_CONTENT_TYPE_NOSNIFF = True` in production.
* **Environment Segregation:** All sensitive keys (`DJANGO_SECRET_KEY`, `DB_PASSWORD`, `DB_HOST`, `EMAIL_HOST_PASSWORD`) live exclusively in `.env`.
* **Split Settings:**
  * `config/settings/base.py`: Common installed apps, middleware, password validators, templates.
  * `config/settings/dev.py`: `DEBUG = True`, console email backend.
  * `config/settings/prod.py`: `DEBUG = False`, strict allowed hosts, security headers, production email backend.
* **Authentication Hardening:** Login rate limiting (blocks brute force attacks), strong password validation rules (minimum 8 characters, alphanumeric + symbol requirements).

### B. Centralized Audit Log
* Every security and business event is permanently recorded in the `AuditLog` table:
  * User ID, Organization ID, Action Type (`LOGIN`, `LOGOUT`, `CREATE`, `UPDATE`, `DELETE`, `EXPORT_DATA`, `INVITE_USER`), Model Name, Object ID, Timestamp, and IP Address.
  * Business Owners and Admins can inspect the audit trail to see who modified or deleted any record.

---

## 7. Business Owner Self-Service & Compliance
* **One-Click Data Backup / Export:** The organization owner can click "Export All Data" to download a ZIP archive containing individual CSV files (`contacts.csv`, `companies.csv`, `deals.csv`, `tasks.csv`).
* **Self-Service Account Deletion:** Owner can trigger permanent account deletion with double confirmation. This cascades and permanently purges all organization records from the database in compliance with data privacy standards.
* **Legal Pages:** Clean, accessible public pages for **Terms of Service** and **Privacy Policy** with customizable placeholder copy ready for review.

---

## 8. SaaS Platform Super-Admin Area (Master Portal)
A secure portal accessible **only** to the platform creator (Django Superuser):
* **Completely Segregated from Tenant Admins:** Regular business owners cannot access this URL.
* **Global SaaS Metrics:**
  * Total signed-up businesses and total active users across all organizations.
  * Signup dates, trial expiration countdowns, and subscription statuses (`TRIAL`, `ACTIVE`, `EXPIRED`).
  * Aggregate counts: Number of contacts and deals created per business (system health indicator).
* **Strict Privacy Boundary:** Platform admin dashboard displays **aggregate metrics only**—it **never** displays private customer names, contact emails, deal notes, or phone numbers belonging to client businesses.

---

## 9. Core CRM Modules

1. **Companies:** Directory of client organizations with industry, phone, website, address, employee count, and linked contacts/deals.
2. **Contacts:** People directory linked to companies, with direct click-to-call, click-to-email, status badges, and notes.
3. **Deals Pipeline:** Multi-stage revenue pipeline with expected close dates, win probabilities, and dynamic stage value summaries.
4. **Tasks & Reminders:** Action items with priority tags (*Low*, *Medium*, *High*, *Urgent*), due date alerts (*Overdue*, *Due Today*, *Upcoming*), and direct linkage to Contacts or Deals.
5. **Analytics Dashboard:**
   * Metric Cards: Active Deals, Total Pipeline Value, Won Revenue This Month, New Leads.
   * Chart.js Graphs: Pipeline Funnel by Stage, Monthly Revenue Trend, Deal Status Breakdown.
6. **CSV Import Engine:** Upload contacts or companies with header validation and preview before commit.

---

## 10. Database Schema Design (MySQL 8)

```
+---------------------------------------------------------------+
|                        Organization                           |
+---------------------------------------------------------------+
| id (PK)                                                       |
| name (VARCHAR 150)                                            |
| slug (VARCHAR 100, UNIQUE)                                    |
| plan_status (ENUM: 'TRIAL', 'ACTIVE', 'EXPIRED', 'CANCELLED') |
| trial_ends_at (DATETIME)                                      |
| max_users (INTEGER DEFAULT 5)                                 |
| is_active (BOOLEAN DEFAULT TRUE)                              |
| created_at (DATETIME)                                         |
| updated_at (DATETIME)                                         |
+---------------------------------------------------------------+
                             | 1
                             |
         +-------------------+-------------------+-------------------+
         | N                                     | N                 | N
+-----------------------------------+   +--------------------+   +------------------------------------+
|               User                |   |   TeamInvitation   |   |             AuditLog               |
+-----------------------------------+   +--------------------+   +------------------------------------+
| id (PK)                           |   | id (PK)            |   | id (PK)                            |
| organization_id (FK)              |   | organization_id(FK)|   | organization_id (FK)               |
| email (VARCHAR 254, UNIQUE)       |   | email (VARCHAR 254)|   | user_id (FK -> User, NULLABLE)     |
| first_name (VARCHAR 50)           |   | role (ENUM)        |   | action_type (VARCHAR 50)           |
| last_name (VARCHAR 50)            |   | token (VARCHAR 64) |   | target_model (VARCHAR 50)          |
| role (ENUM: 'OWNER','ADMIN',      |   | is_accepted (BOOL) |   | target_id (VARCHAR 50)             |
|             'MEMBER')             |   | expires_at (DTIME) |   | ip_address (VARCHAR 45)            |
| is_email_verified (BOOLEAN)       |   | created_at (DTIME) |   | description (TEXT)                 |
| created_at (DATETIME)             |   +--------------------+   | created_at (DATETIME)              |
+-----------------------------------+                            +------------------------------------+
         | 1
         |
         +-----------------------+-----------------------+
         | N                                             | N
+-----------------------------------+   +-----------------------------------+
|             Company               |   |              Contact              |
+-----------------------------------+   +-----------------------------------+
| id (PK)                           |   | id (PK)                           |
| organization_id (FK)              |   | organization_id (FK)              |
| name (VARCHAR 150)                |   | company_id (FK -> Company, NULL)  |
| industry (VARCHAR 100)            |   | first_name (VARCHAR 75)           |
| website (VARCHAR 200)             |   | last_name (VARCHAR 75)            |
| phone (VARCHAR 30)                |   | email (VARCHAR 254)               |
| address (TEXT)                    |   | phone (VARCHAR 30)                |
| created_by_id (FK -> User)        |   | job_title (VARCHAR 100)           |
| created_at (DATETIME)             |   | status (VARCHAR 50)               |
| updated_at (DATETIME)             |   | created_by_id (FK -> User)        |
+-----------------------------------+   | created_at (DATETIME)             |
         | 1                             +-----------------------------------+
         |                                                 | 1
         +-----------------------+-------------------------+
                                 | N
+---------------------------------------------------------------+
|                             Deal                              |
+---------------------------------------------------------------+
| id (PK)                                                       |
| organization_id (FK -> Organization)                          |
| title (VARCHAR 200)                                           |
| value (DECIMAL 12, 2)                                         |
| stage (ENUM: 'lead', 'contacted', 'proposal',                 |
|              'negotiation', 'won', 'lost')                    |
| company_id (FK -> Company, NULLABLE)                          |
| contact_id (FK -> Contact, NULLABLE)                          |
| owner_id (FK -> User)                                         |
| expected_close_date (DATE)                                    |
| probability (INTEGER 0-100)                                   |
| created_at (DATETIME)                                         |
| updated_at (DATETIME)                                         |
+---------------------------------------------------------------+
                             | 1
                             | N
+---------------------------------------------------------------+
|                             Task                              |
+---------------------------------------------------------------+
| id (PK)                                                       |
| organization_id (FK -> Organization)                          |
| title (VARCHAR 200)                                           |
| description (TEXT)                                            |
| due_date (DATETIME)                                           |
| priority (ENUM: 'low', 'medium', 'high', 'urgent')            |
| status (ENUM: 'pending', 'in_progress', 'completed')          |
| assigned_to_id (FK -> User)                                   |
| deal_id (FK -> Deal, NULLABLE)                                |
| contact_id (FK -> Contact, NULLABLE)                          |
| company_id (FK -> Company, NULLABLE)                          |
| created_at (DATETIME)                                         |
+---------------------------------------------------------------+
```

---

## 11. Design & UI Guidelines
* **Color Palette:**
  * **Brand Primary:** Deep Slate Navy (`#0F172A`)
  * **Brand Accent / Action:** Vibrant Indigo (`#4F46E5`) with hover (`#4338CA`)
  * **Success / Won:** Emerald Green (`#10B981`)
  * **Warning / Trial Notice:** Amber Gold (`#F59E0B`)
  * **Danger / Lost / Delete:** Rose Crimson (`#EF4444`)
  * **Surface Background:** Crisp Soft Gray (`#F8FAFC`)
  * **Cards & Containers:** Pure White (`#FFFFFF`) with subtle border (`#E2E8F0`)
* **Typography:** Clean Google Font **Inter** (weights: 400, 500, 600, 700).
* **Mobile Ergonomics:**
  * All buttons, select inputs, and interactive cards have minimum touch size of `44px`.
  * Visual feedback on click/tap (ripple or subtle transform).
  * Data tables switch to card lists below `768px` screen width.

---

## 12. Code Rules

These rules must be strictly adhered to throughout every build task:

1. **Only Required Code:** Write only the code needed for the features listed in `PROJECT_BRIEF.md`. No extra features, no "might need later" speculative code, and no unused files, functions, or packages.
2. **Django-First:** Always utilize Django's built-in features first (authentication, forms, admin, ORM, CSRF protection, messages framework) before writing custom solutions or reaching for third-party libraries.
3. **Package Approval:** Introduce a new third-party package only if it saves substantial custom code. Always explain what it is and why it is needed before adding it.
4. **DRY (Don't Repeat Yourself):** Never duplicate code. If the same logic or query pattern is needed twice, centralize it in one place.
5. **Simplicity & Conciseness:** Keep files compact, variable/function names plain and descriptive, and comments short—commenting only where the business or algorithmic logic is not immediately self-evident.
6. **Preserve Working Code:** Do not rewrite, restructure, or refactor working code unless explicitly requested.
7. **Proactive Simplicity Check:** If any task appears to require significantly more code or complexity than anticipated, stop, report it immediately, and suggest a simpler alternative.
8. **Task Completion Checklist:** At the conclusion of every step:
   * Prune all unused imports, scratch files, and dead code.
   * Run the test suite to ensure zero regressions.
   * Report the exact file count and approximate line count added/modified.

> [!IMPORTANT]
> **Safety Invariance:** Being lean does **NOT** mean compromising on safety. Never cut or dilute:
> * Automatic data separation between organizations
> * Core security protections (HTTPS cookies, CSRF, rate limits)
> * Input validation
> * Automated test suites for multi-tenant isolation and payment/subscription logic

---

## 13. Numbered Foundation-First Build Plan

1. **Step 1: Environment & Dependency Setup**
   * Create Python virtual environment (`venv`).
   * Install Django, PyMySQL/mysqlclient, python-dotenv, django-ratelimit, and development tooling.
   * Generate `requirements.txt`.

2. **Step 2: MySQL 8 Database & Split Settings Architecture**
   * Configure `.env` with database credentials, secrets, and environment flags.
   * Set up modular settings: `config/settings/base.py`, `dev.py`, `prod.py` (ensuring `DEBUG = False` ready in prod).
   * Verify MySQL 8 connection and database creation.

3. **Step 3: Multi-Tenant Architecture & Data Separation Core**
   * Create `organizations` and `accounts` apps.
   * Implement `Organization` model (with `plan_status` and 14-day `trial_ends_at`).
   * Implement abstract `TenantModel` and `TenantManager` to enforce automatic `organization_id` scoping across all future models.
   * Add tenant request middleware to guarantee every query binds to the current user's organization.

4. **Step 4: Automated Multi-Tenancy Isolation Tests**
   * Write and run automated tests (`test_tenant_isolation.py`) proving:
     * User from Org A cannot see or modify data from Org B.
     * IDOR attempts via URL parameter manipulation return 404.
   * Run automated tests to verify the isolation engine passes before building user interfaces.

5. **Step 5: Signup, Email Verification, Team Invites & Roles**
   * Build self-service business signup form (Business Name, Owner Name, Email, Password).
   * Automatically generate 14-day trial for new organization.
   * Implement email verification and password reset workflows.
   * Build Team Management portal: invite team members by email with roles (`OWNER`, `ADMIN`, `MEMBER`).

6. **Step 6: Security Hardening & Audit Logging System**
   * Implement `AuditLog` model and signals/middleware to log `LOGIN`, `CREATE`, `UPDATE`, `DELETE`, and `EXPORT` events.
   * Configure login rate limiting to block brute force attacks.
   * Apply HTTPS cookie policies and CSRF verification.

7. **Step 7: Mobile-First Master UI Shell & PWA Setup**
   * Build master responsive layout with Bootstrap 5.3, Inter font, and Bootstrap Icons.
   * Implement collapsible mobile navigation drawer and topbar with trial expiration pill.
   * Configure `manifest.json`, PWA icons, and service worker for home-screen installation.

8. **Step 8: Companies & Contacts Management**
   * Build CRUD operations for Companies and Contacts with automatic organization scoping.
   * Implement the responsive **Table-to-Card** view pattern (data table on desktop, sleek card list on phones).
   * Add search and filter controls.

9. **Step 9: Touch-Friendly Deals Pipeline Board**
   * Build multi-stage Kanban pipeline board with summary metrics per stage column.
   * Enable smooth drag-and-drop on desktop.
   * Add touch-friendly drag and a fallback **"Move to Stage" action button/modal** on each card for mobile users.

10. **Step 10: Tasks, Reminders & Notifications**
    * Build Task management interface with priority badges and due date tracking.
    * Add overdue, due today, and upcoming notification alerts on the topbar.
    * Link tasks to specific contacts, companies, or deals.

11. **Step 11: Interactive Analytics Dashboard**
    * Build KPI overview cards (Active Deals, Pipeline Value, Won Revenue, Team Member Count).
    * Build interactive Chart.js widgets: Stage Funnel, Monthly Revenue Trends, and Win/Loss Ratios.

12. **Step 12: Business Owner Tools & Legal Pages**
    * Build one-click **Export All Data** (downloads a ZIP containing all organization CSVs).
    * Build self-service **Delete Business Account** feature with safety confirmation.
    * Create clean public pages for **Terms of Service** and **Privacy Policy**.

13. **Step 13: SaaS Platform Super-Admin Portal**
    * Build dedicated platform dashboard accessible only to the Django superuser.
    * Display global SaaS metrics: Total businesses, active trials, user counts, contact counts.
    * Enforce strict privacy guardrails: Platform admin views aggregate counts only, never private customer contacts or deal details.

14. **Step 14: CSV Bulk Importer & Final End-to-End Verification**
    * Build CSV bulk import engine with validation and error reporting.
    * Execute end-to-end testing across mobile, tablet, and desktop views.
    * Prepare seed demo data and provide simple instructions for local startup and management.
