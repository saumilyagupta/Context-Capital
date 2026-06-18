# Design Spec — Context Capital Phase-1 Build Pack

**Date:** 2026-06-18
**Author:** Brainstormed via `superpowers:brainstorming` (Claude Code session)
**Status:** Approved by user (2026-06-18); doc-writing deferred to a future session
**Supersedes:** None
**Parent product docs:** `../../intial-praposal.md`, `../../proposal-v2.md`, `../../market-research.md`

---

## 0. Purpose of This Spec

Produce an engineering-grade documentation pack for **Phase 1 of Context Capital** (per `proposal-v2.md` §8), sufficient for an internal engineering team to build the MVP from scratch in ~6 months.

This document is the *spec of specs*: it locks down what each doc covers, who reads it, what stack it commits to, and in what order it gets written. It does **not** contain the doc contents themselves — those are produced in a follow-on session.

## 1. Goals and Non-Goals

### Goals
- A complete, internally-consistent doc set that lets an engineering team build the Phase-1 MVP without further design meetings.
- An open `context-protocol-v0.1.md` spec inside the pack that doubles as the public RFC-style artifact if/when published externally.
- Every load-bearing decision captured in an ADR.
- A threat model that addresses the prompt-injection-via-import attack class (the headline differentiator from `proposal-v2.md` §4.1).

### Non-Goals
- Phase 2 (prosumer SaaS / all-vendor coverage / knowledge graph reasoning) and Phase 3 (enterprise / SOC2 / on-prem) docs. Those get their own design pass.
- Investor-facing pitch material, marketing copy, or partnership decks.
- Code, CI configuration, or live deployments — only documentation.
- Compliance audit deliverables (SOC2 evidence packs, HIPAA BAAs). The threat model is engineering-grade only.

### Out-of-Scope for Phase 1 (consistent with proposal-v2 §8)
- Gemini, Copilot, Cursor capture (Phase 2).
- Hosted multi-tenant backend (Phase 2).
- Conflict-resolution UI (specified in spec doc but UI deferred to Phase 2).
- On-prem deployment, audit log export, dedicated compliance team (Phase 3).
- AAIF submission (Phase 4).

## 2. Audience

Primary: an internal engineering team of ~3–6 people (engineering lead + 2–3 engineers + 1 security engineer + design/PM as needed) who will build and ship the Phase-1 reference client.

Secondary: external implementors of Context Protocol v0.1 who will read only the open spec doc and the conformance suite.

Tertiary: future-self resuming this project after a gap — the spec must be readable cold.

## 3. Phase-1 Scope (Locked)

From `proposal-v2.md` §8 Phase 1:

> Open spec + reference client (months 0–6). Publish Context Protocol v0.1 spec under Apache 2.0. Open-source a reference client (Chrome extension + MCP server) that captures from ChatGPT and Claude. Free for individuals.

Components in scope:

1. **Context Protocol v0.1 schema** (the noun)
2. **Capture layer** — Chrome MV3 extension + ingestion of official ChatGPT and Claude chat-export files
3. **Memory extraction engine** — LLM-driven extraction of memories with confidence scoring and source provenance
4. **Storage layer** — local-first (Postgres or SQLite) with user-held encryption
5. **MCP server** — exposes context export/import + memory queries to compatible MCP clients (Claude Desktop, future others)
6. **Permissions and audit** — per-AI scopes, basic audit log
7. **Prompt-injection sanitization on import** — `proposal-v2.md` §4.1 attack-surface mitigation
8. **Vendor provenance tagging** — `proposal-v2.md` §4.4

## 4. The Doc Bundle (10 Documents)

| # | Doc | Path | Length | Audience | Status field |
|---|---|---|---|---|---|
| 1 | SRS | `docs/srs.md` | ~10pp | Eng team | `Draft` → `Approved` |
| 2 | SDD | `docs/sdd.md` | ~15pp | Eng team | `Draft` → `Approved` |
| 3 | Context Protocol v0.1 spec | `docs/spec/context-protocol-v0.1.md` | ~10pp | Eng + external | `Draft` → `v0.1.0` |
| 4 | API spec | `docs/api/openapi.yaml` + `docs/api/README.md` | ~5pp + YAML | Eng + integrators | `Draft` → `Approved` |
| 5 | Data model | `docs/data-model.md` + `docs/data-model/schema.sql` | ~7pp + SQL | Eng | `Draft` → `Approved` |
| 6 | Threat model | `docs/security/threat-model.md` | ~10pp | Eng + security | `Draft` → `Approved` |
| 7 | Conformance suite | `docs/spec/conformance-suite.md` | ~5pp | External implementors | `Draft` → `v0.1.0` |
| 8 | Test plan | `docs/testing/test-plan.md` | ~7pp | Eng + QA | `Draft` → `Approved` |
| 9 | Deployment runbook | `docs/ops/runbook.md` | ~5pp | Eng + on-call | `Draft` → `Approved` |
| 10 | ADRs | `docs/adr/000-template.md` + `001-…` through `008-…` | 1–2pp each | Eng | `Accepted` per ADR |

