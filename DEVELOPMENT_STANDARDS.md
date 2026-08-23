# FC Hub Development Standards

## 1. Python

- Use clear, conventional Python.
- Prefer explicit code over clever code.
- Use meaningful class, method, and variable names.
- Keep functions focused.
- Avoid hidden global state.
- Use `pathlib.Path` for filesystem paths where practical.
- Use context managers for files and database connections.
- Validate external input.
- Handle errors at appropriate boundaries.
- Do not silently suppress exceptions.

## 2. Imports

Order imports as:

1. Python standard library
2. Third-party packages
3. FC Hub imports

Remove unused imports.

Avoid circular imports.

Feature registration imports belong in the launcher or dedicated registration modules, not in unrelated core code.

## 3. Files and modules

Each file must have a clear responsibility.

Use these layer boundaries:

- models and engines in `core`
- persistence in database/repository code
- feature services in `modules\<feature>\services.py`
- utility registration in `modules\<feature>\utility.py`
- feature windows in `modules\<feature>\windows.py`
- shared windows in `gui`

Do not duplicate the same engine in multiple folders.

## 4. Naming

- Classes: `PascalCase`
- Functions and methods: `snake_case`
- Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: leading underscore
- Modules: lowercase with underscores

Use established business terms consistently.

## 5. CustomTkinter and Tkinter

- Keep a single application root.
- Use `CTkToplevel` or established child-window architecture for utility windows.
- Preserve parent-child relationships.
- Avoid creating hidden additional roots.
- Keep UI work on the Tkinter thread.
- Use native `ttk.Treeview` for tabular data where already established.
- Use attached scrollbars.
- Preserve selection state during sorting or refresh where practical.
- Keep small-screen usability in mind.

## 6. Data presentation

- Store numeric values as numeric values internally.
- Format sizes, dates, and currency only for display.
- Sort by underlying numeric values, not display strings.
- Keep exports readable and deterministic.
- Use stable column order.

## 7. SQLite

- Use parameterized SQL.
- Keep schema creation idempotent.
- Use explicit transactions for multi-step writes.
- Roll back on failure.
- Close connections reliably.
- Use migrations for schema changes.
- Never use the live database for tests.
- Preserve existing data during startup.

## 8. Filesystem safety

- Do not use destructive recursive deletion without explicit approval.
- Do not use Robocopy `/MIR` for recovery overlays.
- Protect `.git` and production databases.
- Create backups before broad file operations.
- Do not hard-code temporary development paths.
- Exclude generated caches and compiled files.

## 9. Logging and diagnostics

- Startup diagnostics must identify the last completed step.
- Diagnostics must not change application architecture.
- Errors must include enough context to locate the failing component.
- Avoid printing sensitive client data.
- Logs must not grow without limit.

## 10. Testing

Minimum verification for changed Python code:

```powershell
python -m compileall .
```

Also run:

- targeted import checks
- affected service tests
- temporary-database tests
- application launch check
- affected utility smoke test

Tests must be reproducible.

## 11. Documentation

Update documentation when changing:

- architecture
- database schema
- installation steps
- utility registration
- recovery process
- sprint status

Do not leave documentation describing code that no longer exists.

## 12. Scope discipline

A repair must not become a redesign.

A feature task must not include unrelated formatting or cleanup.

Record unrelated findings for a later controlled task.

## 13. Shared module workspace

- Mount module windows through the shared `gui.module_host.ModuleHost`.
- Keep workspace margins and focus transfer in the host.
- Preserve the `create_window(master)` module contract.
- Destroy and recreate module windows when navigation changes.
- Do not recreate module windows during resize.
- Keep sidebar scrolling independent from module content.
- Do not install global mouse-wheel bindings.
- Keep Treeview and textbox scrolling attached to the owning module.
