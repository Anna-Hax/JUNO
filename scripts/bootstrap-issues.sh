#!/usr/bin/env bash
# Create M0+M1 concrete issues + M2–M5 epics (wave policy).
set -euo pipefail
REPO="${REPO:-Anna-Hax/JUNO}"

milestone_number() {
  local title="$1"
  gh api "repos/$REPO/milestones" --jq ".[] | select(.title==\"$title\") | .number"
}

M0=$(milestone_number "M0: Project Setup & CI")
M1=$(milestone_number "M1: v1.0 Foundation")
M2=$(milestone_number "M2: v1.1 Browser Capture")
M3=$(milestone_number "M3: v1.2 IDE Capture")
M4=$(milestone_number "M4: v1.3 Proactive & Mobile")
M5=$(milestone_number "M5: v2.0 Polish & Extensions")

issue() {
  local title="$1" body="$2" milestone="$3"
  shift 3
  local labels=("$@")
  local args=(--repo "$REPO" --title "$title" --body "$body" --milestone "$milestone")
  local l
  for l in "${labels[@]}"; do
    args+=(--label "$l")
  done
  gh issue create "${args[@]}"
}

# --- M0 ---
issue "Bootstrap uv project: pyproject, ruff, pytest, empty package" "Acceptance: \`uv run pytest\` green" "$M0" "type: chore" "area: core" "area: ci" "priority: P0"
issue "Repo layout + gitignore (inbox/, data/, .env)" "Acceptance: matches plan tree" "$M0" "type: chore" "area: infra" "priority: P0"
issue ".env.example + README (BotFather, Ollama, PC-off limits)" "Acceptance: honest local-first docs" "$M0" "type: docs" "area: infra" "priority: P0"
issue "Spike S1: PTB + uvicorn shared event-loop hello-world" "Acceptance: both respond without second-loop crash. See ADR-01." "$M0" "type: chore" "area: bot" "area: api" "priority: P0"
issue "ADR-01..03 stubs (event loop, SQLite writes, Alembic)" "Acceptance: docs/adr merged" "$M0" "type: docs" "needs-design" "priority: P0"
issue "GitHub labels + milestones M0–M5" "Acceptance: labels + milestones exist" "$M0" "type: chore" "area: ci" "priority: P0"
issue "CI: ruff check/format + pytest (ubuntu + windows)" "Acceptance: PR blocked on failure" "$M0" "type: chore" "area: ci" "priority: P0"
issue "PR template + pr-checks workflow (title, Closes #)" "Acceptance: missing Closes # fails check" "$M0" "type: chore" "area: ci" "priority: P0"
issue "Projects v2 board + auto-add workflow" "Acceptance: new M0/M1 issues on board" "$M0" "type: chore" "area: ci" "priority: P0"
issue "Windows startup shortcut / runbook (keep Juno alive)" "Acceptance: documented in README" "$M0" "type: docs" "area: infra" "priority: P1"

# --- M1 (subset of highest P0 — full list in plan; keep bootstrap under ~25) ---
issue "Alembic + SQLite schema (captures, nodes, edges, chunks, review_items, module_health, settings)" "Acceptance: juno db-init works" "$M1" "type: feature" "area: graph" "priority: P0"
issue "Enable WAL + async write-queue for all DB writes" "Acceptance: concurrent ingest does not lock" "$M1" "type: feature" "area: core" "priority: P0"
issue "Chroma persistent client wrapper (collection per embedding model)" "Acceptance: persist across restart" "$M1" "type: feature" "area: graph" "priority: P0"
issue "Local embedder (MiniLM) + model id in settings + stub for CI" "Acceptance: batch embed; CI uses stub" "$M1" "type: feature" "area: rag" "priority: P0"
issue "Chat LLM adapter: Ollama + OpenAI-compat + health probe" "Acceptance: .env switches provider; offline fallback" "$M1" "type: feature" "area: rag" "priority: P0"
issue "Ingest pipeline + extractors (txt/md/pdf/url) + inbox watcher" "Acceptance: drop file → capture; bad PDF → failed" "$M1" "type: feature" "area: ingest" "priority: P0"
issue "Retrieve-only + RAG sourced answers with confidence" "Acceptance: citations required" "$M1" "type: feature" "area: rag" "priority: P0"
issue "Telegram allowlist + /start /help + text query" "Acceptance: strangers ignored; bot replies" "$M1" "type: feature" "area: bot" "area: security" "priority: P0"
issue "Telegram forward-to-capture + /digest /pause /resume /status" "Acceptance: pause stops ingest" "$M1" "type: feature" "area: bot" "area: hitl" "priority: P0"
issue "HITL review_items + /review inline Approve/Reject/Skip" "Acceptance: merge needs tap" "$M1" "type: feature" "area: hitl" "area: bot" "priority: P0"
issue "FastAPI loopback /health /status /ingest /search + token auth" "Acceptance: bad token 401" "$M1" "type: feature" "area: api" "area: security" "priority: P0"
issue "Integration tests ingest → retrieve → review (mocked LLM)" "Acceptance: CI happy path" "$M1" "type: test" "area: core" "priority: P1"
issue "CLI juno export + juno wipe" "Acceptance: full export" "$M1" "type: feature" "area: core" "area: security" "priority: P1"
issue "v1.0 release gate checklist" "Acceptance: all M1 P0 closed" "$M1" "type: chore" "area: infra" "priority: P0"

# --- Epics M2–M5 ---
issue "Epic: M2 Browser capture (v1.1)" "Expand when M1 closes. Spike S2, MV3 scaffold, URL/title, metrics, highlights, excludes, digests." "$M2" "epic" "type: feature" "area: extension" "priority: P0"
issue "Epic: M3 IDE / Cursor capture (v1.2)" "Expand when M2 closes. Spike S3, adapter, metadata then bubbles, error match, HITL." "$M3" "epic" "type: feature" "area: ide" "priority: P0"
issue "Epic: M4 Proactive + mobile depth (v1.3)" "Scheduler, morning digest, temporal queries, voice, PC-off status." "$M4" "epic" "type: feature" "area: jobs" "priority: P0"
issue "Epic: M5 v2.0 polish" "Flashcards, drafts, skill-gap, trust dial, Slack forward, prune, release gate." "$M5" "epic" "type: feature" "area: core" "priority: P0"

echo "Issues created for $REPO"
