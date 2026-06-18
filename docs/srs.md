# Software Requirements Specification — Context Capital Phase 1

| | |
|---|---|
| **Document** | SRS — Context Capital Phase 1 |
| **Version** | Draft v0.1 |
| **Date** | 2026-06-18 |
| **Status** | Draft |
| **Scope** | Phase 1 reference client + open Context Protocol v0.1 spec |
| **Owner** | Engineering Lead (TBD) |
| **Parent design** | [`superpowers/specs/2026-06-18-context-capital-build-pack-design.md`](superpowers/specs/2026-06-18-context-capital-build-pack-design.md) |
| **Parent product docs** | [`proposal-v2.md`](proposal-v2.md), [`market-research.md`](market-research.md) |

---

## 1. Introduction

### 1.1 Purpose
This SRS specifies the requirements for **Context Capital Phase 1** — a local-first, user-owned reference client for capturing, extracting, encrypting, exporting, and importing personal AI context across vendors, plus the **Context Protocol v0.1** open specification it implements.

Phase 1 is the smallest viable artifact that proves the thesis: a user can capture their ChatGPT and Claude history, extract useful long-term memories, encrypt them with their own keys, and export a signed, portable `context.json` that any compliant tool can re-import — including a sanitized import path that defends against the prompt-injection attack class that imported memories introduce.

### 1.2 Scope
**In scope (Phase 1):**
- Chrome MV3 extension for capture-side workflows.
- A local MCP server exposing the user's context to MCP-compatible clients (Claude Desktop and any future MCP client).
- An LLM-driven memory-extraction pipeline.
- Local encrypted storage (Postgres + pgvector primary; SQLite single-user fallback).
- An open Context Protocol v0.1 schema, JSON Schema, JSON-LD `@context`, and signed-export format.
- A sanitization layer for imported memories.
- Per-AI permission scopes and an audit log.

**Out of scope (deferred to later phases or sibling brainstorms):** see §8.

### 1.3 Definitions, acronyms, abbreviations

| Term | Definition |
|---|---|
| Context | The set of long-term memories representing a subject (person or organization) across AI tools. |
| Context Protocol | The open schema this project defines for exporting/importing context. Versioned v0.1 in Phase 1. |
| Memory | A single structured fact, preference, decision, project, workflow, or skill — extracted from raw chat or document content. |
| Subject | The person or organization a context describes. Identified by a DID. |
| Provenance | The vendor, conversation, timestamp, and excerpt a memory was extracted from. |
| Sensitivity | A classification tag (`public` / `work` / `personal` / `secret`) attached to each memory; secret-tagged memories MUST never leave the user device. |
| MCP | Model Context Protocol (Anthropic-led, Linux Foundation AAIF project). Used here as the transport between this product and AI tools. |
| Capture | Ingesting raw vendor chat exports (the user's own data, obtained through the vendor's official export). |
| Extraction | LLM-driven conversion of raw chat content into structured memories with confidence scores. |
| Sanitization | The process of validating imported memories and stripping/flagging directives that target a model's behavior rather than describing the subject. |
| DID | Decentralized Identifier (W3C). Used for subject identity; survives vendor changes. |
| Reference client | The Phase-1 deliverable: extension + MCP server + extraction engine + storage. Open-source, locally run. |

### 1.4 References
- [Build-pack design spec](superpowers/specs/2026-06-18-context-capital-build-pack-design.md) — locks scope, stack, doc bundle.
- [`proposal-v2.md`](proposal-v2.md) — product strategy and architecture overview.
- [`market-research.md`](market-research.md) — competitive landscape and adoption analogs.
- RFC 2119 / RFC 8174 — keyword normativity.
- JSON Schema 2020-12, JSON-LD 1.1, RFC 8032 (Ed25519).
- MCP 2026 roadmap (`blog.modelcontextprotocol.io/posts/2026-mcp-roadmap`).

### 1.5 Document overview
§2 frames the product. §3 enumerates the nine system features F-1 through F-9 with functional requirements. §4 covers external interfaces. §5 lists non-functional requirements grouped by quality attribute. §6 captures hard constraints. §7 defines success metrics. §8 lists out-of-scope items by design.

