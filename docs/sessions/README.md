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

Architecture decisions live in [`../adr/`](../adr/). Product requirements: [`../../personal-knowledge-graph-prd.md`](../../personal-knowledge-graph-prd.md).
