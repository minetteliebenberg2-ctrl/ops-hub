# FC Hub AI Workflow

## 1. Purpose

This file defines how AI-assisted development on FC Hub works, and what
Minette's role is in it.

## 2. Roles

### The assistant (currently Claude Code)

Handles the full development loop for a task:

- reading governance files and auditing the relevant code
- reporting the plan before changing anything
- implementing one controlled change
- running syntax checks, import checks, and targeted tests
- reviewing its own result against the frozen rules before reporting it
  done
- providing safe Git commands

### Minette

- approves scope
- runs local commands when required
- verifies visible application behaviour
- decides whether functionality is acceptable
- approves commits and tags

## 3. Mandatory order of work

For every coding task:

1. Read `PROJECT_RULES.md`, `AI_WORKFLOW.md`, `DEVELOPMENT_STANDARDS.md`,
   `DEVELOPMENT_SPECIFICATION.md`, `SPRINT_PROCESS.md`, and
   `RECOVERY_PLAYBOOK.md`.
2. Inspect the current repository.
3. Confirm the requested scope.
4. Identify the safest known-good baseline.
5. Audit before changing.
6. Implement one controlled change.
7. Run verification.
8. Review the result against frozen rules.
9. Ask Minette to test visible behaviour.
10. Provide safe Git commands.
11. Commit and tag only after verification.

## 4. Full-file rule

Complete files are returned or created, not fragments.

Patches are used only when Minette explicitly requests them.

A complete-file delivery identifies:

- exact path
- purpose
- dependencies
- verification performed

## 5. No-assumption rule

Do not assume:

- a file exists
- a module is registered
- a database is disposable
- a test passed
- a backup succeeded
- a Git branch is clean
- a utility is missing merely because it is not visible

Inspect first.

## 6. Recovery communication

During recovery:

- keep instructions brief
- give one action at a time
- use one-line commands where possible
- state when to stop
- do not move ahead until the previous result is known
- keep the recovery checklist visible

## 7. Review gate

Before reporting a change complete, reject it yourself if it:

- changes unrelated architecture
- removes working UI elements
- introduces placeholders
- rewrites modules unnecessarily
- modifies the live database without explicit authorisation and a
  verified backup
- hard-codes temporary paths
- claims unrun tests
- omits complete files
- violates the requested scope

## 8. Approval gate

No change is considered complete until:

- syntax checks pass
- imports pass
- FC Hub launches
- affected utility opens
- visible behaviour is confirmed
- database safety is confirmed
- Git status is reviewed