---

## 2. Overall Description

### 2.1 Product perspective
Context Capital sits **between** AI vendors (ChatGPT, Claude in Phase 1) and the user. It is not an AI vendor itself; it does not host a chat product. It is a privacy-respecting **memory passport** plus an **open protocol** that lets memories travel between vendors. The product follows a "tools, not platforms" posture: the user keeps everything locally; the open Context Protocol lets other tools cooperate without depending on Context Capital infrastructure.

### 2.2 Product functions (high-level)
1. **Capture:** Read user-supplied ChatGPT or Claude chat export files.
2. **Sanitize:** On import, scrub prompt-injection payloads and tag vendor provenance.
3. **Extract:** Run extraction prompts against captured content to produce structured memories with confidence.
4. **Store:** Persist memories in encrypted local storage; user holds the keys.
5. **Permission:** Tag memories with sensitivity; grant per-AI access scopes.
6. **Export:** Produce signed `context.json` in Context Protocol v0.1 format.
7. **Import:** Accept signed `context.json` from any compliant tool; sanitize; merge.
8. **Serve:** Expose memories to AI tools via MCP server (Claude Desktop integration as the canonical Phase-1 client).
9. **Audit:** Log all reads/writes/exports/imports for user review.

### 2.3 User classes and characteristics

| User class | Description | Volume estimate | Phase-1 priority |
|---|---|---|---|
| **Developer / power user** | Self-hosts, runs CLI, customizes extraction prompts | ~80% of Phase-1 users | P0 |
| **Prosumer** | Installs the extension, uses Claude Desktop, doesn't open a terminal | ~20% of Phase-1 users | P1 (basic UX is required; deep customization is not) |
| **External Context Protocol implementor** | Reads the open spec to build a competing or complementary product | < 10 in Phase 1 | P0 (the spec MUST be implementable from the doc alone) |

Out of scope for Phase 1: enterprise admins, compliance officers, casual consumers, AI agent developers — these classes get first-class treatment in later phases.

### 2.4 Operating environment

| Component | Target environment |
|---|---|
| Chrome extension | Chromium-based browsers ≥ MV3 (Chrome, Edge, Brave, Arc). Manifest V3 only. |
| MCP server | macOS 13+, Windows 11+, Ubuntu 22.04+. Python 3.12+. |
| Storage | Postgres 16 + pgvector ≥ 0.7 (primary); SQLite ≥ 3.42 (fallback). |
| AI tools | ChatGPT (chat export `.zip` / `conversations.json`), Claude (chat export `.json`). Claude Desktop as the canonical MCP client. |

### 2.5 Design and implementation constraints
- **Local-first.** Phase 1 ships no hosted service. All data lives on the user's machine.
- **User-held keys.** No Context Capital operator key can decrypt any user's data.
- **MCP-compatible.** Tool integration MUST go through MCP; no proprietary vendor APIs in Phase 1.
- **No unauthorized scraping.** Capture MUST use the vendor's official export mechanism or an authenticated, user-authorized API path. No screen-scraping, no DOM exfiltration from accounts the user has not explicitly authorized.
- **Open spec.** Context Protocol v0.1 ships under Apache 2.0 with a published JSON Schema and JSON-LD context.

### 2.6 User documentation
The Phase-1 release MUST ship with:
- A README covering install, first-run, and the capture→export→import golden path.
- The Context Protocol v0.1 spec (`docs/spec/context-protocol-v0.1.md`).
- The deployment runbook (`docs/ops/runbook.md`).
- A 60-second quickstart video (optional, P1).

### 2.7 Assumptions and dependencies
- The user can obtain a ChatGPT export from `chatgpt.com/#settings/DataControls` and a Claude export from Anthropic's privacy settings.
- The user has API access to at least one extraction-capable LLM (Anthropic, OpenAI, or a local Ollama model).
- MCP-compatible clients exist (Claude Desktop confirmed in Phase 1; others optional).
- Postgres + pgvector OR SQLite is available; the installer can bootstrap SQLite automatically.

---

## 3. System Features