All paths are relative to `/Users/shyamal/Desktop/code/token-capital/`.

## 5. Per-Doc Outlines

The future-writer should produce each document with these section headings, at minimum, in order.

### 5.1 SRS (`docs/srs.md`)
1. Introduction (purpose, scope, definitions)
2. Overall description (product perspective, user classes, operating environment, constraints, assumptions)
3. System features
   - F-1 Capture from ChatGPT export
   - F-2 Capture from Claude export
   - F-3 Memory extraction (LLM-driven, confidence-scored)
   - F-4 Encrypted local storage
   - F-5 Context Protocol v0.1 export
   - F-6 Context Protocol v0.1 import (with sanitization)
   - F-7 MCP server tool/resource surfaces
   - F-8 Per-AI permission scopes
   - F-9 Audit log
4. External interface requirements (UI, hardware, software, communication)
5. Non-functional requirements
   - Security (encryption at rest, key handling, sanitization)
   - Privacy (data minimization, deletion guarantees)
   - Performance (extraction throughput, query latency targets)
   - Reliability (crash recovery, data integrity)
   - Portability (macOS / Windows / Linux for ext + server)
   - Maintainability (test coverage targets)
   - Localization (English only for Phase 1)
6. Constraints (browser MV3, MCP transport, no scraping of unauthorized accounts)
7. Success metrics (DoD-style: e.g., capture+extract+export round-trip succeeds on N real ChatGPT/Claude exports)
8. Out-of-scope (explicit list — Phase 2/3 items)

### 5.2 SDD (`docs/sdd.md`)
1. Architecture overview (the 9-layer diagram from `proposal-v2.md` §4, refined)
2. Component design
   - 2.1 Chrome extension (MV3, background service worker, content scripts, options page)
   - 2.2 Ingestion pipeline (export-file parsers for ChatGPT JSON, Claude JSON)
   - 2.3 Sanitization layer (prompt-injection scrub, provenance tagging)
   - 2.4 Memory extraction engine (LLM driver, prompt templates, confidence scoring)
   - 2.5 Storage layer (Postgres + pgvector, SQLite fallback)
   - 2.6 Crypto layer (age / libsodium, OS keystore wrapping)
   - 2.7 MCP server (tools, resources, prompt surfaces)
   - 2.8 Permissions and audit
3. Sequence diagrams (Mermaid)
   - Capture → extract → store
   - Export to context.json
   - Import context.json with sanitization
   - MCP client query → response
4. Data flow (capture sources → sanitization → extraction → storage → export)
5. Deployment topology (local single-user; staging optional)
6. Error and failure modes (failure table per component)
7. Observability (structured logs, metrics, no telemetry-by-default)

### 5.3 Context Protocol v0.1 Spec (`docs/spec/context-protocol-v0.1.md`)
1. Status (Draft v0.1.0)
2. Abstract
3. Terminology (RFC 2119)
4. Goals & non-goals
5. Data model
   - 5.1 Document envelope
   - 5.2 Subject
   - 5.3 Issuer
   - 5.4 Memory entries
   - 5.5 Provenance
   - 5.6 Validity (valid_from / valid_until / superseded_by)
   - 5.7 Sensitivity classifications
   - 5.8 Permissions
6. JSON Schema (2020-12, embedded or linked)
7. JSON-LD `@context` (linked)
8. Signing (Ed25519 detached signature; canonicalization rules)
9. Versioning (semver; v0.x = pre-stable; deprecation policy)
10. Conformance requirements summary (full suite in §5.7 doc)
11. Security considerations (prompt injection on import is normative)
12. Privacy considerations (sensitivity tags MUST be honored)
13. References (RFC 2119, RFC 8174, JSON Schema 2020-12, JSON-LD 1.1, RFC 8032 Ed25519)
14. Open questions / non-decisions

