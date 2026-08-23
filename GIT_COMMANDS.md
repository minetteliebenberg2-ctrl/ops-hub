# FC Hub Git Commands

These commands are a safe template. Inspect the repository before selecting the final commands.

## Inspect first

```powershell
cd C:\FC_Hub
git status
git branch --show-current
git log --oneline --decorate -10
git tag --list
git diff --stat
```

## Review changes

```powershell
git diff
```

## Stage verified files

Preferred:

```powershell
git add <specific verified files and folders>
```

Use `git add .` only after reviewing all changes and confirming that no database, cache, backup, or unrelated file will be staged.

## Confirm staged changes

```powershell
git status
git diff --cached --stat
git diff --cached
```

## Commit verified Sprint 18 recovery

Suggested message:

```powershell
git commit -m "Sprint 18: verify clean rebuild and restore utilities"
```

Adjust the message to match the actual audited changes.

## Tag only after all verification passes

```powershell
git tag Sprint-18-Verified
```

## Confirm

```powershell
git log --oneline --decorate -5
git status
```

## Forbidden without explicit approval

```text
git reset --hard
git clean -fd
git checkout -- .
git restore .
git push --force
git rebase --onto
git filter-branch
```

Do not use commands that discard work or rewrite history during routine recovery.
