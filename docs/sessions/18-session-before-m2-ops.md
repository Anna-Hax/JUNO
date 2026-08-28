# Session 18 — Before M2 ops (branch protection + M1 close)

**Date:** 2026-08-29  
**Branch:** `chore/before-m2-ops`

## What changed

- Applied **`main` branch protection** via GitHub API (documented in `scripts/branch-protection-main.json`):
  - Required checks: `lint-test (ubuntu-latest)`, `lint-test (windows-latest)`, `pr-hygiene`
  - PR required (0 approving reviews — solo maintainer)
  - No force-push / delete on `main`
- Closed milestone **[M1: v1.0 Foundation](https://github.com/Anna-Hax/JUNO/milestone/7)** (0 open issues, 14 closed).
- Updated `docs/next-work.md`, `docs/sessions/01-github-setup.md`, `docs/v1.0-release-gate.md`.

## How to re-apply branch protection

```powershell
gh api repos/Anna-Hax/JUNO/branches/main/protection -X PUT --input scripts/branch-protection-main.json
gh api repos/Anna-Hax/JUNO/branches/main/protection
```

## Verify

- Settings → Branches → `main` shows required status checks.
- Direct push to `main` should be rejected (use PRs).
- M1 milestone shows **Closed**.

## Links

| Doc | Role |
|-----|------|
| [next-work.md](../next-work.md) | Before-M2 queue |
| [01-github-setup.md](01-github-setup.md) | Board + protection |
