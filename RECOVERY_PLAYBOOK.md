# FC Hub Recovery Playbook

## 1. First response

When FC Hub fails:

1. Stop making changes.
2. Capture the full traceback.
3. Record what changed immediately before failure.
4. Run:

```powershell
git status
git branch --show-current
git log --oneline --decorate -10
```

5. Do not reset, clean, or delete anything.

## 2. Protect data

Before recovery:

- back up `C:\FC_Hub`
- separately back up `C:\FC_Hub\database\fc_hub.db`
- verify the backup exists and has a realistic file size
- preserve `.git`

## 3. Diagnose

Check:

- `launcher.py`
- utility registration
- imports
- empty files
- missing modules
- duplicate modules
- placeholder modules
- hard-coded paths
- database startup logic
- recent Git changes
- recent AI-assisted changes

Use:

```powershell
python -m compileall C:\FC_Hub
```

Run targeted imports before launching the full GUI.

## 4. Restore order

Preferred order:

1. known-good Git commit
2. verified local backup
3. verified recent AI-assisted output
4. reconstruction from frozen specifications

Never rebuild first when a complete working version exists.

## 5. Safe overlay rules

For file overlays:

- create a dated backup first
- use copy/overlay, not mirror
- exclude `.git`
- exclude live databases
- exclude caches
- stop on copy failure
- inspect the copy log

Do not use:

```text
robocopy /MIR
git reset --hard
git clean -fd
```

unless Minette explicitly approves after the risks are explained.

## 6. Launcher recovery

A recovered launcher must:

- remain minimal
- register only real utilities
- preserve Communications
- preserve CRM
- preserve Duplicate Email / Mailbox Intelligence
- preserve Image Duplicate Finder where part of the current baseline
- produce a useful traceback on failure

Do not redesign the main window during launcher recovery.

## 7. Database recovery

If the database is suspected:

1. Do not overwrite it.
2. Copy it to a dated backup.
3. Test against a copy.
4. Run integrity checks on the copy.
5. Repair schema through controlled migration only.
6. Verify record counts before and after.

### Migration failure

If a versioned migration fails:

1. Stop application use.
2. Preserve the failed database for diagnosis.
3. Confirm `schema_migrations` and `PRAGMA user_version` did not advance.
4. Verify the pre-migration backup.
5. Restore only through the existing Backup service.
6. Run database integrity, foreign-key and migration-state diagnostics.
7. Correct the problem in a new migration version; never edit an applied
   migration.

Pending production migrations must not run automatically. Create and verify a
backup before explicitly authorising migration.

## 8. Verification sequence

After restoration:

1. syntax compilation
2. import checks
3. database initialization check
4. launch
5. Communications
6. Duplicate Email / Mailbox Intelligence
7. Image Duplicate Finder
8. CRM
9. exports and reports where affected
10. Git status

## 9. Commit recovered state

Only after all checks pass:

```powershell
git status
git add <verified files>
git commit -m "Recover Sprint XX verified working state"
git tag Sprint-XX-Recovered
```

Use the actual sprint number and verified description.

## 10. Recovery completion checklist

- FC Hub launches
- all expected utilities are visible
- all expected utilities open
- live database preserved
- no temporary paths
- no placeholders
- no unexplained files
- tests recorded
- recovery report saved
- Git commit created
- stable tag created