Each feature lists: description, priority (P0 / P1 / P2), stimulus → response, and numbered functional requirements (FR-x.y). Priorities: **P0 = required to ship Phase 1; P1 = should ship; P2 = nice-to-have**.

### 3.1 F-1 — Capture from ChatGPT export
**Description.** Ingest an official ChatGPT data export and produce raw conversation records suitable for extraction.

**Priority:** P0.

**Stimulus / Response.**
- *Stimulus:* User downloads ChatGPT data export, drops the `.zip` (or extracted `conversations.json`) into the extension or CLI.
- *Response:* System parses the export, normalizes per-conversation records (turns, timestamps, model used), and writes them to the `contexts` and `raw_messages` tables tagged with `provenance.source = "chatgpt"`.

**Functional requirements.**
- **FR-1.1** The system MUST accept ChatGPT's official `conversations.json` schema as input.
- **FR-1.2** The system MUST normalize each conversation into one `context` row and N `raw_message` rows.
- **FR-1.3** The system MUST preserve raw text verbatim (for audit and re-extraction).
- **FR-1.4** The system MUST tag every captured record with `provenance.source = "chatgpt"`, `provenance.captured_at = <ISO 8601>`, and `provenance.export_file_hash = <sha256>`.
- **FR-1.5** The system MUST reject malformed or truncated exports with a structured error pointing at the failing record.
- **FR-1.6** The system SHOULD process exports up to 1 GB without OOM on a 16 GB-RAM developer machine.

### 3.2 F-2 — Capture from Claude export
**Description.** Same as F-1, for Claude.

**Priority:** P0.

**Functional requirements.**
- **FR-2.1** The system MUST accept Anthropic's official Claude data-export JSON schema.
- **FR-2.2** The system MUST normalize as in FR-1.2 with `provenance.source = "claude"`.
- **FR-2.3** FR-1.3 through FR-1.6 apply, substituting Claude.
- **FR-2.4** The system MUST handle Claude's nested artifact references (code blocks, tool calls) without losing structure.

### 3.3 F-3 — Memory extraction
**Description.** Convert captured raw conversation content into structured memories: preferences, facts, decisions, projects, workflows, skills. Each memory carries a confidence score and provenance link.

**Priority:** P0.

**Stimulus / Response.**
- *Stimulus:* User runs `extract --context-id <id>` or clicks "Extract" in the extension.
- *Response:* System chunks the raw content, runs extraction prompts against the configured LLM, validates the model output against the Context Protocol schema, persists memories with provenance, and reports extraction job status.

**Functional requirements.**
- **FR-3.1** The system MUST support extraction via a pluggable model layer (`litellm`-fronted) with at least one of: Anthropic Claude (default, with prompt caching), OpenAI, or Ollama.
- **FR-3.2** The system MUST produce, for every extracted memory: `kind`, `predicate`, `object`, `confidence ∈ [0, 1]`, `provenance.source`, `provenance.raw_excerpt`.
- **FR-3.3** The system MUST validate every extracted memory against the Context Protocol v0.1 JSON Schema before persisting; invalid memories MUST be dropped and logged.
- **FR-3.4** The system MUST be deterministic given the same input + prompt + model + temperature=0; i.e., re-extracting from the same `context_id` MUST produce identical memory IDs (content-addressed).
- **FR-3.5** The system MUST support resumable extraction: if interrupted, the next run continues from the last completed chunk.
- **FR-3.6** The system SHOULD support batch extraction of multiple contexts in parallel, respecting model rate limits.
- **FR-3.7** The system MUST attach a `sensitivity` tag to every memory; default `work` unless an extraction prompt classifies otherwise.

### 3.4 F-4 — Encrypted local storage
**Description.** All memories, raw messages, and audit entries are stored locally and encrypted at rest under user-held keys.

**Priority:** P0.

