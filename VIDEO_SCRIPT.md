# KinetiQ — Video Demo Script (2:45 Total Run Time)

---

### [0:00 - 0:25] Introduction & The Problem (25 seconds)
- **Visual:** Open on KinetiQ Login screen and log in as `admin@acme.com`. Show modern Slate Navy and Indigo dashboard.
- **Narrator Points:**
  - Introduce KinetiQ: A multi-tenant B2B CRM designed for fast-paced sales teams.
  - The Core Problem: In most CRMs, closing a deal is where the software stops. Reps have to jump to external billing tools, manually re-enter client data, and chase invoice links.
  - The KinetiQ Solution: KinetiQ seamlessly integrates the PayPal Invoicing API v2 directly into the sales pipeline—enabling one-click invoicing on Won deals and instant payment tracking.

---

### [0:25 - 0:50] The Deals Pipeline & Winning an Opportunity (25 seconds)
- **Visual:** Click **Deals** in navigation. Display the Kanban board showing deals organized by stages (*Lead*, *Contacted*, *Proposal*, *Negotiation*, *Won*).
- **Narrator Points:**
  - Showcase the visual pipeline with revenue totals per stage.
  - Drag an active opportunity or open the Won deal: **"Custom API & Microservices Architecture"** (\$4,800 USD).
  - Highlight that because this deal is marked **Won**, the PayPal Invoicing action is unlocked for the business Owner and Admin.

---

### [0:50 - 1:25] Sending a Real PayPal Sandbox Invoice (35 seconds)
- **Visual:** Click **Send PayPal invoice** button on the Won deal page.
- **Narrator Points:**
  - Notice the modal is automatically pre-filled: customer email, deal value (\$4,800.00), currency (USD), and due date.
  - Check the confirmation box and click **Create & Send Invoice**.
  - Behind the scenes: KinetiQ securely calls PayPal Invoicing API v2, generates the official next invoice number, creates a draft, dispatches it to the client, and receives the buyer's payment link.
  - Point to the new invoice card displaying the **SENT** badge, invoice number, and payer link.
  - Mention safety: Double-submission prevention guarantees only one active invoice can exist per deal.

---

### [1:25 - 1:55] Buyer Checkout & Real-Time Status Refresh (30 seconds)
- **Visual:** Open the payer link in a new tab showing PayPal Sandbox Checkout. Log in as test Personal Buyer and click "Pay Now".
- **Visual:** Switch back to KinetiQ deal page. Click the **Refresh status** button.
- **Narrator Points:**
  - In PayPal Sandbox, the buyer completes the invoice payment in seconds.
  - In KinetiQ, clicking "Refresh status" polls PayPal's API v2 to fetch verified invoice details.
  - Watch the badge instantly update to **PAID** and display the exact payment timestamp.
  - Navigate to the **Invoices** page to show the full invoice ledger with status filters and mobile-friendly cards.

---

### [1:55 - 2:20] Executive Revenue Dashboard & Kine AI Copilot (25 seconds)
- **Visual:** Click **Dashboard**. Point out the 3 PayPal payment cards: Total Invoiced, Paid & Collected, and Awaiting Payment.
- **Visual:** Open **Kine Assistant** in topbar/sidebar.
- **Narrator Points:**
  - The executive dashboard dynamically reflects the updated paid totals per currency.
  - Open Kine, the built-in AI copilot. Ask: *"What is our total invoiced and collected revenue?"* or *"Show me the status of Sarah's invoice"*.
  - Kine uses deterministic, role-scoped internal tools to answer accurately in real time.
  - Mention safety: Kine cannot perform destructive actions without an interactive confirmation card requiring an explicit user click.

---

### [2:20 - 2:45] Multi-Tenant Isolation & Wrap-Up (25 seconds)
- **Visual:** Log out of Acme Innovations. Log in as `owner@betalogistics.com` (Beta Logistics tenant). Show dashboard and deals.
- **Narrator Points:**
  - Strict Multi-Tenancy: Beta Logistics has completely separate data. Even if someone tries to access Acme's invoice or deal URL directly, KinetiQ returns a strict 404.
  - Built with Python, Django 5, MySQL 8, Bootstrap 5, Chart.js, and PayPal Invoicing API v2.
  - Delivered with one-command Docker setup and 124 passing automated tests.
  - Closing: KinetiQ turns every won deal into collected revenue. Thank you!

