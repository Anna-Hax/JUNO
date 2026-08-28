# GitHub setup — labels, milestones, issues, board, CI

**Last updated:** 2026-08-20  
**Remote:** https://github.com/Anna-Hax/JUNO

---

## Labels

Created under `type:`, `area:`, `priority:`, plus meta (`epic`, `blocked`, `needs-design`, `good first issue`).

Bootstrap script (bash): [`scripts/bootstrap-labels.sh`](../../scripts/bootstrap-labels.sh)  
(Actual creation in M0 was done via PowerShell/`gh` because bash PATH lacked `gh`.)

---

## Milestones

| Milestone | Target |
|-----------|--------|
| M0: Project Setup & CI | pre-v1 |
| M1: v1.0 Foundation | Telegram + ingest + graph + HITL |
| M2: v1.1 Browser Capture | Extension |
| M3: v1.2 IDE Capture | Cursor |
| M4: v1.3 Proactive & Mobile | Digests / voice / temporal |
| M5: v2.0 Polish & Extensions | Flashcards, drafts, trust dial |

Script: [`scripts/bootstrap-milestones.sh`](../../scripts/bootstrap-milestones.sh)

---

## Issues (wave policy)

- **Created now:** M0 + M1 concrete issues + one **epic** per M2–M5 (~28 issues).
- **Not created yet:** full ~85-ticket split backlog for M2+ (expand when milestone unlocks).
- Script: [`scripts/bootstrap-issues.sh`](../../scripts/bootstrap-issues.sh)

### M0 status after bootstrap session

| # | Title | State |
|---|-------|-------|
| 1–3, 5–8, 10 | Scaffold / CI / ADRs / README | **Closed** |
| 4 | Spike S1 live Telegram smoke | Open |
| 9 | Projects v2 board | Open |

### M1 open (examples)

#11 schema/Alembic · #12 write queue · #13 Chroma · #14 embedder · #15 LLM · #16 ingest · #17 RAG · #18–21 bot/HITL/API · #22–24 tests/export/release gate

Epics: #25 M2 · #26 M3 · #27 M4 · #28 M5

---

## Progress board (Projects v2)

**Status:** **live** — [JUNO Roadmap](https://github.com/users/Anna-Hax/projects/1) (project **#1**).

```powershell
gh auth refresh -h github.com -s project,read:project
.\scripts\bootstrap-project.ps1   # idempotent — reuses project #1
```

Status columns today: **Todo → In Progress → Done** (customize in the UI for Ready / Blocked / In Review if desired).

CI secrets for auto-add: `PROJECT_PAT`, `PROJECT_NUMBER=1` (see `.github/workflows/project-automation.yml`).

---

## CI

| Workflow | Trigger | Notes |
|----------|---------|-------|
| CI Python | push/PR to `main` | **Green** on first scaffold push |
| CI Extension | path `apps/extension/**` | JSON + file presence |
| PR Checks | PR open/edit | title format + Closes/Refs |
| Project Automation | issue/PR open | uses `PROJECT_PAT` + `PROJECT_NUMBER=1` |

PR template: `.github/PULL_REQUEST_TEMPLATE.md`

---

## Branch protection

Not enabled yet. Recommended after board exists: require PR + `CI Python` + `PR Checks` before merge to `main`.
