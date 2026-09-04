# Session & project docs

Living notes for what was implemented, how GitHub is set up, and what to do next.

**Next work (global):** [`docs/next-work.md`](../next-work.md) — the living queue. Kept as-is across branch merges; do not recreate `03-next-work.md` here.

| Doc | Description |
|-----|-------------|
| [00-session-m0-bootstrap.md](00-session-m0-bootstrap.md) | **First execute session** — everything done to bootstrap M0 |
| [01-github-setup.md](01-github-setup.md) | Labels, milestones, issues, board, CI state |
| [02-codebase-map.md](02-codebase-map.md) | Module map of the scaffold |
| [04-session-chroma-client.md](04-session-chroma-client.md) | **M1 #13** — persistent Chroma client |
| [05-session-alembic.md](05-session-alembic.md) | **M1 #11** — first Alembic revision |
| [06-session-ingest.md](06-session-ingest.md) | **M1 #16** — ingest pipeline, extractors, inbox watcher |
| [07-session-embedder-llm.md](07-session-embedder-llm.md) | **M1 #14 / #15** — MiniLM path + LLM health in `/status` |
| [08-session-rag.md](08-session-rag.md) | **M1 #17** — retrieve-only + sourced RAG with citations |
| [09-session-telegram-bot.md](09-session-telegram-bot.md) | **M1 #18 / #19** — Telegram query, capture, pause/digest/status |
| [10-session-hitl-review.md](10-session-hitl-review.md) | **M1 #20** — HITL review queue + `/review` buttons |
| [11-session-api-harden.md](11-session-api-harden.md) | **M1 #21** — loopback API + token auth |
| [12-session-write-queue.md](12-session-write-queue.md) | **M1 #12** — WAL + concurrent ingest write queue |
| [13-session-integration-tests.md](13-session-integration-tests.md) | **M1 #22** — ingest → retrieve → review integration tests |
| [14-session-export-wipe.md](14-session-export-wipe.md) | **M1 #23** — `juno export` + `juno wipe` |
| [15-session-v1-release-gate.md](15-session-v1-release-gate.md) | **M1 #24** — v1.0 release gate |
| [16-session-spike-s1-live.md](16-session-spike-s1-live.md) | **#4** — Live Spike S1 (shared-loop smoke) |
| [17-session-projects-board.md](17-session-projects-board.md) | **#9** — Projects v2 board + auto-add |
| [18-session-before-m2-ops.md](18-session-before-m2-ops.md) | Before M2 — branch protection + M1 close |
| [19-session-spike-s2.md](19-session-spike-s2.md) | **#44** — Spike S2 browser → /ingest |
| [20-session-mv3-scaffold.md](20-session-mv3-scaffold.md) | **#45** — MV3 scaffold |
| [21-session-browser-timestamp.md](21-session-browser-timestamp.md) | **#46** — URL + title + timestamp |
| [22-session-engagement-metrics.md](22-session-engagement-metrics.md) | **#47** — Engagement metrics |
| [23-session-highlights.md](23-session-highlights.md) | **#48** — Highlights / selections |
| [24-session-domain-excludes.md](24-session-domain-excludes.md) | **#49** — Domain excludes + pause |
| [25-session-module-health.md](25-session-module-health.md) | **#50** — Extension module health |
| [26-session-cross-reference.md](26-session-cross-reference.md) | **#51** — Cross-reference browser vs inbox |
| [27-session-digest-enrichment.md](27-session-digest-enrichment.md) | **#52** — Digest enrichment (browser vs uploads) |
| [28-session-m2-gate.md](28-session-m2-gate.md) | **#53** — M2 gate + extension validation |
| [29-session-spike-s3.md](29-session-spike-s3.md) | **#64** — Spike S3 Cursor vscdb → /ingest |
| [30-session-ide-scaffold.md](30-session-ide-scaffold.md) | **#65** — IDE adapter scaffold |
| [31-session-ide-chat.md](31-session-ide-chat.md) | **#66** — Chat/composer ingest |
| [32-session-ide-errors.md](32-session-ide-errors.md) | **#67** — Terminal error capture |
| [33-session-ide-hitl.md](33-session-ide-hitl.md) | **#68** — HITL IDE error-match / batches |
| [34-session-error-match.md](34-session-error-match.md) | **#69** — Error-matching retrieval |
| [35-session-ide-crossref.md](35-session-ide-crossref.md) | **#70** — Cross-reference IDE vs browser + inbox |
| [36-session-ide-digest.md](36-session-ide-digest.md) | **#71** — Digest enrichment for IDE |
| [37-session-ide-health.md](37-session-ide-health.md) | **#72** — IDE module health |
| [38-session-m3-gate.md](38-session-m3-gate.md) | **#73** — M3 gate + v1.2 |
| [39-session-spike-s4.md](39-session-spike-s4.md) | **#86** — Spike S4 APScheduler shared-loop smoke |
| [v1.0-release-gate.md](../v1.0-release-gate.md) | M1 checklist (all P0 closed) |
| [v1.1-release-gate.md](../v1.1-release-gate.md) | M2 checklist (browser capture) |
| [v1.2-release-gate.md](../v1.2-release-gate.md) | M3 checklist (IDE capture) |

Architecture decisions live in [`../adr/`](../adr/). Product requirements: [`../../personal-knowledge-graph-prd.md](../../personal-knowledge-graph-prd.md).
