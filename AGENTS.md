# Ops Hub Development Rules

This file defines mandatory safety rules for any AI coding agent working on Ops Hub.
Read this entire file before making any changes.

---

## 1. Application purpose

Ops Hub is a Python desktop CRM and operations application for a small service business
(business identity not yet configured — see `CLAUDE.md`).

It manages the full business workflow: customer relationships, site visits, measurements, quotes,
proposals, pro-forma invoices, tax invoices, statements, job cards, payments, accounting, banking,
photos, documents, communications, scheduling, and reporting.

The application runs fully offline on Windows. It is frozen to a standalone .exe via PyInstaller.

---

## 2. Architecture

### Entry point

- **File:** `launcher.py` (repository root)
- **Start command:** `python launcher.py` (development) or `<AppName>.exe` (production)

### GUI framework

- **CustomTkinter** (a modern themed wrapper around tkinter)
- All UI is desktop-only, single-window with a sidebar and swappable module host

### Database

- **SQLite** via Python's built-in `sqlite3`
- **Live database:** `database/app.db` (created fresh on first run — not included in this copy)
- **Schema managed by:** `core/migrations/` (versioned migration files, auto-discovered by the runner)

### Main folders

| Folder | Purpose |
|--------|---------|
| `launcher.py` | Application entry point |
| `core/` | Business logic, services, repositories, data models, migrations, PDF generation |
| `gui/` | Shared GUI components (main window, sidebar, entity tables, form dialogs, flow layout, styles) |
| `framework/` | Module manager, base module class, auto-discovery |
| `modules/` | Feature modules (accounting, accounting_workbook, backup, calendar, communications, crm, dashboard, documents, gallery, projects, proposals, quotes, settings, and utility modules) |
| `assets/` | Logo placeholder, icons, fonts, default images |
| `database/` | Live SQLite database and database backups |
| `backups/` | Full project backups |
| `tests/` | Automated test suite |
| `tools/` | Standalone utility scripts |
| `config/` | Application configuration |
| `documents/` | Document templates |
| `exports/` | Generated export files |
| `logs/` | Application logs |

### Startup sequence

1. `launcher.py` imports `customtkinter`, loads fonts, connects to the database
2. `MigrationRunner` applies any pending schema migrations
3. `module_manager` auto-discovers all `modules/*/module.py` files
4. `MainWindow` builds the sidebar navigation and module host
5. `window_focus` monkey-patches CTkToplevel to auto-raise popups

---

## 3. Business-critical functionality

The following areas are business-critical. Changes to any of them require extra caution, thorough testing, and explicit approval for anything beyond trivial fixes:

- **Customers** — CRM records, contacts, sites, addresses, activity log
- **Projects** — accepted quotes tracked as active projects
- **Site measurements** — measurement forms linked to site visits
- **Quotes** — quote creation, line items, revision tracking, PDF generation
- **Invoices** — pro-forma and tax invoice generation, numbering sequence
- **Payments** — payment logging, allocation to invoices
- **Accounting** — ledger, bank reconciliation, financial statements, categories
- **Expenses** — expense tracking within the accounting module
- **Banking integrations** — bank statement CSV import, transaction matching
- **Photos and documents** — site images, gallery, document templates, compliance library
- **Communications** — email import, review queue, CRM linking
- **Reports** — financial reports, KPI dashboard, ledger exports
- **Job cards** — per-job work logs linked to customers and sites
- **Scheduling** — calendar, scheduled jobs

---

## 4. Safety rules

These rules are non-negotiable:

1. **Never delete data.** No DROP TABLE, no DELETE without WHERE, no truncation of production records.
2. **Never delete or rename files without explicit approval.**
3. **Never change the database schema destructively.** No dropping columns, tables, or removing records without explicit approval.
4. **Never change accounting calculations during a visual-only change.**
5. **Never change banking integrations during an unrelated change.**
6. **Never rewrite the whole application for a small request.**
7. **Never replace working functionality with a simplified demo.**
8. **Never create duplicate versions of active files.**
9. **Never edit backup, temporary, or obsolete files unless explicitly requested.**
10. **Never assume which file is active; trace the imports and startup path.**
11. **Never make unrelated improvements while completing a requested change.**
12. **Never change multiple modules when one module is sufficient.**
13. **Never use fake production data.**
14. **Never expose passwords, API keys, banking credentials, or private customer data.**
15. **Never commit secrets to GitHub.**
16. **Never remove the Contact Person field from `CustomerForm`.** It loads/saves the primary contact name — any rewrite of `CustomerForm` must preserve it.

