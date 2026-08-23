# DEVELOPMENT_SPECIFICATION.md

# ==========================================================

# FC Hub - Development Specification

# ==========================================================

#

# Purpose:

# Defines the permanent architectural rules for FC Hub.

#

# This document is the authoritative reference for all future

# development. Every sprint, implementation and AI prompt

# must comply with these specifications unless this document

# is formally revised.

#

# Author:

# [Business Name]

#

# Revision:

# 1.0

#

# Status:

# Approved

#

# ==========================================================

# 1. PROJECT PHILOSOPHY

FC Hub is a single modular desktop application.

Every feature is treated equally as a module.

There are no special utility frameworks, plugin frameworks or secondary architectures.

Business modules, administration modules, reporting modules and utilities all follow the same framework.

The framework exists to allow new modules to be added without modifying the application core.

---

# 2. CORE PRINCIPLES

The architecture must remain:

* Simple
* Modular
* Predictable
* Self-discovering
* Maintainable
* Extensible
* Backwards compatible where practical

Avoid unnecessary abstraction.

Avoid over-engineering.

Every design decision should favour long-term maintainability.

---

# 3. PERMANENT FRAMEWORK

The permanent framework consists of:

* BaseModule
* ModuleInfo
* ModuleManager
* ModuleDiscoveryReport

These components are the only authoritative module framework.

No competing framework may be introduced.

---

# 4. MODULE DEFINITION

Every FC Hub feature is a module.

Examples include:

* CRM
* Communications
* Troubleshooter
* Backup
* Sales
* Quotations
* Operations
* Finance
* Reports
* Administration
* Batch Renamer
* Duplicate Finder
* Email Cleanup
* File Mover
* Empty Folder Finder

Utilities are modules.

Business functions are modules.

System services are modules.

---

# 5. MODULE STRUCTURE

Standard module layout:

modules/

```
module_name/

    __init__.py

    module.py

    services.py

    windows.py
```

Only module.py is required for discovery.

Additional files are permitted where justified.

---

# 6. MODULE CONTRACT

Every module must inherit from BaseModule.

Every module supplies ModuleInfo metadata.

Stable module IDs uniquely identify modules.

Display names may change.

Module IDs may not.

---

# 7. MODULE DISCOVERY

Module discovery is automatic.

ModuleManager is responsible for:

* discovery
* validation
* registration
* ordering
* reporting

The launcher must never contain manual module registration.

Adding a new module must not require editing launcher.py.

---

# 8. LAUNCHER

launcher.py is responsible only for:

* starting the application
* invoking ModuleManager
* receiving discovered modules
* launching the user interface

It must never contain:

* manual module imports
* manual registration
* hard-coded navigation

---

# 9. MODULE MANAGER

ModuleManager is the only registration authority.

Responsibilities include:

* discover modules
* validate modules
* register modules
* prevent duplicate IDs
* prevent duplicate instances
* maintain deterministic ordering
* provide module access
* produce ModuleDiscoveryReport

Discovery must be idempotent.

---

# 10. DISCOVERY RULES

Discovery must:

* continue after failures
* isolate broken modules
* report failures
* ignore invalid folders
* ignore **pycache**
* ignore hidden folders

One broken module must never prevent healthy modules from loading.

---

# 11. MODULE IDENTITY

Module identity is determined by:

Stable Module ID

Display names are descriptive only.

Duplicate display names are reported.

Duplicate module IDs are prohibited.

---

# 12. TROUBLESHOOTER

Troubleshooter uses ModuleDiscoveryReport.

It must display:

* discovered modules
* registration order
* discovery failures
* duplicate IDs
* duplicate display names
* disabled modules
* import failures
* validation failures

Troubleshooter must never perform discovery itself.

---

# 13. USER INTERFACE

Navigation is generated dynamically.

No module buttons are hard coded.

The UI reflects ModuleManager results.

---

# 14. DATABASE

The framework must never modify the live database unless the sprint explicitly requires database work.

Framework changes must leave the database unchanged.

---

# 15. FC_UTILITIES

FC_Utilities is the reference project.

It is read-only unless a sprint explicitly authorises migration.

Utilities are migrated individually.

The source project is never modified during migration.

---

# 16. TESTING

Every framework change requires:

* automated tests
* compilation verification
* live application launch
* regression testing
* database integrity verification

Code is not considered complete until verification succeeds.

---

# 17. GIT

Development follows this workflow:

Architecture

↓

Implementation

↓

Automated Tests

↓

Manual Verification

↓

Review

↓

Commit

↓

Freeze

Commits occur only after successful review.

---

# 18. DOCUMENTATION

The following documents define FC Hub development:

* PROJECT_RULES.md
* DEVELOPMENT_STANDARDS.md
* DEVELOPMENT_SPECIFICATION.md
* AI_WORKFLOW.md
* SPRINT_PROCESS.md
* RECOVERY_PLAYBOOK.md

These documents form the permanent development standard.

---

# 19. REVISION CONTROL

Architectural changes require:

* discussion
* agreement
* implementation
* verification
* documentation update

The implementation must never become the architecture.

The documentation defines the architecture.

---

# 20. RESPONSIVE MODULE WORKSPACE

The main window mounts home and module views through a shared ModuleHost.

ModuleHost owns:

* consistent outer workspace margins
* expansion within the root window
* one active module window
* destroy-and-recreate switching
* focus transfer after mounting
* safe presentation of module creation errors

Modules continue to implement `create_window(master)` and own their visible
headings. The framework does not cache module windows or wrap all module
content in a global scrolling canvas.

Navigation displays each visible module name once. Textual icon metadata is
not concatenated with display names. Navigation scrolling is independent of
Treeview and textbox scrolling, and no global mouse-wheel binding is used.

---

# 21. VERSIONED DATABASE MIGRATIONS

FC Hub schema changes use the migration runner under `core/migrations`.

Migrations:

* have contiguous integer versions
* have immutable names and SHA-256 checksums
* run one version per explicit transaction
* record only successful versions in `schema_migrations`
* mirror the latest completed version in `PRAGMA user_version`
* verify schema, integrity and foreign-key state
* roll back explicitly on failure

Fresh non-production databases may initialise to the latest baseline.
Existing production databases are inspected but are never migrated silently.
A verified pre-migration backup and explicit authorisation are required before
any production migration.

# End of Development Specification
