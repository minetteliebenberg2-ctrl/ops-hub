# Ops Hub — New Session Startup Prompt

Copy everything below the line into a new Claude Code session.

---

## Who I am

I'm Minette (minette@facilitiesco.com). Ops Hub is a generic small-business operations app — Python desktop GUI (CustomTkinter + SQLite), frozen to Windows .exe via PyInstaller. Runs fully offline. Lives at `C:\FC Add on`.

It is derived from FC Hub (FacilitiesCo's live app at `C:\FC_Hub`) but stripped of all shade-netting pricing, FacilitiesCo branding, and client data.

## The project

Read `CLAUDE.md` and `AGENTS.md` in the project root FIRST — they contain the full architecture, module status, workflow, and session log. Those files are the source of truth.

## Current state (as of 2026-08-29)

- **DB:** `database/app.db` — SQLite, migrations run automatically on first launch
- **Tests:** 638 passed, 1 skipped
- **Exe:** `Ops Hub.exe` in project root (same PyInstaller build pattern as FC Hub — exe must live in root, not `dist/`)

## Active modules

| Module | Notes |
|--------|-------|
| Dashboard | KPIs, A-Z client finder, quick actions (incl. Add Contact), activity feed |
| CRM | Customers, contacts, sites, addresses, activity log |
| Quotes | Full chain, revision tracking, spreadsheet grid, VAT, PDF auto-save |
| Accounting | Ledger, bank import, reconciliation, financial statements |
| Accounting Workbook | Generate annual Excel workbook via `tools/build_accounting_workbook.py` |
| Job Cards | CRM → Sites tab only. Not top-level nav. |
| Calendar / Jobs | Scheduling backed by scheduled_jobs table |
| Communications | Email import, review queue, CRM jump |
| Documents | Templates, compliance library, expiry tracking |
| Gallery | Photo management — albums, tags, edit, delete, stats |
| Projects | Shows accepted quotes as project cards |
| Proposals | .docx export, customer link |
| Settings | Business settings, supplier pricing, line item types |
| Backup | Covers whole project root |

## Removed from this copy

- **Site Visit module** (`modules/site_visit/`) — deleted. Core site visit data services in `core/` are retained; dashboard activity feed and KPI strip still use them.
- Shade Sails module, shade-netting pricing engine (`core/structure_quote.py`, `core/structure_catalog.py`), all shade-netting BOM logic.
- All FacilitiesCo business identity, client data, branding.

## How to work with me

1. **Read CLAUDE.md, AGENTS.md BEFORE doing anything.** Don't ask about features we already built — search code and git history first.
2. **Ask 3-5 clarifying questions before non-trivial work.** Don't guess design or layout. Show a mock-up before building.
3. **Migrations are YOUR job.** Back up `database/app.db` before applying. Never leave a migration added-but-unapplied.
4. **Test before proposing a commit.** Run `pytest tests/ -q` AND verify the launcher starts clean. Data-layer tests passing does NOT mean the UI works.
5. **Don't commit before I confirm it works in the exe.** I run the .exe, not the source.
6. **Business identity not yet configured.** The app has placeholder branding. Don't hard-code business name, VAT status, or numbering scheme — those come from Settings when configured.

## Critical technical rules (same as FC Hub)

1. Never define `_root()` on a CTkFrame or CTkToplevel subclass — causes infinite recursion.
2. CTkToplevel must parent to a real root/Toplevel (`self.winfo_toplevel()`), never a CTkFrame.
3. tkcalendar DateEntry freezes the CTk event loop — use `ctk.CTkEntry` instead.
4. Window stacking fix is in `gui/window_focus.py` — don't remove or duplicate it.
5. Don't pass `width`/`height` to `.place()` on CTkFrame/CTkScrollableFrame — set in constructor.
6. Module auto-discovery: every `modules/*/module.py` becomes a nav entry. A folder without `module.py` breaks utility tests.

## Exe deployment

After every build:
1. Close the app (file lock)
2. `copy "dist\Ops Hub.exe" "Ops Hub.exe"`
3. Launch and confirm it loads cleanly