---

## 5. Required workflow before coding

Before making any change, the AI must:

1. **Restate the requested change** in plain language to confirm understanding.
2. **Inspect the relevant files** — read the actual code, do not guess.
3. **Trace imports and dependencies** to understand what is connected.
4. **Identify the active code path** — follow from `launcher.py` through module discovery.
5. **List the exact files it plans to edit.**
6. **Explain possible risks** — what could break.
7. **State what it will not change.**
8. **Wait for approval** if the change is potentially risky or ambiguous.

---

## 6. Required workflow after coding

After making any change, the AI must:

1. **Run syntax checks** (`python -m py_compile <file>`).
2. **Run available tests** (`pytest tests/ -q`).
3. **Start the application** (`python launcher.py`) to verify it launches.
4. **Test the affected workflow** end to end.
5. **Check that database access still works.**
6. **Check that imports still work.**
7. **Report every changed file.**
8. **Report every test performed.**
9. **Report any unresolved issue.**
10. **Never claim that something works without testing it.**

---

## 7. Change classification

### Safe changes

Low risk, can proceed without a backup plan:

- Text changes (labels, tooltips, messages)
- Colour changes
- Spacing and padding changes
- Button labels
- Small layout changes that do not affect business logic

### Moderate-risk changes

Require a clear plan before editing:

- Changes to shared UI components (anything in `gui/`)
- Changes to navigation or module structure
- Changes to forms or data entry screens
- Changes to customer, project, or quote screens
- Changes to file and photo handling

### High-risk changes

Require a plan, a database backup, and explicit approval:

- Database schema changes (migrations)
- Accounting calculations or ledger logic
- Invoice or quote numbering sequences
- Payment matching and allocation
- Banking integrations and statement import
- Authentication or security changes
- Import/export processes
- Changes affecting multiple modules simultaneously
- Changes to the application startup process (`launcher.py`, `framework/`, `core/database.py`)

---

## 8. Database rules

- The existing database must be **backed up before any schema change**.
- Migrations must be **reversible** where practical.
- Existing records must **remain compatible** after migration.
- No columns, tables, or records may be **removed without explicit approval**.
- Database changes must be **tested with a copy** of the production database first.
- The application must **fail safely** if the database is unavailable.
- Migrations are auto-discovered from `core/migrations/versions/`. Never apply to the live database without `allow_production=True, backup_verified=True`.

---

## 9. User interface rules

Ops Hub should look and feel like a modern, minimalist business CRM:

- Professional and practical — built for daily use by a business owner
- Designed primarily for laptop use (1366x768 minimum)
- Dark charcoal or navy sidebar navigation
- Light workspace area
- Clear page hierarchy with consistent headers
- Clean tables with readable data density
- Consistent status badges and colour coding
- Spacious but information-dense layouts
- No excessive gradients or shadows
- No unnecessary decorative cards or animations
- No generic redesign that breaks the existing workflow
- Preserve existing terminology unless a terminology change is explicitly requested
- Brand colour: **not yet configured** — set in `gui/design_tokens.py` when the new business is defined

### Colour scheme

All colours are defined in `gui/design_tokens.py` (single source of truth). `gui/styles.py` re-exports from it. `gui/ctk_theme.py` generates a CustomTkinter theme JSON from these tokens at startup — every CTk widget inherits the brand colour by default.

**Never hardcode hex colours in module files.** Always use `COLORS["key"]` from `gui.design_tokens`.

