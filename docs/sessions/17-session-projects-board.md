# Session 17 — Projects v2 board (#9)

**Date:** 2026-08-29  
**Issue:** [#9](https://github.com/Anna-Hax/JUNO/issues/9) — Projects v2 board + auto-add workflow  
**Branch:** `chore/projects-board-9`

## What changed

- Confirmed **[JUNO Roadmap](https://github.com/users/Anna-Hax/projects/1)** (project **#1**) already held open/closed M0–M5 issues with Status **Todo / In Progress / Done**.
- Made `scripts/bootstrap-project.ps1` **idempotent** (parse `gh project list` JSON `.projects`, reuse open “JUNO Roadmap”, do not create duplicates). Closed/deleted an accidental project #2 created during the first buggy run.
- Set repo secrets **`PROJECT_NUMBER=1`** and **`PROJECT_PAT`** (token with `project` scope) so `.github/workflows/project-automation.yml` can auto-add new issues/PRs.
- Updated `docs/sessions/01-github-setup.md` + `docs/next-work.md`.

## Acceptance

| Check | Result |
|-------|--------|
| Open issues on board | Yes (#9, #25–#28 + historical M1 items) |
| Bootstrap script safe to re-run | Yes — reuses #1 |
| Auto-add secrets | `PROJECT_PAT` + `PROJECT_NUMBER` set |

Optional UI polish (not blocking): rename/expand Status options to Backlog / Ready / In Review / Blocked in the project UI.

## Note on `PROJECT_PAT`

Bootstrap used the current `gh auth` token. If Actions add-to-project starts failing after re-auth, replace the secret with a classic PAT that has **project** (and repo) scope.

## How to verify

```powershell
gh project list --owner Anna-Hax
.\scripts\bootstrap-project.ps1   # should print Reusing project #1
gh secret list --repo Anna-Hax/JUNO   # PROJECT_PAT, PROJECT_NUMBER present
```

Open a throwaway issue or PR and confirm the Project Automation workflow adds it to project #1.

## Links

| Doc | Role |
|-----|------|
| [01-github-setup.md](01-github-setup.md) | Board + secrets |
| [next-work.md](../next-work.md) | Global board |
| [16-session-spike-s1-live.md](16-session-spike-s1-live.md) | Prior Before-M2 item |
