# FC Hub Backup Module

The Backup module creates verified full backups through the native FC Hub
module framework. The default destination is `C:\FC_Hub\backups`, but the
dashboard accepts another local, external, network, or synchronised folder.

## Safe use

1. Choose a destination with enough free space. Prefer an external drive or a
   different physical drive from FC Hub.
2. Create a backup and wait for the manifest verification to complete.
3. Copy a verified backup folder off the computer for offsite protection.
4. Use **Verify Backup** before relying on a backup.
5. Use **Prepare Restore** to inspect files and overwrite targets. A preview
   changes nothing.

Backups contain a versioned manifest, application and Git metadata, selected
project files, module data, configuration, documents, and a consistent SQLite
database snapshot created with `sqlite3.Connection.backup`. The live database
file is never copied as an ordinary file.

The manifest identifies configuration or key material that may contain
passwords, tokens, credentials, or private keys. Do not publish those files or
their manifest paths without reviewing them.

## Recovery rules

- Never manually edit a manifest or backup file.
- A backup marked `incomplete`, `failed`, or `unverified` must not be restored.
- FC Hub must be closed for an actual restore. The current implementation
  provides a guarded full-restore method; the dashboard only prepares and
  previews it.
- A pre-restore safety backup is required before any real restore.
- If FC Hub cannot launch, preserve the repository and database, inspect the
  manifest and verification result, and follow [`RECOVERY_PLAYBOOK.md`](../../RECOVERY_PLAYBOOK.md).

The module distinguishes **created**, **verified**, and **restore-tested**. A
production backup is never called restore-tested unless an isolated restore
test has actually passed. Retention only reports candidates; no backup is
deleted automatically and at least one verified backup is preserved.