| Token | Usage |
|-------|-------|
| `accent_primary` | Brand colour — all primary buttons, active states |
| `accent_hover` | Primary button hover |
| `accent_light` | Light tint for badges, active sidebar |
| `button_secondary` | Grey secondary/utility buttons |
| `button_secondary_hover` | Secondary button hover |
| `surface_primary` | Main content background |
| `surface_secondary` | Headers, cards |
| `surface_tertiary` | Sidebar, disabled states |
| `text_primary` | Body text, headings |
| `text_secondary` | Supporting text |
| `text_tertiary` | Metadata, hints |
| `success` | Positive / completed |
| `warning` | Caution |
| `danger` | Destructive actions |
| `info` | Informational |
| `border_default` | Standard borders |
| `sidebar_bg` | Sidebar background |
| `sidebar_active_bg` | Sidebar active item |
| `sidebar_active_text` | Sidebar active text |

Actual hex values from the FacilitiesCo source have been left in place in `gui/design_tokens.py` as a starting palette — replace them once the new business's brand colours are decided.

**Runtime overrides:** Users can change any colour via Settings → Appearance. Overrides are saved to `user_theme.json` and applied on restart. The Appearance panel covers 16 colour keys and 6 font slots.

---

## 10. Git and backup rules

- Work must be performed on a **branch** where practical.
- The **main branch must remain stable**.
- Small changes should be **committed separately** with clear messages.
- Commit messages must **describe the change**, not just "update" or "fix".
- The AI must **not force-push**.
- The AI must **not rewrite history**.
- The AI must **not use destructive Git commands** (reset --hard, clean -f, branch -D) without explicit approval.
- A **working restore point** must exist before risky changes.
- The production .exe must live in the project root, not in `dist/`.
- **All commits must be pushed to GitHub** (`git push origin main`) before the session ends. Never leave commits local-only.

---

## 11. Communication rules

The AI must:

- **Ask questions instead of guessing** — 3 to 5 clarifying questions before non-trivial work.
- **Explain technical terms in plain language.**
- **Keep changes limited to the request** — no scope creep.
- **Mention when a request conflicts** with the existing architecture.
- **Say clearly when it cannot safely complete a task.**
- **Give simple instructions for testing the result.**
- **Search code, git history, and context before asking** the user to re-explain something that was already built.

---

## 12. Current repository findings

This repository was forked from FC Hub (a live app built for a shade-netting business) on
2026-08-23 as a clean, business-agnostic starting point. See `CLAUDE.md` session log for what was
stripped and what was kept.