### 5.4 API spec (`docs/api/openapi.yaml` + `docs/api/README.md`)
**YAML** — OpenAPI 3.1 covering:
- `POST /v1/contexts` (create context from raw capture)
- `GET /v1/contexts/{id}` (fetch)
- `POST /v1/contexts/{id}/memories` (extract from raw payload)
- `GET /v1/contexts/{id}/memories` (list / filter)
- `POST /v1/contexts/{id}/export` (produce signed context.json)
- `POST /v1/contexts/import` (validate + sanitize + ingest)
- `GET /v1/audit-log` (paginated)
- Error envelope (RFC 7807 Problem Details)

**README narrative** — auth model (Phase 1: local-only loopback, no remote auth), error semantics, rate limits, idempotency, versioning policy, MCP tool/resource surface (separate from REST).

### 5.5 Data model (`docs/data-model.md` + `docs/data-model/schema.sql`)
**Narrative** — tables, relationships, indexing strategy, vector-search approach, retention/deletion semantics, migrations approach.

**Tables (provisional list, refine during write):**
- `subjects` — person/org identities
- `contexts` — document envelopes
- `memories` — individual memory rows (kind, predicate, object, confidence)
- `provenance` — per-memory source records
- `validity_periods` — temporal validity
- `permission_grants` — per-AI scopes
- `audit_log_entries` — all reads/writes/exports/imports
- `extraction_jobs` — async extraction state
- `vector_embeddings` — pgvector index for semantic recall

**ER diagram** — ASCII or Mermaid.

**`schema.sql`** — Postgres DDL with comments, pgvector setup, indexes, constraints.

### 5.6 Threat model (`docs/security/threat-model.md`)
1. Scope and trust boundaries
2. STRIDE walkthrough per component
   - Spoofing
   - Tampering
   - Repudiation
   - Information disclosure
   - Denial of service
   - Elevation of privilege
3. **Prompt-injection-via-import attack tree** (headline section)
   - Direct directive injection ("ignore previous instructions…")
   - Indirect injection via field values
   - Schema-level smuggling (oversized fields, unusual encodings)
   - Provenance spoofing
   - Mitigations: sanitization rules, sensitivity tags, untrusted-input markers
4. Supply-chain risks (browser ext malicious update, npm/pip dependency attacks)
5. Crypto threats (key extraction, downgrade, side channels)
6. Data exfiltration paths
7. Mitigations summary table
8. Residual risks and acceptance

### 5.7 Conformance suite (`docs/spec/conformance-suite.md`)
1. What conformance means (claim levels: import / export / round-trip / full)
2. Test categories
   - Schema validation tests
   - Signing/verification tests
   - Sanitization tests (must reject N classes of malicious payloads)
   - Provenance preservation tests
   - Versioning tests
   - Sensitivity-honoring tests
3. Reference test corpus (URLs to fixture files in the open-source repo)
4. How to run the suite (command, expected output, badge issuance)
5. Reporting non-compliance

### 5.8 Test plan (`docs/testing/test-plan.md`)
1. Testing philosophy (TDD-friendly; behavior-focused)
2. Test pyramid
   - Unit (coverage target 80%+)
   - Integration (per pipeline stage)
   - E2E (golden-path capture→extract→export→import→verify)
   - Conformance (against the v0.1 suite)
   - Performance (extraction throughput, query latency p50/p95)
   - Adversarial (prompt-injection corpus, malformed exports)
3. Tools (pytest, Playwright, Postman/Newman, locust or k6 for perf)
4. CI gates (must-pass list pre-merge; nightly extended)
5. Regression strategy
6. Acceptance criteria for Phase-1 ship

### 5.9 Deployment runbook (`docs/ops/runbook.md`)
1. Local dev (one-command bootstrap, prerequisites, troubleshooting)
2. Staging (Docker Compose; only for team testing, not external)
3. Production (Phase 1 ships local-only; runbook reserves prod section for Phase 2 but stubs it)
4. Secrets management (no secrets in repo; OS keystore for user; .env-template documented)
5. Observability (log locations, metrics endpoints if any)
6. On-call basics (Phase 1 is community-supported; no formal on-call yet)
7. Backup and recovery (user-driven; documented user export procedure)
8. Upgrade and migration procedure

