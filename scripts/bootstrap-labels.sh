#!/usr/bin/env bash
# Bootstrap GitHub labels for Anna-Hax/JUNO (idempotent).
set -euo pipefail
REPO="${REPO:-Anna-Hax/JUNO}"

create() {
  local name="$1" color="$2" desc="${3:-}"
  if gh label list --repo "$REPO" --limit 200 | grep -Fqx "$name" 2>/dev/null; then
    echo "exists: $name"
  else
    gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" 2>/dev/null \
      || gh label edit "$name" --repo "$REPO" --color "$color" --description "$desc"
    echo "created: $name"
  fi
}

# Prefer create; ignore if exists
mk() {
  gh label create "$1" --repo "$REPO" --color "$2" --description "$3" 2>/dev/null || true
}

mk "type: feature" "1D76DB" "New capability"
mk "type: bug" "D73A4A" "Broken behavior"
mk "type: chore" "FBCA04" "Refactor, deps, tooling"
mk "type: docs" "0075CA" "Docs / ADRs"
mk "type: test" "5319E7" "Tests only"
mk "type: security" "B60205" "Privacy / auth / data"

mk "area: core" "C5DEF5" "Core runtime"
mk "area: bot" "BFDADC" "Telegram bot"
mk "area: graph" "D4C5F9" "Knowledge graph"
mk "area: ingest" "F9D0C4" "Ingestion"
mk "area: rag" "FEF2C0" "Retrieval / LLM"
mk "area: hitl" "E99695" "Human in the loop"
mk "area: api" "C2E0C6" "Local API"
mk "area: extension" "BFD4F2" "Browser extension"
mk "area: ide" "D1D5DA" "Cursor / IDE"
mk "area: jobs" "F9C513" "Scheduler"
mk "area: infra" "EDEDED" "Repo / tooling"
mk "area: ci" "0052CC" "CI / workflows"

mk "priority: P0" "B60205" "Blocks milestone"
mk "priority: P1" "FBCA04" "Important"
mk "priority: P2" "0E8A16" "Nice to have"

mk "good first issue" "7057FF" "Small starter"
mk "blocked" "000000" "Waiting on dependency"
mk "needs-design" "D4C5F9" "Open design question"
mk "epic" "3E4B9E" "Milestone epic"

echo "Labels done for $REPO"