**Functional requirements.**
- **FR-4.1** The system MUST encrypt all data at rest using a symmetric key derived via Argon2id from the user's passphrase, OR a key generated and wrapped in the OS keystore (Keychain / DPAPI / Secret Service).
- **FR-4.2** No Context Capital operator key, server-side key, or vendor key MUST be required to decrypt user data.
- **FR-4.3** The system MUST never log raw secrets, passphrases, or derived keys.
- **FR-4.4** The system MUST support `lock` and `unlock` operations that release/load the in-memory key.
- **FR-4.5** The system MUST refuse all read/write operations while locked, returning a structured `LOCKED` error.
- **FR-4.6** The system MUST support secure passphrase rotation that re-wraps the data-encryption key without re-encrypting all rows.
- **FR-4.7** The system MUST zeroize sensitive buffers after use (where the platform permits).

### 3.5 F-5 — Context Protocol v0.1 export
**Description.** Produce a signed `context.json` document compliant with Context Protocol v0.1.

**Priority:** P0.

**Functional requirements.**
- **FR-5.1** The system MUST produce a document validating against the published v0.1 JSON Schema.
- **FR-5.2** The system MUST exclude all `sensitivity = "secret"` memories from the export by default; export MUST require an explicit `--include-secret` flag and an additional unlock prompt to override.
- **FR-5.3** The system MUST canonicalize the document per the spec (likely RFC 8785 JCS — to be locked in the spec doc) before signing.
- **FR-5.4** The system MUST sign the canonicalized document using Ed25519 with the subject's signing key.
- **FR-5.5** The system MUST record an audit log entry for every export (FR-9.x).
- **FR-5.6** The system MUST permit export of a filtered subset (by kind, predicate, sensitivity, or vendor source) via flags.
- **FR-5.7** Exported documents MUST be human-readable JSON (no binary framing) for debuggability.

### 3.6 F-6 — Context Protocol v0.1 import (with sanitization)
**Description.** Accept a signed `context.json` produced by any v0.1-compliant tool. Validate, sanitize, and merge into local storage.

**Priority:** P0. **This is the security-critical feature.**

**Functional requirements.**
- **FR-6.1** The system MUST verify the document's signature before any other processing; signature failure MUST abort import with no side effects.
- **FR-6.2** The system MUST validate the document against the v0.1 JSON Schema; schema failure MUST abort import.
- **FR-6.3** The system MUST treat all imported memory text as **untrusted input** and apply sanitization (see threat model §3 Prompt Injection):
  - Strip or quote-escape strings that look like model directives ("ignore previous instructions", "system:", "you are now …", etc.) within `object.value`, `provenance.raw_excerpt`, and other free-text fields.
  - Tag every imported memory with `provenance.imported = true` and `provenance.import_source = <issuer.tool>`.
  - Refuse memories whose `sensitivity` field is missing or invalid (default-deny).
- **FR-6.4** The system MUST detect duplicate memories (by content hash) and skip or merge per user-configured policy (default: skip).
- **FR-6.5** The system MUST detect conflicting memories (same subject + predicate, different object) and surface them in the audit log (FR-9.x); resolution MUST be user-driven (no automatic last-write-wins).
- **FR-6.6** The system MUST not auto-grant any per-AI permission scope based on imported permission grants; imports update the memory store only.
- **FR-6.7** The system MUST log an audit entry per import (FR-9.x).

### 3.7 F-7 — MCP server tool/resource surfaces
**Description.** Expose memories to MCP-compatible clients via a local MCP server.

**Priority:** P0.

**Functional requirements.**
- **FR-7.1** The system MUST implement a Model Context Protocol server using Anthropic's official `mcp` Python SDK.
- **FR-7.2** The server MUST support both `stdio` and Streamable HTTP transports (per the MCP 2026 roadmap).
- **FR-7.3** The server MUST expose at minimum the following tools:
  - `query_memories(subject_id, filters)` — return memories matching filters.
  - `get_memory(memory_id)` — return a single memory.
  - `record_observation(observation_text)` — append a user-confirmed observation as a new memory (P1).
- **FR-7.4** The server MUST expose at minimum the following resources:
  - `subject_summary://current` — a short text summary of the current subject suitable for system-prompt injection.
