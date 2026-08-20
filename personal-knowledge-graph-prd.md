# PRD: Personal Knowledge Graph Agent

**Status:** Draft v1

**Owner:** You

**Last updated:** August 13, 2026

---

## 1. Summary

A personal agentic system that passively captures what you read, code, and discuss across your browser, IDE, phone, and curated document uploads — and unifies it into a queryable, proactive "second brain." Primary interaction surface is a **Telegram bot**, so the agent is always one message away regardless of which device you're on.

## 2. Problem Statement

Right now your learning and work trail is scattered across:

- Browser tabs and history (no memory of *why* you read something or how it connects to anything else)
- Cursor/IDE chats (valuable problem-solving history that's locked in a session and never resurfaces)
- Slack discussions in your tech club (easy to miss, hard to search later)
- Mobile study/reading activity (completely disconnected from desktop context)

There is no single place that remembers, connects, and resurfaces this information when it's actually useful.

## 3. Goals

- Passively capture activity across browser, IDE, and mobile with minimal manual effort
- Let a curated set of docs/links (from Slack, manually gathered) be ingested into the same graph
- Connect entities/topics across all sources (an article, a Cursor chat, a Slack doc, a phone note about "Rust ownership" should all resolve to one node)
- Support both **pull** (you ask a question) and **push** (agent proactively resurfaces relevant things) interactions
- Make Telegram the universal interface — chat with the agent from anywhere

## 4. Non-Goals (for v1)

- Real-time multi-user / team knowledge graph (this is single-user, personal)
- Full mobile OS-level activity monitoring (starts with a manual upload/sync space, not deep OS hooks)
- Automatic Slack workspace integration (see §6.3 — intentionally decoupled)
- Building a general-purpose note-taking app — this augments existing tools, doesn't replace them

## 5. Users & Core Use Cases

Single user (you). Representative queries the system should be able to answer or act on:

- "What was I reading about distributed systems last week?"
- "Have I hit this error before?"
- "Anything relevant in Slack to what I'm reading right now?"
- "Summarize what I learned this month about X"
- "Remind me what I was building before I got distracted"
- (Proactive) "You've read 3 articles on vector databases this week — want a synthesis?"
- (Proactive, via Telegram) morning digest of what's queued up / relevant today

---

## 6. Feature Modules

### 6.1 Browser Monitoring

**Capture (P0)**

- URL, title, timestamp, active time on page, scroll depth
- Text highlights/selections
- Referring search query (what you searched to land here)

**Capture (P1)**

- Tab session clustering (which tabs were open together → implies a "research session")
- Bookmarks/reading-list items

**Retrieval & Reasoning (P0)**

- Semantic search: "what was I reading about X" over history + highlights, not just keyword match
- Weekly/daily reading digest

**Retrieval & Reasoning (P1)**

- Resurfacing unfinished reads ("opened, low scroll depth, never revisited")
- Duplicate-read detection — warn before reopening something already fully read
- Rabbit-hole detection — reconstruct a session's path (A → B → C) as a mini narrative

**Retrieval & Reasoning (P2)**

- Auto-flashcard/spaced-repetition generation from highlights
- Topic decay tracking — resurface old deep-dives before they're fully forgotten

---

### 6.2 IDE Monitoring (Cursor-first)

**Capture (P0)**

- Cursor chat history via an existing open-source exporter that reads Cursor's local chat/composer data directly (e.g. `cursor-chat-export`, `cursor-history`, or similar SQLite-based tools) rather than any official API — Cursor stores chats locally in `state.vscdb` SQLite files per workspace, and several actively maintained open-source projects already parse and export from these (chat/composer sessions, searchable, exportable to Markdown/JSON). Wrap one of these as the ingestion source instead of building a custom exporter from scratch
- Terminal errors encountered
- File/project touched, commit messages

**Capture (P1)**

- Idle-then-burst time patterns (proxy for "was stuck, then solved it")
- Dependency/library versions in use per project

**Retrieval & Reasoning (P0)**

- "Have I seen this error before?" — semantic match against past chats/errors across all projects
- Cross-project pattern surfacing ("you solved something similar in Project A")

**Retrieval & Reasoning (P1)**

- Auto-drafted dev journal / weekly changelog from commits + chat context
- Link IDE errors to related browser history ("you read a GitHub issue about this 2 days ago") and to synced Slack docs

**Retrieval & Reasoning (P2)**

- Skill-gap detection — recurring struggle with a concept flagged over time, resources suggested
- Auto-drafted README/doc generation from session history

---

### 6.3 Curated Docs / "Slack" Ingestion — via Upload Space, Not Direct Connection

Per your note: instead of a live Slack integration, this is a **manual sync space** — a folder/inbox (could literally be a Telegram channel, a watched folder, or a simple web upload) where you drop:

- Docs shared in your tech club Slack
- Links you want tracked
- Notes/screenshots from any discussion

**Capture (P0)**

- Ingest whatever's dropped into the space: files, pasted links, text
- Extract text (PDF/doc parsing), tag by topic, timestamp of upload

**Retrieval & Reasoning (P0)**

- Cross-reference: while reading an article or hitting an IDE error, check if anything in this space is related
- Reverse lookup: "what's in my upload space about X"

**Why decoupled:** No OAuth/bot-in-workspace complexity, no risk of over-scoped access to a shared space, and you stay in full control of what enters your personal graph. Can always upgrade to a live integration later if the manual step becomes friction.

**Extension (P2)**

- If later desired: a lightweight Slack app that *you* trigger (e.g. a slash command or emoji reaction) to forward a specific message into the upload space — still opt-in per item, not a full passive listener.

---

### 6.4 Mobile Connect

Given sensitivity, mobile starts scoped rather than full OS-level monitoring.

**Capture (P0)**

- A manual/semi-automatic sync space (mirrors §6.3) for: articles read on phone, notes app exports, voice memos
- Telegram itself doubles as the mobile capture surface — forward things to the bot directly

**Capture (P1)**

- Study app integrations where APIs/export exist (e.g. read-later apps, Kindle highlights export)
- Voice memo → transcription → structured note pipeline

**Capture (P2 — needs explicit privacy scoping first)**

- Selective chat export from specific study/tech-focused threads only (never blanket chat access)

**Retrieval & Reasoning (P0)**

- Unified timeline across phone + desktop activity
- Continuity: something queued on phone shows up as "waiting for you" on desktop context

**Retrieval & Reasoning (P1)**

- Idea capture — dictate a stray thought, agent tags and resurfaces it later when contextually relevant (e.g. while coding the related project)

**Reliability (P0)**

- **Offline capture queue**: phone captures (forwards, notes, voice memos) are queued locally on-device when there's no connectivity, and sync automatically once back online — mobile connectivity won't always be there, so capture shouldn't silently fail or be lost while offline

---

### 6.5 Telegram Bot — Primary Interface

This is the hub, not an afterthought.

**Core (P0)**

- Chat interface to query the knowledge graph in natural language
- Forward-to-bot as a universal capture method (link, doc, voice note, photo — all get ingested)
- On-demand digest command ("/digest today", "/digest week")

**Core (P1)**

- Proactive push messages: daily/weekly digest sent automatically, contextual resurfacing ("this came up again — here's what you know")
- Inline actions: "save this," "what do I know about this," "remind me about this in 3 days"

**Core (P2)**

- Voice message in → transcribed → answered
- Multi-turn conversational memory within Telegram itself (agent remembers the chat thread context, not just the graph)

---

## 7. Unifying Layer — The Knowledge Graph

This is what turns four loggers into one system.

- **Entity/topic linking**: same concept across browser, IDE, uploads, and mobile resolves to one graph node with pointers to every source instance
- **Temporal reasoning**: track how your understanding of a topic evolved over time, not just latest state
- **Source provenance**: every fact/node keeps a link back to where it came from (article, chat, doc, phone note) so answers are traceable
- **Proactive layer**: scheduled jobs that scan for resurfacing-worthy items and push them via Telegram
- **Unified search**: one semantic search across everything, replacing the need to separately search browser history / Slack / notes / chats

---

## 8. Human-in-the-Loop (HITL) Layer

An agent this autonomous needs deliberate checkpoints where you stay in control — both for trust and for graph quality, since bad auto-merges or false cross-references compound over time. HITL is a cross-cutting layer, not a single module: it governs how confidently the agent is allowed to act versus when it must ask first.

**Where the agent should pause and ask, not just act (P0)**

- **Entity resolution / merging**: when the agent decides two items (an article, a Cursor chat, a Slack doc) are "the same topic," that merge is proposed and confirmed, not auto-applied — at least until confidence for that topic cluster is established
- **Cross-referencing suggestions**: low-confidence "this might be related" matches surface as a yes/no suggestion rather than being silently woven into the graph as fact
- **Sensitive ingestion (mobile chats especially)**: any chat export or phone content requires explicit per-batch review/approval before entering the graph — never a blanket "sync everything" toggle
- **Destructive or irreversible actions**: pruning, deleting nodes, archiving a project as "done" always require confirmation first

**Where the agent should pause and ask, not just act (P1)**

- **Auto-generated artifacts**: dev journals, README drafts, flashcards, digests land in a draft/review state — you skim, edit, approve, rather than the agent auto-publishing
- **IDE error-matching**: before reusing an old solution as canonical, you confirm it's actually the same root cause, not just a similar-looking stack trace

**Mechanism: a review queue, with Telegram as the approval surface (P0)**

- New nodes/edges/merges land in a `pending` state with a confidence score
- High-confidence, low-risk items (e.g. logging that a URL was read) commit automatically
- Low-confidence or high-impact items (merges, sensitive ingestion, deletions) sit in a queue instead
- Telegram doubles as the review interface — inline buttons (✅ / ❌ / edit) on digest messages, so approving something is a one-tap action rather than a context switch to a separate dashboard

**The feedback loop this creates (P1)**

- Every accept/reject/edit is itself a data point
- Auto-merge confidence thresholds tune themselves per topic over time
- The agent learns which kinds of cross-references are actually useful versus noisy
- Auto-drafted content improves toward your voice based on repeated edits

**Trust dial (P2)**

- Early on, most actions route through you for approval
- As the agent earns confidence in a specific category (e.g. "browser → digest" proves reliable after a month), that category's gate can loosen while tighter categories — mobile chat ingestion especially — stay gated indefinitely
- This should be an explicit, per-category setting you control, not a global switch

**Transparency in answers (P0)**

- **Confidence-scored answers with inline sources**: every proactive or pull answer shows which graph nodes it drew from and how confident it is, so you can catch a hallucinated or weak-evidence answer instead of trusting it blindly — this is HITL applied to retrieval, not just to ingestion

---

## 9. Non-Functional Requirements

- **Privacy-first by design**: everything stored locally or in a storage you control; no third-party analytics on captured content
- **Selective capture**: ability to pause/exclude specific apps, sites, or projects (e.g. don't log banking sites, personal chats)
- **Focus/pause mode**: a single Telegram command (e.g. `/pause`) that fully suspends all capture across every module for sensitive work — a fast, universal override on top of the persistent per-domain/per-app excludes above
- **Capture health monitoring**: a status view (e.g. `/status` in Telegram) showing per-module sync health — "browser extension: last synced 2h ago," "IDE hook: last synced 3 days ago (broken?)" — so silent breakage in these fragile integrations is caught quickly instead of discovered as a gap in the graph weeks later
- **Offline resilience**: mobile capture must queue locally and sync when connectivity returns, so a dead zone or airplane mode never means lost data
- **Data ownership**: full export/delete capability at any time
- **Latency**: retrieval queries should feel conversational (seconds, not minutes)
- **Extensibility**: each capture module (browser/IDE/mobile/uploads) should plug into the same graph schema so new sources can be added later without a redesign

---

## 10. Rough Phased Roadmap

**Phase 1 — Foundation**

- Telegram bot skeleton (chat + forward-to-capture)
- Upload space (manual doc/link ingestion) — covers both §6.3 and initial §6.4
- Basic knowledge graph schema + semantic search over ingested content
- Review queue + `/pause` + `/status` — HITL and reliability basics built in from the start, not bolted on later

**Phase 2 — Browser**

- Browser extension for capture (URL, time, highlights)
- Cross-reference against upload space content
- Daily/weekly digest via Telegram

**Phase 3 — IDE**

- Cursor chat + terminal error capture
- Error-matching retrieval
- Cross-linking with browser + upload space

**Phase 4 — Proactive Layer + Mobile Depth**

- Scheduled resurfacing/push notifications
- Deeper mobile capture (voice memos, read-later app integrations)
- Temporal reasoning ("how has my understanding of X evolved")

**Phase 5 — Polish & Extensions**

- Flashcards/spaced repetition
- Auto-generated dev journal / doc drafts
- Skill-gap tracking
- Optional lightweight Slack forwarding trigger

---

## 11. Open Questions

- Where does the graph/data actually live — self-hosted server, local-first with sync, or cloud? (affects mobile access design)
- Browser capture: custom extension vs. existing history/bookmark APIs to start lighter?
- Which open-source Cursor chat exporter to standardize on (evaluate `cursor-chat-export`, `cursor-history`, `cursor-session` for maintenance activity, format support, and stability across Cursor version updates) — and how to handle breakage if Cursor changes its internal storage schema
- What's the retention/pruning policy — keep everything forever, or age out low-value data?
- Voice memo transcription: on-device vs. API-based (cost/privacy trade-off)?

---

## 12. Success Metrics (informal, personal-project scale)

- You actually use the Telegram bot daily without it feeling like a chore
- At least weekly, the agent surfaces something you'd have otherwise forgotten or missed
- Time to find "that thing I read/built/discussed a while back" drops meaningfully vs. manual search today
