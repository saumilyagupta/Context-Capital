# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**Documentation-only project.** There is no code, no build, no tests, no lint, and no package manifest. The artifact is a *specification pack* for a product called **Context Capital** — a universal, user-owned, cross-vendor AI memory portability layer. All deliverables are Markdown (plus one Postgres DDL file and one OpenAPI YAML).

If a future session adds code, the planned stack is: **TypeScript + React + Vite** (Chrome MV3 extension) and **Python 3.12 + FastAPI + Anthropic's `mcp` Python SDK** (local MCP server) — locked in by [`docs/adr/002-stack-and-language.md`](docs/adr/002-stack-and-language.md). Until then, no `make`/`pytest`/`npm` to run.

## Document tree (orient here first)

```
docs/intial-praposal.md         original draft (kept for history; superseded by docs/proposal-v2.md)
docs/proposal-v2.md             current product strategy — start here
docs/market-research.md         33-source competitive + adoption research backing proposal-v2
docs/
├── superpowers/specs/2026-06-18-context-capital-build-pack-design.md   spec-of-specs (locks scope, stack, doc list)
├── srs.md                 requirements (F-1..F-9, NFR-*, success criteria G-*/Q-*/P-*)
├── sdd.md                 architecture, components, Mermaid sequence diagrams, failure modes
├── spec/
│   ├── context-protocol-v0.1.md     open RFC-style spec (JSON Schema + JSON-LD + Ed25519 + JCS)
│   └── conformance-suite.md         L1–L4 levels and test categories
├── data-model.md          narrative + ER diagram
├── data-model/schema.sql  Postgres 16 + pgvector DDL
├── api/openapi.yaml       OpenAPI 3.1 for the loopback REST surface
├── api/README.md          narrative companion (auth, errors, MCP surface)
├── security/threat-model.md   STRIDE + prompt-injection-via-import attack tree
├── testing/test-plan.md   pyramid, CI gates, coverage matrix
├── ops/runbook.md         local dev / staging / secrets / observability
└── adr/                   MADR 3.0 — template + ADR-001..008 for load-bearing decisions
```

**Reading order for a fresh contributor:** `docs/proposal-v2.md` → `docs/market-research.md` → `docs/superpowers/specs/2026-06-18-…-design.md` → `docs/srs.md` → `docs/sdd.md` → ADRs → the rest.

## Strategic facts to keep in mind

- **Plurality Network is a direct, shipping competitor** on the original "Open Context Layer" thesis (London, ~3 employees, Outlier Ventures / Futureverse seed, TEE encryption, $10/$20 mo). Proposal-v2 pivoted away from that lane toward **enterprise + open spec**. Do not write copy that re-enters Plurality's positioning. See `docs/proposal-v2.md` §2 and `docs/market-research.md` §2.2.
- **Phase-1 scope is locked at one specific slice:** open Context Protocol v0.1 + Chrome extension + local MCP server + capture from ChatGPT and Claude only. Anything broader (Gemini, Copilot, hosted SaaS, enterprise tier) is Phase 2/3 and out-of-scope for the current docs.
- **Four v2-only architecture pieces** (added during the deep-research-driven revision; don't drop them):
  1. Prompt-injection sanitization on import (`docs/proposal-v2.md` §4.1, threat model §3 — the headline differentiator).
  2. Published open Context Protocol schema (`spec/context-protocol-v0.1.md`).
  3. Conflict resolution / diff tools (ADR-008 — surface-only, never last-write-wins).
  4. Vendor provenance tagging on every memory.
- **Standards strategy** (proposal-v2 §7): publish the spec under Apache 2.0, target the **Linux Foundation AAIF** as the standards venue (founded Dec 2025 with OpenAI/Anthropic/Google/Microsoft/AWS as platinum members; its MCP / goose / AGENTS.md projects explicitly *do not* cover memory portability — that's the gap).

## Conventions in these docs

- **Markdown + Mermaid** everywhere (diagrams render in GitHub/GitLab/VSCode).
- **RFC 2119 keywords** (MUST/SHOULD/MAY) are normative inside `spec/context-protocol-v0.1.md` and `spec/conformance-suite.md`; informational elsewhere.
- **ADRs follow MADR 3.0** (Status / Context / Decision drivers / Considered options / Decision outcome / Pros & cons / More information). One decision per file.
- **Dates are ISO 8601** (`YYYY-MM-DD`). All timestamps in examples are UTC.
- **Cross-references use relative paths** from the source doc's location — never absolute paths.
- **Identifiers are namespaced.** SRS uses `F-1..F-9` for features, `FR-x.y` for functional requirements, `NFR-SEC/PRV/PRF/REL/PRT/MNT/LOC-*` for non-functional, `C-1..C-7` for constraints, `G-*/Q-*/P-*` for success criteria. Threat model uses `G.1..G.5` for the prompt-injection attack tree. Conformance suite uses `SV-/SG-/SA-/PP-/VR-/SH-/RT-/EX-` test prefixes.
- **Memory IDs are content-addressed**: `mem_<32-hex-of-sha256-of-canonical-content>`.

## Open questions carried forward

These are explicitly unresolved; touch them with care. Sources: `docs/proposal-v2.md` §11, `docs/market-research.md` §9, `docs/superpowers/specs/2026-06-18-…-design.md` §11.

1. Plurality's exact technical export schema — direct technical due diligence still needed before any "first published spec" claim.
2. ~30 named competitors (Mem0, Zep, Letta, Cognee, vendor-native ChatGPT/Claude/Gemini memory features, Rewind, Saga, Mem.ai, etc.) were named but not verified in Phase-1 research.
3. No analyst-grade TAM/SAM/SOM survived adversarial verification.
4. Major vendor positions on memory-export APIs (OpenAI/Anthropic/Google/Microsoft) — AAIF participation says cooperation; commercial incentive says lock-in.

## Auto-memory

This project has an auto-memory file at `~/.claude/projects/-Users-shyamal-Desktop-code-token-capital/memory/MEMORY.md` that the Claude Code harness loads automatically. It carries the same project-context summary — don't duplicate it here; update it via the auto-memory protocol when material project facts change.