- **FR-7.5** Every tool/resource call MUST honor the active per-AI permission scope (F-8) and refuse memories outside the granted scope.
- **FR-7.6** The server MUST log every call to the audit log (F-9).
- **FR-7.7** The server MUST refuse to start when the store is locked; calls received while locked return `LOCKED`.

### 3.8 F-8 — Per-AI permission scopes
**Description.** Grant or revoke access to subsets of the memory store per AI tool / per session.

**Priority:** P0.

**Functional requirements.**
- **FR-8.1** The system MUST support named **scope grants**, each consisting of: scope name, AI client identifier, allowed `sensitivity` levels, allowed `kind` values, allowed `predicate` patterns, expiry timestamp (optional).
- **FR-8.2** The system MUST refuse any MCP tool/resource call that requests memories outside the active grant.
- **FR-8.3** Scope grants MUST be signed by the user (or wrapped in OS keystore) so a process running as another user can't forge a grant.
- **FR-8.4** Revocation MUST take effect within 1 second of the user issuing it.
- **FR-8.5** The default grant MUST be **deny-all**; the user MUST explicitly create the first scope.
- **FR-8.6** Sensitivity = `secret` MUST be excluded from every grant unless the user passes an explicit `--allow-secret` flag at grant creation.

### 3.9 F-9 — Audit log
**Description.** Append-only log of every read, write, export, import, scope-grant, and lock/unlock event.

**Priority:** P0.

**Functional requirements.**
- **FR-9.1** Every read of `query_memories`, `get_memory`, every export, import, scope grant/revoke, and lock/unlock MUST produce an audit entry.
- **FR-9.2** Audit entries MUST contain: `id`, `timestamp` (ISO 8601, UTC), `actor` (CLI user, MCP client identifier, or `system`), `action` (enum), `subject_id`, `details` (JSON), `outcome` (success | denied | error).
- **FR-9.3** Audit entries MUST be append-only at the database level (no DELETE / UPDATE permitted; verified by a daily integrity check).
- **FR-9.4** Audit entries MUST be encrypted at rest like other rows.
- **FR-9.5** The system MUST support paginated read access via the API and a CLI command (`cc audit tail`, `cc audit search`).
- **FR-9.6** The system MUST NOT include raw memory text or raw chat content in audit entries; references (memory IDs) only.
- **FR-9.7** A periodic (per-day) integrity check MUST verify that the audit log is internally consistent and hash-chained.

---

## 4. External Interface Requirements

### 4.1 User interfaces
- **Chrome MV3 extension** with at minimum: drop-zone for export files, capture/extract status panel, scope-grants list, audit-log viewer, lock/unlock control. React + TypeScript.
- **CLI** (`cc`) covering capture, extract, export, import, scope, audit, lock/unlock. Python `typer`-based.
- **No web UI for the hosted backend in Phase 1.**

### 4.2 Hardware interfaces
- None beyond standard developer hardware. No GPU required (extraction goes through API or local Ollama).

### 4.3 Software interfaces
| External system | Interface | Direction |
|---|---|---|
| ChatGPT export | File ingest (`conversations.json`) | Inbound |
| Claude export | File ingest (`.json`) | Inbound |
| Anthropic Claude API | HTTPS via Anthropic SDK | Outbound (extraction) |
| OpenAI API | HTTPS via OpenAI SDK (optional) | Outbound (extraction) |
| Ollama | HTTP (`localhost:11434` by default, optional) | Outbound (extraction) |
| MCP clients (Claude Desktop, others) | MCP stdio or Streamable HTTP | Bidirectional |
| Postgres / SQLite | Native DB protocol | Bidirectional |
| OS Keystore | macOS Keychain / Win DPAPI / Linux Secret Service | Bidirectional |

### 4.4 Communications interfaces
- **MCP stdio:** child-process pipe between MCP client and server (Phase-1 canonical).
- **MCP Streamable HTTP:** loopback `http://127.0.0.1:<port>` only; no external bind in Phase 1.
- **No outbound telemetry by default.** Opt-in only.

---

## 5. Non-functional Requirements

