# Ops Hub — Project Instructions

## What this is
Ops Hub is a Python desktop GUI application (CustomTkinter + SQLite) — a generic small-business
operations app derived from FC Hub. Covers CRM, quoting, invoicing, accounting, job cards, site
visits, calendar/scheduling, documents, and communications. Frozen to a Windows .exe via
PyInstaller. Runs fully offline.

This is a clean starting point — no business identity, pricing, or client data has been carried
over. Fill in the sections below as the new business is configured.

---

## Business identity

**Not yet configured.** Set these before going live:
- Trading name
- VAT registration status
- Registration number
- Location
- Brand colour
- Logo — replace `assets/logo_placeholder.png`
- Numbering scheme for Quotes/Pro-Formas/Invoices/Statements/Job Cards

---

## The business workflow

**Site Visit → Measurement Form → Quote (or Proposal if images) → Pro-Forma → Invoice → Warranty**

| Step | Where in app | Notes |
|------|-------------|-------|
| 1. Site Visit | Site Visit module → hub | Schedule visit against a customer + site |
| 2. Measurement Form | Site Visit hub → Measurement Form | Record physical dimensions on site |
| 3a. Quote | Quotes module | Standard path — no images needed |
| 3b. Proposal | Proposals module | When images are required — generates .docx |
| 4. Pro-Forma | Quotes → issue → Generate Pro-Forma | Generated from an issued Quote, never hand-typed |
| 5. Tax Invoice | From Pro-Forma | Generated from Pro-Forma |
| 6. Statement | Quotes → Statements tab | Aggregates Tax Invoices over a date range |
| 7. Warranty | CRM → Sites tab → edit site | Date field, updated manually |

**Job Cards** are per-job/PO work logs. Accessed from CRM → customer → Sites tab. One card per
job/PO; add dated rows as work progresses.

This workflow is generic to a quote-based service business. Rework the step list if the new
business's sales process differs (e.g. no site visit step, or a different document chain).

---

## Pricing calculator — where to find it

The shade-netting-specific pricing engine (structure catalog, netting BOM, shade sails) has been
**stripped out of this copy**. What remains:

1. **Settings → Supplier Pricing** — generic pricing editor. Re-purpose or clear out for the new
   business's own price list.
2. **Quotes module** — line items are entered manually or via Line Item Types (Settings → Line
   Item Types). No automatic BOM calculator is wired in.

If the new business needs an automated pricing/BOM calculator like the original shade-netting one,
build it fresh against `core/quote_service.py` and `modules/settings/` rather than trying to adapt
the removed `structure_quote.py` (not included in this copy).

---

## Module status

| Module | Status | Notes |
|--------|--------|-------|
| Dashboard | Working | Light theme, real KPIs |
| CRM | Working | Customers, contacts, sites, addresses, activity log |
| Quotes | Working | Full chain, revision tracking, spreadsheet grid, VAT, PDF auto-save |
| Accounting | Working | Ledger, bank import, reconciliation, financial statements |
| Site Visit | Working | Hub, Measurement Form, Checklist, Site Plan, Visit History |
| Communications | Working | Email import, review queue, CRM jump |
| Documents | Working | Templates, compliance library, expiry tracking |
| Proposals | Working | .docx export, customer link |
| Job Cards | Working | CRM → Sites tab only. Not a top-level nav module. |
| Settings | Working | Business settings, supplier pricing, line item types |
| Gallery | Working | Photo management — albums, tags, edit, delete, stats |
| Calendar / Jobs | Working | Scheduling backed by scheduled_jobs table |
| Projects | Working | Shows accepted quotes as project cards, links to scheduled jobs |
| Backup | Working | Covers whole project root (DB + client folders + documents) |

**Removed from this copy:** Shade Sails module, shade-netting structure pricing engine
(`core/structure_quote.py`, `core/structure_catalog.py`), all shade-netting BOM logic.

---

## Architecture

```
launcher.py
└── MainWindow (sidebar + top bar + ModuleHost)
    ├── Sidebar (persistent left nav, light theme)
    ├── TopBar (search, title)
    └── ModuleHost (swappable content frame)

modules/<name>/
├── module.py     ← registers with framework (ModuleInfo, category, sort_order)
├── utility.py    ← BaseModule subclass, create_window() returns a CTkFrame
└── windows.py    ← all UI classes

core/             ← business logic, services, repositories, migrations
gui/              ← shared components (sidebar, entity_table, form_dialogs, etc.)
framework/        ← module manager, base module, auto-discovery
assets/           ← logo placeholder, default site plan grid image
database/         ← app database (created on first run — not included in this copy)
```

