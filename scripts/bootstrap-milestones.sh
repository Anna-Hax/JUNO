#!/usr/bin/env bash
# Create milestones M0–M5 (idempotent-ish).
set -euo pipefail
REPO="${REPO:-Anna-Hax/JUNO}"

mk() {
  local title="$1" desc="$2"
  if gh api "repos/$REPO/milestones" --jq '.[].title' | grep -Fqx "$title"; then
    echo "exists: $title"
  else
    gh api "repos/$REPO/milestones" -f title="$title" -f description="$desc" >/dev/null
    echo "created: $title"
  fi
}

mk "M0: Project Setup & CI" "Scaffold, CI, board, ADRs"
mk "M1: v1.0 Foundation" "Telegram + ingest + graph + HITL"
mk "M2: v1.1 Browser Capture" "MV3 extension + digests"
mk "M3: v1.2 IDE Capture" "Cursor state.vscdb + error match"
mk "M4: v1.3 Proactive & Mobile" "Scheduled push + voice + temporal"
mk "M5: v2.0 Polish & Extensions" "Flashcards, drafts, trust dial"

echo "Milestones done for $REPO"