### 5.10 ADRs (`docs/adr/`)
Files:
- `000-template.md` — MADR 3.0 template
- `001-capture-mode.md` — Chrome MV3 extension + official chat-export files
- `002-stack-and-language.md` — TypeScript + React + Vite (ext); Python 3.12 + FastAPI + `mcp` SDK (server)
- `003-storage.md` — Postgres 16 + pgvector + JSONB; SQLite fallback
- `004-encryption.md` — age + libsodium; Argon2id-derived master key; OS keystore wrapping
- `005-extraction-model.md` — `litellm`-fronted pluggable layer; default Claude API w/ prompt caching
- `006-mcp-transport.md` — Official Anthropic `mcp` Python SDK over stdio + Streamable HTTP
- `007-schema-format.md` — JSON Schema 2020-12 + JSON-LD `@context` + Ed25519 detached signature
- `008-conflict-resolution-policy.md` — Surface-only default; user-resolve mode for prosumer; last-write-wins explicitly off

## 6. Stack Decisions (Locked Day 1; Each Becomes an ADR)

| Layer | Decision | ADR | Notes |
|---|---|---|---|
| Capture | Chrome MV3 extension + official chat-export ingestion | ADR-001 | No unauthorized scraping |
| Extension stack | TypeScript + React + Vite + Manifest V3 | ADR-002 | |
| Server stack | Python 3.12 + FastAPI + asyncio + Anthropic `mcp` Python SDK | ADR-002 | |
| Database | Postgres 16 + pgvector + JSONB | ADR-003 | SQLite fallback for single-user/self-host |
| Encryption | age + libsodium; Argon2id master key; OS keystore wrap (Keychain / DPAPI / Secret Service) | ADR-004 | WebCrypto in-browser |
| Extraction LLM | `litellm` pluggable; default Anthropic Claude with prompt caching | ADR-005 | OpenAI + Ollama optional |
| MCP transport | Official `mcp` Python SDK; stdio + Streamable HTTP | ADR-006 | Per MCP 2026 roadmap |
| Schema format | JSON Schema 2020-12 + JSON-LD `@context` + Ed25519 detached signature | ADR-007 | |
| Conflict resolution | Surface-only default; user-resolve mode for prosumer | ADR-008 | Last-write-wins explicitly off |

## 7. Conventions

- **Markup:** GitHub-flavored Markdown for all docs.
- **Diagrams:** Mermaid blocks (renderable in GitHub/GitLab/VSCode); fall back to ASCII art when Mermaid can't express the layout.
- **ADR template:** MADR 3.0 (`Status / Context / Decision / Consequences / Alternatives considered`).
- **Spec keywords:** RFC 2119 / RFC 8174 (MUST / SHOULD / MAY) in `context-protocol-v0.1.md` and `conformance-suite.md`. Non-normative docs use plain prose.
- **Dates:** ISO 8601 (`YYYY-MM-DD`).
- **Code samples:** Fenced blocks with language hints (` ```python `, ` ```ts `, ` ```sql `, ` ```json `).
- **File naming:** `kebab-case.md` throughout.
- **Section numbering:** Heading-only; let renderers handle TOCs.
- **Cross-references:** Relative paths from doc location; never absolute paths.

## 8. Write Order and Dependencies

```
1. SRS                          (foundation; cited by all)
   ↓
2. Context Protocol v0.1 spec   (the noun; cited by SDD, data model, API, conformance)
   ↓
3. SDD                          (the verbs)
   ↓
4. Data model                   (concrete tables from SDD)
   ↓
5. API spec                     (interface to SDD; cites schema)
   ↓
6. Threat model                 (needs full architecture)
   ↓
7. Conformance suite            (needs spec finalized)
   ↓
8. Test plan                    (needs threat model + spec)
   ↓
9. Deployment runbook           (needs stack picks)
   ↓
10. ADRs                        (locked Day 1; each finalized when its decision is stable)
```

**Reading order for a new engineer:** SRS → SDD → ADRs → Context Protocol v0.1 → data model → API → threat model → test plan → runbook → conformance suite.

## 9. Definition of Done per Doc

Each doc is "Approved" when:

- All headings from §5 are present and non-empty.
- All cross-doc references resolve (no `TODO: link to X`).
- No `TBD` / `TODO` markers remain in the body (open questions move to a labeled `## Open Questions` section, which is permitted).
- The doc has been read end-to-end by a human reviewer who is not the writer.
- Code/schema/diagram fragments parse / render / validate (e.g., `openapi.yaml` passes `openapi-spec-validator`; `schema.sql` parses; Mermaid renders).

