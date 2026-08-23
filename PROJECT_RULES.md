# FC Hub Project Rules

## 1. Governing principle

Protect working functionality, user data, and recoverability before adding features.

## 2. Frozen development rules

1. Give the easiest and best solution first.
2. Provide complete files, not fragments or patches, unless Minette explicitly requests a patch.
3. Restore known-good code before rebuilding it.
4. Make one controlled change at a time.
5. Never replace working modules with placeholders, stubs, or simplified substitutes.
6. Never claim a test passed unless it was actually run.
7. Never overwrite the live database during recovery, deployment, or testing.
8. Never delete or rewrite Git history to solve an ordinary coding problem.
9. Preserve unrelated working files.
10. Explain risk before any command that can overwrite, delete, reset, mirror, or clean files.
11. Use the shortest safe command first.
12. Do not make Minette assemble multi-line commands when a single safe command will work.
13. Do not repeatedly promise a deliverable. Provide it.
14. Keep instructions short and sequential during recovery.
15. Confirm the result of each major recovery step before continuing.
16. Keep the recovery checklist visible until recovery is complete.

## 2a. Build spec protection (`FC Hub.spec`)

`FC Hub.spec` must never have its `hiddenimports` list emptied or shortened, and `database` must never be added to `datas` (bundling the live DB into the exe package risks shipping stale/duplicate data). Before rebuilding, verify `hiddenimports` still includes: docx, openpyxl, PIL, reportlab + its submodules (`reportlab.lib`, `reportlab.lib.colors`, `reportlab.lib.pagesizes`, `reportlab.lib.styles`, `reportlab.lib.units`, `reportlab.lib.enums`, `reportlab.platypus`, `reportlab.pdfgen`), pypdf, send2trash, sqlite3, mailbox, csv, configparser, ctypes, email, hashlib, json, queue, uuid, getpass. If a change to this file wasn't requested, restore it before rebuilding.

## 3. Project location

Primary working repository:

```text
C:\FC_Hub
```

Do not hard-code AI-assistant scratch or output folders into application code.

## 4. Protected resources

The following must not be overwritten or deleted without explicit approval:

```text
C:\FC_Hub\.git
C:\FC_Hub\database\fc_hub.db
```

Also protect:

- client data
- exports
- backups
- configuration
- working utilities
- historical records

## 5. Application architecture

FC Hub is a modular desktop application.

Expected layers:

```text
launcher.py
framework\
core\
database\
gui\
modules\
utilities\
tests\
```

Responsibilities must remain separated:

- `launcher.py`: application startup and utility registration only
- `framework`: utility contracts and registry
- `core`: reusable domain logic and engines
- `database`: persistent data
- `gui`: shared or standalone windows
- `modules`: feature-specific services, utility registration, and windows
- `tests`: automated verification

## 6. Launcher rules

The launcher must remain minimal.

It may:

- configure CustomTkinter
- import real utility registration classes
- register utilities
- create the root application
- create the main window
- start the event loop
- provide controlled startup diagnostics

It must not:

- contain feature business logic
- recreate the database destructively
- import placeholder utilities
- depend on AI-assistant scratch or output folders
- silently swallow startup errors

## 7. Database rules

1. SQLite data must be preserved.
2. Schema changes require a controlled migration.
3. Never replace a live database with a generated test database.
4. Tests must use temporary databases.
5. Database initialization must be idempotent.
6. Existing records must survive normal startup.
7. Back up the database before migrations.
8. Do not store generated test data in the production database.

## 8. UI rules

1. Preserve established CustomTkinter architecture.
2. Preserve native `ttk.Treeview` behaviour where already used.
3. Do not replace a working native widget with a Canvas workaround without approval.
4. Keep layouts suitable for a small screen.
5. Preserve selection and multi-selection behaviour.
6. Keep scrollbars attached to the relevant control.
7. Avoid unnecessary visual redesign during functional repairs.
8. Use readable labels and consistent terminology.

## 9. Recovery rules

1. Stop before any destructive command.
2. Create a verified backup first.
3. Prefer copy/overlay operations over mirror operations.
4. Exclude the live database from rebuild overlays unless explicitly required.
5. Preserve `.git`.
6. Verify backup success before applying changes.
7. Verify syntax and imports before launch.
8. Launch and test each utility after recovery.
9. Commit only after successful verification.
10. Tag stable recovery points.

## 10. Delivery rules

Every implementation response must include:

- what changed
- complete file locations
- tests run
- test results
- remaining risks
- recommended Git commands

No vague statements such as “should work” when verification is possible.
