# FC Hub Sprint Process

## 1. Sprint preparation

Before a sprint:

1. Confirm FC Hub launches.
2. Confirm Git status.
3. Commit or safely preserve current work.
4. Tag the previous stable baseline where appropriate.
5. Define the sprint scope.
6. Freeze acceptance criteria.
7. Identify protected files and data.
8. Confirm the plan with Minette before implementing.

## 2. Sprint definition

Every sprint must state:

- sprint number and name
- baseline
- objective
- included work
- excluded work
- protected components
- acceptance criteria
- tests required
- rollback plan

## 3. Implementation

1. Read all governance files.
2. Audit the relevant code before changing anything.
3. Report the plan.
4. Make one controlled change.
5. Provide complete files.
6. Run syntax and import checks.
7. Run targeted tests.
8. Review the result against scope and architecture before reporting it done.
9. Minette tests the application.

## 4. Verification

A sprint is not complete until:

- FC Hub launches
- affected utilities open
- requested behaviour works
- existing related behaviour still works
- the live database is safe
- no hard-coded temporary paths exist
- no placeholders were introduced
- tests are recorded
- Git diff is reviewed

## 5. Git closeout

After verification:

```powershell
git status
git diff --stat
git diff
```

Then stage deliberately:

```powershell
git add <verified files>
```

Commit:

```powershell
git commit -m "Sprint XX: concise verified description"
```

Tag a stable milestone when appropriate:

```powershell
git tag Sprint-XX-Stable
```

Never tag before verification.

## 6. Sprint report

Create or update a sprint report containing:

- baseline
- files changed
- behaviour added
- defects fixed
- tests run
- test results
- known limitations
- Git commit
- tag
- next sprint candidates

## 7. Freeze

Once accepted:

- mark the sprint frozen
- do not patch it casually
- start later changes from the frozen baseline
- create a new sprint for additional work

## 8. Recovery during a sprint

If a sprint breaks the application:

1. Stop feature work.
2. Preserve the broken state for diagnosis.
3. Identify the last stable baseline.
4. Back up the live project and database.
5. Restore before rebuilding.
6. Verify each utility.
7. commit the recovered state.
8. Resume in a new controlled sprint.