### 5.1 Security (NFR-SEC-*)
- **NFR-SEC-1** All persistent data MUST be encrypted at rest with user-held keys (FR-4.1).
- **NFR-SEC-2** Every external surface (MCP, CLI, extension messages) MUST authenticate the caller; unsigned scope grants MUST be rejected.
- **NFR-SEC-3** Sanitization (FR-6.3) MUST be applied to every imported memory before any LLM ever sees it.
- **NFR-SEC-4** Crypto primitives MUST use well-known libraries: `age` for symmetric file encryption, `libsodium` for AEAD, `argon2` for KDF, `ed25519-dalek`/`pynacl` for signing.
- **NFR-SEC-5** No secrets, passphrases, derived keys, or unencrypted memory text MUST appear in logs, telemetry, or crash reports.
- **NFR-SEC-6** Dependencies MUST be pinned, hash-checked, and audited at least quarterly.
- **NFR-SEC-7** The browser extension MUST request only the permissions strictly required for Phase-1 functions (file access, native messaging to the local MCP server, optional `clipboardWrite`).

### 5.2 Privacy (NFR-PRV-*)
- **NFR-PRV-1** Data MUST stay on the user's machine unless the user explicitly exports it.
- **NFR-PRV-2** Telemetry MUST be off by default and opt-in only.
- **NFR-PRV-3** A `delete` operation MUST hard-delete all rows for a given subject, including audit entries' referenced raw text, while leaving an audit "tombstone" recording the deletion.
- **NFR-PRV-4** `Sensitivity = "secret"` memories MUST NOT cross the export boundary or the MCP boundary by default (FR-5.2, FR-7.5, FR-8.6).

### 5.3 Performance (NFR-PRF-*)
- **NFR-PRF-1** Capture (parse-only) of a 100 MB ChatGPT export MUST complete in < 30 s on a 16 GB-RAM developer machine.
- **NFR-PRF-2** Extraction throughput SHOULD reach ≥ 500 memories/hour using Claude Sonnet with prompt caching enabled.
- **NFR-PRF-3** `query_memories` for typical filters (≤ 5 predicates) MUST return p50 < 100 ms, p95 < 500 ms on a store of up to 100,000 memories.
- **NFR-PRF-4** Export of 10,000 memories MUST complete in < 5 s.
- **NFR-PRF-5** MCP server cold-start time MUST be < 2 s.

### 5.4 Reliability (NFR-REL-*)
- **NFR-REL-1** Extraction jobs MUST be resumable after a crash with no duplicated memories (FR-3.4 deterministic IDs).
- **NFR-REL-2** Database writes MUST be transactional; a crash during write MUST never produce a partial memory.
- **NFR-REL-3** The system MUST support a `verify` command that performs a full integrity check (hashes, audit chain, schema conformance) and reports anomalies.
- **NFR-REL-4** Power-loss during export MUST never produce a malformed `context.json` reaching disk (write-to-temp + atomic rename).

### 5.5 Portability (NFR-PRT-*)
- **NFR-PRT-1** The CLI and MCP server MUST run on macOS ≥ 13, Windows ≥ 11, Ubuntu ≥ 22.04.
- **NFR-PRT-2** The extension MUST function on Chrome, Edge, Brave, and Arc (Chromium-based, MV3-capable).
- **NFR-PRT-3** SQLite fallback MUST be feature-complete relative to Postgres for single-user mode, modulo vector-search ANN performance.

### 5.6 Maintainability (NFR-MNT-*)
- **NFR-MNT-1** Unit-test coverage MUST be ≥ 80% for the extraction, sanitization, crypto, and schema layers.
- **NFR-MNT-2** All public Python and TypeScript APIs MUST have type hints / type annotations and pass `mypy --strict` / `tsc --strict`.
- **NFR-MNT-3** Every commit MUST pass linting (`ruff`, `eslint`), formatting (`black`, `prettier`), and the unit-test suite.
- **NFR-MNT-4** Every change to the Context Protocol schema MUST bump the schema version, ship a migration, and update the conformance suite.

### 5.7 Localization (NFR-LOC-*)
- **NFR-LOC-1** Phase 1 ships in English only. All user-visible strings MUST be wrapped in an i18n function so future localization is mechanical.
- **NFR-LOC-2** Date/time displayed to the user MUST use the OS locale; internal storage is always UTC ISO 8601.