## 10. Resume Instructions (For the Future Doc-Writing Session)

The actual doc-writing was deferred for cost reasons. To resume:

1. Open a new Claude Code session in `/Users/shyamal/Desktop/code/token-capital`.
2. Confirm context loaded — the auto-memory file `~/.claude/projects/-Users-shyamal-Desktop-code-token-capital/memory/project_context_capital.md` should appear in session context.
3. Read this spec (`docs/superpowers/specs/2026-06-18-context-capital-build-pack-design.md`) end-to-end.
4. Invoke `superpowers:writing-plans` to produce an execution plan that fans out the 10 docs in the order from §8, with one Plan-skill `[Plan]` checkpoint per doc.
5. Execute the plan. Recommended pacing:
   - SRS, SDD, Context Protocol spec — 1 session each (high-stakes).
   - Data model, API spec, threat model — 1 session each.
   - Conformance suite, test plan, runbook, ADRs — bundle into 1–2 sessions.
6. Each doc must pass §9 Definition of Done before the next is started.

Alternative resume modes:
- **Single long session** (~$30–40): all 10 docs in one shot. Risk: context exhaustion, lower per-doc quality.
- **Cron / scheduled agent** (`schedule` skill): one doc per scheduled run, low daily cost.
- **GAN loop** (`gan-build` skill): generator/evaluator on the spec doc to maximize quality.

## 11. Open Questions / Explicit Non-Decisions

These are deliberately deferred to the doc-writing session or to a Phase 2 brainstorm:

1. **DID method.** `proposal-v2.md` §5 uses `did:cc:...` as a placeholder. Resolve in `context-protocol-v0.1.md` §5.2 (likely `did:key` for v0.1 simplicity, `did:web` optional).
2. **Embedding model.** Pluggable via `litellm`; default model name to be picked in ADR-005 (likely `voyage-3` or `text-embedding-3-large` — verify cost/quality at write time).
3. **Sanitization severity.** How aggressive is the prompt-injection scrub on import? Conservative-by-default; specifics in threat model §6.3.
4. **Local-first storage path.** Per-OS convention (e.g., `$XDG_DATA_HOME/context-capital/` on Linux, `~/Library/Application Support/Context Capital/` on macOS) — pick in runbook.
5. **License posture.** Apache 2.0 per `proposal-v2.md` §8; confirm vs. MIT during the first doc-writing session.
6. **Phase-1 telemetry policy.** Default off; opt-in only; specifics in runbook §5.
7. **Schema canonicalization for signing.** RFC 8785 (JCS) vs. a project-defined ordering — settle in `context-protocol-v0.1.md` §8.

## 12. Out-of-Scope Reminders

These were explicitly excluded from this brainstorm and remain out of scope:

- Phase 2/3 prosumer SaaS and enterprise tier docs.
- Marketing copy, pitch decks, investor narrative.
- Standards-body submission (AAIF SEP) — only the open spec doc, not the submission process.
- Plurality Network partnership / competitive countermove planning (separate strategy session).
- Anything depending on Phase-2 research items in `market-research.md` §9 (Mem0/Zep/Letta deep dives, TAM, etc.).

## 13. Cost & Time Estimate for the Deferred Doc-Writing Session

- SRS: ~$2, ~30 min.
- SDD: ~$3–4, ~45 min.
- Context Protocol v0.1 spec: ~$3, ~45 min.
- API spec (YAML + narrative): ~$2, ~30 min.
- Data model: ~$2, ~30 min.
- Threat model: ~$3–4, ~45 min.
- Conformance suite: ~$1.5, ~25 min.
- Test plan: ~$2, ~30 min.
- Deployment runbook: ~$1.5, ~25 min.
- 9 ADRs (template + 8): ~$3, ~45 min.

**Estimated total for the deferred session:** ~$23–28, ~5 hours of agent work.

These are rough; actual cost depends on model effort level (`/effort`) and how much research/cross-checking each doc demands.

## 14. References

- `../../intial-praposal.md` — original product proposal.
- `../../proposal-v2.md` — research-driven revised proposal; this build pack implements its Phase 1.
- `../../market-research.md` — competitive and adoption research (Jun 2026) backing the proposal.
- External: RFC 2119, RFC 8174, JSON Schema 2020-12, JSON-LD 1.1, RFC 8032 (Ed25519), MADR 3.0 (https://adr.github.io/madr/), MCP 2026 roadmap.