**Database:** `database/app.db` — SQLite, created fresh on first launch, migrations run
automatically.

**Migration pattern:**
```python
# core/migrations/versions/v00NN_name.py
MIGRATION = Migration(version=NN, name="name",
    checksum=migration_checksum(PAYLOAD), apply=apply, verify=verify)
# Auto-discovered by runner — just drop the file, no manual registration
```
Never apply to a live DB without:
```python
runner.migrate(allow_production=True, backup_verified=True)
```

---

## Exe deployment (critical)

The frozen .exe **must** live in the project root next to `launcher.py`, not in `dist/`.
`get_project_root()` in `core/app_paths.py` resolves data paths relative to the exe.
If the exe is in `dist/`, it reads a stale empty database.

**After every build:**
1. Close the app if running (file lock)
2. `copy "dist\<AppName>.exe" "<AppName>.exe"`
3. Launch exe and confirm it loads cleanly against an empty/fresh database

**PyInstaller checksum note:** The build sometimes exits code 1 at the PE-checksum step but the
exe is still fully built. Check the exe's LastWriteTime and that it launches — don't trust the
exit code alone.

---

## Critical technical rules

**1. Never define `_root()` on a CTkFrame or CTkToplevel subclass.**
tkinter calls `_root()` internally via `winfo_children()` → `nametowidget()`. Overriding it causes
infinite recursion. Use `_toplevel()` or any other name.

**2. CTkToplevel must parent to a real root/Toplevel, not a CTkFrame.**
```python
# WRONG — freeze / grab_set conflict:
self.hub = MyHub(self)           # self is CTkFrame

# RIGHT:
self.hub = MyHub(self.winfo_toplevel())
```

**3. tkcalendar DateEntry freezes the CTk event loop.**
Replace with `ctk.CTkEntry` pre-filled with `date.today().strftime("%Y-%m-%d")`.

**4. Window stacking fix is in `gui/window_focus.py`.**
Monkey-patches `CTkToplevel.__init__` to auto-raise every popup site-wide. Don't remove or
duplicate it.

**5. CTkFrame / CTkScrollableFrame: don't pass `width`/`height` to `.place()`.**
Set them in the constructor instead. CustomTkinter rejects them in `.place()`.

**6. Module auto-discovery:** `framework/module_manager.py` discovers every `modules/*/module.py`.
Adding a folder without a `module.py` breaks utility tests that enumerate modules. If a window
class should NOT be a nav module, put it in an existing module's `windows.py`.

---

## Key process rules

1. **Don't commit before the business owner confirms it works in the exe.** Data-layer tests
   passing ≠ UI works.
2. **Ask clarifying questions before non-trivial work.** Don't guess design or layout.
3. **Show a mock-up before building UI changes** when practical.
4. **Test canvas / click UI with synthetic Tk events** — `py_compile` and service tests won't
   catch click-binding bugs.
5. **Always back up the live DB before migrations.** Apply the migration; don't leave it
   added-but-unapplied.
6. **Pricing changes:** direct the business owner to Settings → Supplier Pricing — no code change
   needed for a plain price update.
7. **Search before asking.** When asked about an existing feature, search code + git history
   thoroughly before asking for a re-explanation.

---

## What is working well — don't touch without good reason

- Quote → Pro-Forma → Tax Invoice → Statement chain, numbering, revision tracking
- Payment logging, bank reconciliation, ledger
- PDF exports and auto-save to client folders
- CRM customer / contact / site / address model
- Migration runner and schema integrity checks
- Backup system (covers whole project root)
- `gui/window_focus.py` popup auto-raise

---

## Session log

**Rule: update this section before ending every session. Next Claude reads this first.**

### 2026-08-23 — repository created

Cloned from FC Hub (FacilitiesCo's live app) as a clean starting point for a new business.
Removed: all client data, FacilitiesCo business identity/pricing docs, FacilitiesCo logo,
shade-netting pricing engine and Shade Sails module, live database. Kept: full module set (CRM,
Quotes, Accounting, Site Visit, Job Cards, Documents, Communications, Gallery, Calendar, Projects,
Settings, Backup), all shared GUI/framework code, migration history up to the point of the fork.

**Next session should start with:** configure business identity (name, VAT status, reg number,
logo, brand colour), decide on document numbering scheme, and confirm the app launches clean
against a brand-new empty database.