| Item | Finding |
|------|---------|
| **Active entry point** | `launcher.py` (repository root) |
| **Start command** | `python launcher.py` (dev) / `<AppName>.exe` (production) |
| **GUI framework** | CustomTkinter (ctk) |
| **Database** | SQLite — `database/app.db`, created fresh on first launch |
| **Main folders** | `core/`, `gui/`, `framework/`, `modules/`, `assets/`, `database/`, `tests/`, `tools/` |
| **Important shared files** | `gui/main_window.py`, `gui/entity_table.py`, `gui/form_dialogs.py`, `gui/flow_layout.py`, `gui/window_focus.py`, `gui/styles.py` (re-export shim), `gui/design_tokens.py` (single source of truth for colours/fonts), `gui/ctk_theme.py` (generates CTk widget defaults from tokens), `core/database.py`, `core/app_paths.py`, `framework/module_manager.py` |
| **Business-critical files** | `core/quote_service.py`, `core/quote_repository.py`, `core/quote_pdf.py`, `core/numbering_service.py`, `core/ledger_service.py`, `core/ledger_repository.py`, `core/payment_service.py`, `core/payment_repository.py`, `core/financial_statements.py`, `core/bank_statement_parser.py`, `core/supplier_pricing_service.py`, `core/crm_service.py`, `core/crm_repository.py` |
| **Existing tests** | `tests/` directory with test files covering CRM, quotes, migrations, services, PDF generation. Shade-sail-specific tests were removed with the module — re-run `pytest tests/ -q` after the fork to confirm the suite is clean in this copy. |
| **Known technical risks** | Never define `_root()` on a CTkFrame subclass (causes infinite recursion). CTkToplevel must parent to a real root/Toplevel, not a CTkFrame. tkcalendar DateEntry freezes the CTk event loop. Do not pass `width`/`height` to `.place()` on CTkFrame. |
| **Customer numbering** | `customer_number_prefix()` in `core/crm_repository.py` strips leading articles ("The", "A", "An") before taking first 3 letters. Only affects new customers. |
| **PDF BILL TO block** | Quote, Pro-Forma, and Tax Invoice PDFs show the primary contact person's name under the company name, passed as `contact_name` kwarg to all three PDF generators. |
| **Theme system** | `gui/ctk_theme.py` generates a CTk theme JSON from `COLORS` at startup. `launcher.py` calls `apply_ctk_theme()` — never use `ctk.set_default_color_theme("blue")` or hardcoded hex in modules. All modules must use `COLORS["key"]` from `gui.design_tokens`. |
| **Job KPI cost logic** | `modules/dashboard/kpi_window.py` — maintenance-style items use a DB-driven cost map from `job_cost_items` (editable via Settings → Job Costing). Each item has a cost_bucket (labour/cable/materials/netting) and GP%. Any structure-BOM-driven costing that existed in the source app was removed with the shade-netting pricing engine — this will need rework for the new business's own product/service costing model. |
| **Job Costing tool** | Settings → Job Costing tab. Editable list of cost items with Sell Price, auto-calculated Cost (sell × (1 − GP%)), cost bucket, and GP%. Stored in `job_cost_items` table (migration v0047). `JobCostItemRepository.cost_map()` feeds the KPI window. |
| **Customer edit form** | `CustomerForm` in `modules/crm/windows.py` includes a Contact Person field that loads/saves the primary contact. Never remove it. |
| **Troubleshooter** | Tools → Troubleshooter. Runs diagnostic checks (project structure, Python env, dependencies, imports, module registration, module discovery, folder access, database health, backups, paths/resources, overall health) + migration apply. |
| **Window maximised** | The app opens maximised by default (`self.master.state("zoomed")` in `gui/main_window.py`). NOTE: this does not fire reliably on all PCs — a ⛶ button next to the Dashboard heading calls `winfo_toplevel().state("zoomed")` as a manual workaround (added 2026-09-11). |
| **Annual Compliance module** | `modules/annual_compliance/` — Payroll, Annual Returns, and COIDA Tracker tabs. No hardcoded business details — all fields are entered by the user. Icons registered in `gui/components/sidebar.py` ICON_MAP (`annual_compliance` → 🗂️) and `gui/components/module_nav.py` ICON_MAP (`FileCheck` → ✅). Migration v0051. Added 2026-09-11. |
| **Supplier Pricing PDF import** | Settings → Supplier Pricing → "Import from PDF" button. Opens a two-panel dialog: left is a queue of auto-parsed items (via `pdfplumber`), right is controls (category, supplier, VAT checkbox, manual add). Duplicates prompt Update / Skip / Add New. |
| **Supplier Pricing → Line Item Types picker** | Settings → Line Item Types → "From Supplier Pricing" button. Filterable picker to create Line Item Types from supplier pricing items, sell price auto-calculated from cost + GP% (default 45% — reconsider for the new business). |
| **Accounting Dashboard** | Three-panel layout: expense breakdown donut chart (top 7 categories + Other), monthly income vs expenses bar chart, recent transactions. Uses matplotlib for all charts. KPI cards at top (Income/Expenses/Profit). |
| **Manage Accounts** | Accounting Hub → "Manage Accounts" button. Standalone window to add bank account names. `bank_accounts` table (migration v50) stores names independently of transactions. `list_accounts()` unions both sources. Bank import dropdown also allows typing new names. |
| **Daily scheduled backup** | `tools/scheduled_backup.py` — runs at 18:00 SAST via Windows Task Scheduler ("Ops Hub Daily Backup"). Creates a full backup then deletes backups older than 7 days via `BackupService(retention_days=7)` + `shutil.rmtree()`. Logs to `logs\scheduled_backup.log`. `modules/backup/services.py` DATABASE_RELATIVE_PATH is `app.db` (corrected 2026-09-11). |
| **Removed from this copy** | Shade Sails module (`modules/shade_sails/`), shade-netting structure pricing engine (`core/structure_quote.py`, `core/structure_catalog.py`), netting-specific quote logic in Proposals, all client data, FacilitiesCo business identity/branding/pricing docs, the live database. |