---

## 6. Constraints

| ID | Constraint | Source |
|---|---|---|
| C-1 | Capture MUST go through official vendor export files (no unauthorized scraping) | Legal/ethical posture; proposal-v2 §4.1 |
| C-2 | Chrome extension MUST use Manifest V3 | Chrome MV2 sunset |
| C-3 | Tool integration MUST be MCP-only in Phase 1 | proposal-v2 §7; AAIF alignment |
| C-4 | All data MUST remain local in Phase 1 | proposal-v2 §8 Phase-1 scope |
| C-5 | All crypto MUST use user-held keys; no escrow | proposal-v2 §6 |
| C-6 | Schema MUST be published under Apache 2.0 | proposal-v2 §8 |
| C-7 | Sanitization MUST run before any LLM ever reads imported memory content | proposal-v2 §4.1 |

---

## 7. Success Metrics

Phase 1 ships when **all** of the following are demonstrably true:

### 7.1 Functional acceptance
- [ ] **G-1 Round-trip.** A real ChatGPT export AND a real Claude export, each ≥ 200 conversations, capture → extract → export → import-into-clean-instance → verify with no memory loss, no schema errors, no signature failures.
- [ ] **G-2 Sanitization.** The adversarial test corpus of ≥ 20 prompt-injection-via-import payloads (see threat model) MUST be blocked or neutralized; success rate = 100%.
- [ ] **G-3 MCP integration.** Claude Desktop, configured against the local MCP server, can answer "what do you know about me?" using memories surfaced via `subject_summary://current` and `query_memories`.
- [ ] **G-4 Conformance.** A second external implementation (even a minimal one — could be a script) passes the conformance suite against an exported Phase-1 `context.json`.
- [ ] **G-5 Lock/unlock.** The system correctly refuses all reads/writes while locked and accepts them after unlock; verified by automated test.

### 7.2 Quality metrics
- [ ] **Q-1** Unit-test coverage ≥ 80% in the four security-critical layers (NFR-MNT-1).
- [ ] **Q-2** Zero `mypy --strict` / `tsc --strict` errors.
- [ ] **Q-3** No `HIGH` or `CRITICAL` findings from a dependency audit (`pip-audit`, `npm audit`) at release.
- [ ] **Q-4** Threat-model mitigations all implemented or explicitly accepted with rationale.

### 7.3 Performance targets
- [ ] **P-1** NFR-PRF-1 through NFR-PRF-5 all met on the reference developer machine (16 GB RAM, M-series or equivalent x86).

---

## 8. Out-of-Scope (Phase 1)

The following are explicitly **not** Phase-1 requirements. They appear in `proposal-v2.md` for later phases and will get their own SRSes:

| Item | Why deferred |
|---|---|
| Gemini, Copilot, Cursor capture | Phase 2; Phase 1 proves the pattern on two vendors |
| Hosted multi-tenant backend, team accounts | Phase 2 prosumer SaaS |
| Knowledge-graph reasoning / inferential queries | Phase 2 |
| Conflict-resolution UI | Phase 2 (data model supports it; UI is later) |
| SOC2 / HIPAA / on-prem deployment | Phase 3 enterprise |
| Audit log export for compliance officers | Phase 3 |
| AAIF SEP submission | Phase 4 standards leadership |
| Marketing site, billing, account management | Outside engineering scope |
| Mobile apps | Future |
| Memory-export endpoints from AI vendors themselves | Vendor-dependent; we use official export files as the rail |
| Browser-extension support for Safari / Firefox | Could be added post-Phase 1 if demand justifies |

---

## Document control

- **Next review:** When the SDD (`docs/sdd.md`) is drafted; both docs MUST cross-reference each other consistently.
- **Change policy:** Material changes to F-1 through F-9 require updating both this SRS and the affected ADRs.
- **Approval gate:** This document is approved when (a) every section is non-empty, (b) all FR-x and NFR-* IDs are unique and referenced from at least one downstream doc, (c) the build-pack design spec §9 DoD checklist passes.
