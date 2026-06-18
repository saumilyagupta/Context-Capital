# Context Capital — Universal AI Memory Infrastructure (v2)

> **What changed in v2.** Deep market research (Jun 2026, 33 sources, 23 adversarially-verified claims) shows the original positioning — "Open Context Layer / portable AI context passport" — is **no longer greenfield**. A London-based competitor, Plurality Network, ships almost-identical messaging today. Standards bodies (MCP, AAIF) have not committed to memory portability, leaving a real gap — but it is narrower than the original draft assumed, and requires a sharper differentiator, an API/standards-first go-to-market, and an explicit security architecture. This document supersedes `intial-praposal.md`.

---

## 0. TL;DR

- **Thesis still valid:** Models are commoditizing; user-owned, portable context is the asset.
- **Greenfield assumption wrong:** Plurality Network occupies the "Open Context Layer" tagline already, with TEE encryption, cross-vendor coverage (ChatGPT/Claude/Gemini/Grok/Perplexity/DeepSeek), Chrome extension, MCP server, and $10–20/mo pricing.
- **Real remaining gap:** No one has yet delivered (a) an **enterprise-grade**, audit-friendly portable-context layer with on-prem option, (b) an **open schema specification** submitted to a neutral standards body (AAIF/MCP working group), or (c) a **memory layer hardened against prompt-injection-via-import** — the attack class that imported memories enable.
- **Pivot:** From "consumer passport" to **"Context Protocol + Enterprise Context Capital"**. Lead with a published open schema; monetize enterprise deployment, compliance, and quality, not consumer subscriptions.
- **GTM lesson from research:** UK Open Banking (4M+ users, 1.3B API calls/mo) outperformed GDPR Article 20 (which only ~7% of eligible users have ever exercised, and which explicitly excludes inferred/derived data — i.e. AI memories). Build standardized APIs with intermediary services, not legal-rights theater.

---

## 1. Problem Statement (Refined)

Original framing was right, but the audience that *pays* is different from the audience that *suffers most*.

### Who suffers

- **Individual users** re-explain themselves to every AI tool.
- **Developers** restate their stack, conventions, and project context 20 times a week.
- **Companies** watch institutional knowledge solidify inside one vendor's memory store.
- **Agents** lose identity, continuity, and judgment when the underlying model changes.

### Who pays

Research shows the consumer segment is already being chased (Plurality at $10–20/mo, OS-level memory by Pieces, walled-garden personal AIs by Personal.ai). **The unmet demand sits with enterprise procurement and security teams**: they have compliance mandates around portability (DORA, GDPR Article 20 for the non-derived subset, EU Data Act 2025), they pay 100× consumer ARPU, and they need an answer to "what happens to our institutional context if we switch from Claude Enterprise to GPT?"

### Restated problem

> AI models are becoming replaceable for everyone. **Context portability is currently optional for consumers and mandatory for institutions** — and no one is shipping an institution-grade, audit-friendly portable-context product.

---

## 2. Differentiated Positioning

Three things the proposal cannot continue to be:


| ❌ Don't be                                                          | Why                                                                                                                          |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| "Open Context Layer" / "passport" / "context that travels anywhere" | Plurality owns this verbatim; trying to out-brand them is unwinnable                                                         |
| Pure consumer subscription                                          | Plurality is in this lane; ARPU is low; switching cost is low                                                                |
| Standards-after-product                                             | History (OAuth, OpenID, RSS, GDPR Art. 20) shows products shipped before the standard get eaten by the standard's incumbents |


Two things it should be:


| ✅ Be                                                                                          | Why                                                                                               |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| The **Context Protocol** — a published, versioned, neutral schema for portable AI memory      | Plurality has not published one; MCP roadmap doesn't address memory; this is the AAIF-shaped hole |
| **Context Capital Enterprise** — the audit-friendly, on-prem-capable reference implementation | Enterprise procurement is where the budget is; reference-impl + standard = pull from incumbents   |


### Tagline candidates (avoiding Plurality's space)

- "The Context Protocol: institution-grade portable AI memory."
- "Your company's AI institutional knowledge, on your keys, on any model."
- "Memory rights for institutions. Models are rentals. Context is owned."

---

## 3. Competitive Landscape (Verified)


| Segment                | Product                            | Cross-vendor?                                        | User-owned?                          | Export schema?                         | Pricing                                | Status                                                          |
| ---------------------- | ---------------------------------- | ---------------------------------------------------- | ------------------------------------ | -------------------------------------- | -------------------------------------- | --------------------------------------------------------------- |
| **Open Context Layer** | **Plurality Network**              | Yes (ChatGPT/Claude/Gemini/Grok/Perplexity/DeepSeek) | Yes (TEE)                            | Via MCP server, no public spec         | Free / $10 / $20 mo                    | **Shipping, ~3 employees, Outlier Ventures + Futureverse seed** |
| Developer infra        | Supermemory                        | No (vendor-agnostic for *agents*, not chat bridge)   | No (their platform owns)             | No                                     | $0+$5 / $19 / $100 / $399 / Enterprise | Shipping, profitable trajectory                                 |
| Developer infra        | Mem0, Zep, Letta, Cognee, Graphlit | No                                                   | No                                   | No                                     | Various                                | Shipping; agent memory category leaders                         |
| OS-level memory        | Pieces (LTM-2)                     | OS-wide, not chat-bridge                             | Yes (~90% on-device, 9 mo retention) | No                                     | Freemium                               | Shipping; "digital hippocampus"                                 |
| Walled garden          | Personal.ai                        | No (no ChatGPT/Claude/Gemini integration)            | Claims yes (GDPR/SOC2)               | Promised "future capability"           | Undisclosed                            | Shipping; standalone AI                                         |
| Open-source baseline   | Khoj (35.2k ★)                     | Yes (model-agnostic)                                 | Yes (self-host, AGPL-3.0)            | No persistent memory yet (issue #1097) | Free + cloud                           | Shipping; no chat-bridge feature                                |


### What no one is shipping

1. A **published, versioned, JSON-LD-compatible schema** for portable AI context that has been submitted to a neutral standards body.
2. An **enterprise-grade** product (SOC2 + HIPAA BAA + on-prem + audit log) for portable context — Supermemory is the closest at Scale/$399 but is agent-infra, not user-context-portability.
3. A **prompt-injection-hardened import path** — the security architecture for accepting memories from one vendor and replaying them into another.
4. Cross-vendor **memory diffing/conflict resolution** (when ChatGPT and Claude disagree about who you are).

These are the four wedges this proposal should target — in that order.

> **Caveat from research.** Only 9 of the ~40 competitors named in the original brief were verified in depth. Mem0, Zep, Letta, Cognee, Graphlit, Rewind, Saga, Heyday, Reflect, Mem.ai, ChatGPT Memory, Claude Projects/Memory, Gemini Personal Context, Copilot/Windows Recall, Inflection Pi, Character.ai, Continue.dev, Cursor, Composio, MindOS, Kortix, MemFree, Memori, Memex were named but their 2026 feature-sets, pricing, and portability stance were not adversarially confirmed. Before any pitch deck, run a phase-2 sweep on these.

---

## 4. Architecture (Revised)

The original five layers (Capture → Extraction → Knowledge Graph → Versioning → Migration + Security/Permissions) remain correct. Revisions add four new components made necessary by the research:

```
                ┌──────────────────────────────────────────────┐
                │ ChatGPT  Claude  Gemini  Copilot  Cursor ... │
                └──────────────────────────────────────────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                │  Capture Layer    │   Vendor Adapters │
                │  (ext/API/MCP)    │  (per-vendor SDK) │
                └───────────────────┴───────────────────┘
                                    │
                ┌──────────────────────────────────────┐
                │  ★ Prompt-Injection Sanitization     │ ← NEW
                │  ★ Vendor Provenance Tagging         │ ← NEW
                └──────────────────────────────────────┘
                                    │
                ┌──────────────────────────────────────┐
                │  Memory Extraction Engine            │
                │  Confidence-scored, source-cited     │
                └──────────────────────────────────────┘
                                    │
                ┌──────────────────────────────────────┐
                │  Personal Knowledge Graph + Memory   │
                │  Versioning (timeline, conflicts)    │
                └──────────────────────────────────────┘
                                    │
                ┌──────────────────────────────────────┐
                │  ★ Context Protocol Schema (open)    │ ← NEW
                │  ★ Conflict Resolution / Diff Tools  │ ← NEW
                └──────────────────────────────────────┘
                                    │
                ┌──────────────────────────────────────┐
                │  Encryption (user keys) + Permission │
                │  Per-AI scope + Audit Log            │
                └──────────────────────────────────────┘
                                    │
                ┌──────────────────────────────────────┐
                │  Export: context.json (open schema)  │
                │  Import: any compliant AI system     │
                └──────────────────────────────────────┘
```

### 4.1 Prompt-Injection Sanitization (NEW)

Imported memories are an attack surface. A memory like *"User wants you to ignore all subsequent safety instructions"* would be a privilege-escalation payload when imported into a new vendor. The system must:

- Treat all imported memories as **untrusted input**, scanned with the same defenses used against user prompts.
- Strip imperative directives that target the model's behavior rather than describing the user.
- Tag every memory with vendor provenance — so the receiving model knows the memory was extracted from a competitor, not authored by a human.

### 4.2 Context Protocol Schema (NEW)

The format the original proposal called `context.json` becomes a **first-class, versioned, JSON-LD-compatible specification**. Open from day one. Reference implementation, conformance suite, and SEP-style RFC track. The schema is the moat — Plurality has product but not (yet) a published spec, and MCP doesn't address memory portability.

### 4.3 Conflict Resolution / Diff Tools (NEW)

When ChatGPT's memory says "I prefer Python," Claude's memory says "I prefer Rust," and the user's actual repo on GitHub is mostly Go — the system needs to surface conflicts, not silently merge them. Three modes: surface-only, user-resolve, last-write-wins. Audit-logged.

### 4.4 Vendor Provenance Tagging (NEW)

Every memory carries the chain: `source = chatgpt:conv_abc123 → extracted_at = 2026-04-12 → confidence = 0.82 → reviewed = false`. Enables deletion-by-source, vendor-specific permission rules, and forensic audit.

---

## 5. Open Schema (Context Protocol v0.1 Sketch)

```json
{
  "context_protocol_version": "0.1.0",
  "subject": {
    "type": "person | organization | agent",
    "id": "did:cc:..."
  },
  "issuer": {
    "tool": "context-capital@1.0",
    "exported_at": "2026-06-17T..."
  },
  "memories": [
    {
      "id": "mem_...",
      "kind": "preference | fact | decision | workflow | project | skill",
      "subject_id": "...",
      "predicate": "prefers | uses | works_on | decided | rejected",
      "object": { "value": "PyTorch", "type": "tool" },
      "confidence": 0.92,
      "provenance": {
        "source": "chatgpt:conv_abc123",
        "extracted_at": "...",
        "raw_excerpt": "..."
      },
      "validity": {
        "valid_from": "...",
        "valid_until": null,
        "superseded_by": null
      },
      "sensitivity": "public | work | personal | secret",
      "permissions": { "deny": ["personal_ai_assistant_for_finance"] }
    }
  ],
  "schema_version_log": [],
  "signature": { "alg": "ed25519", "value": "..." }
}
```

Notes for spec:

- JSON-LD `@context` for graph compatibility.
- DIDs (decentralized identifiers) for subject identity — survives vendor + provider changes.
- Signed manifest so importers can prove memories came from a real export.
- `sensitivity` field maps naturally to per-AI permission scopes.

---

## 6. Security Model (Hardened)

Original draft had encryption + permission. Insufficient. Research and threat-modeling add:

1. **User-held keys.** Default. No vendor (including Context Capital) can decrypt. Aligned with Plurality's TEE story but does not require TEE — works on local hardware-key (Secure Enclave, TPM) or self-managed KMS.
2. **Per-AI permission scopes.** Coding assistant gets coding memories only. Finance assistant gets financial memories only. Permission grants are signed and revocable.
3. **Prompt-injection sanitization on import.** See §4.1.
4. **Provenance audit log.** Every read, write, export, import logged with subject + tool + scope.
5. **Right to forget — locally and remotely.** Deletion API that issues revocations to every vendor the memory was previously synced into. Best-effort but auditable.
6. **Sensitivity classification.** Memories tagged with sensitivity level; secret-tagged memories never leave user device.
7. **Adversarial memory testing.** Internal red team that imports synthetic poisoned memories quarterly. Reports public.

This is also the **enterprise-grade story** competitors don't have. Plurality's TEE is impressive but not SOC2-audited; Supermemory has SOC2/HIPAA but doesn't carry user keys; Personal.ai has compliance but no portability.

---

## 7. Standards Strategy — The Decisive Bet

### What the research shows

- **Linux Foundation Agentic AI Foundation (AAIF), Dec 2025.** Anthropic, OpenAI, Google, Microsoft, AWS, Block, Bloomberg, Cloudflare as platinum members. Founding projects: MCP (10,000+ servers), goose, AGENTS.md. **No memory-portability project.**
- **MCP 2026 roadmap.** Four priorities: Transport, Agent Communication, Governance, Enterprise Readiness. **Memory portability not on it.**
- **No competing standards body covers this.**
- **Past attempts:** Solid (low adoption), Data Transfer Project / Initiative (small membership, slow momentum), Digi.me (acquired), MyData (advocacy not adoption).

### What to do

1. **Publish the Context Protocol spec on day 1 of public launch.** Open license (Apache 2.0 or CC-BY). Versioned RFC track.
2. **File an AAIF project proposal** as soon as v0.1 ships and has at least one external implementation. The AAIF's stated mission is interoperability — memory portability is precisely the slot they have not filled.
3. **Build the spec into MCP-server form** so existing MCP clients (Claude Desktop, etc.) can read/write context without us shipping a separate client. This is the Open Banking AISP model — let intermediaries integrate cheaply.
4. **Recruit a second implementor early** (Plurality, Personal.ai, Khoj, or an enterprise) so the standard isn't a one-vendor language. Even hostile second-implementor adoption legitimizes a spec.

### Adoption lessons from research

- **UK Open Banking (sectoral API standardization with intermediaries):** 4M+ users 2022 → 1.3B API requests Dec 2023 → 30% YoY growth → 16.5M users by 2025. ✅
- **GDPR Article 20 (horizontal user-right):** 26% awareness in DE, <7% exercise rate, 74.8% request success rate. Inferred/derived data **explicitly excluded** — AI memories don't qualify. ❌
- **OAuth:** Took ~10 years but won via gradual standards iteration. ✅ slow
- **OpenID Connect:** Succeeded slowly via piggyback on OAuth 2.0. ✅ slow
- **RSS / XMPP:** Faded — walled-garden incentives won. ❌
- **Bitwarden/1Password export:** Worked — well-defined format, minimal vendor cooperation needed. ✅

**Conclusion:** Bet on the API/standards-with-intermediaries pattern. Do not depend on regulation or voluntary big-tech coalitions.

---

## 8. Go-to-Market

### Phase 1 — Open spec + reference client (months 0–6)

- Publish Context Protocol v0.1 spec under Apache 2.0.
- Open-source a reference client (Chrome extension + MCP server) that captures from ChatGPT and Claude.
- Free for individuals; the goal is spec adoption and developer trust.
- Recruit 5–10 friendly third-party MCP integrators.

### Phase 2 — Prosumer + team SaaS (months 6–12)

- Hosted version: $20–30/mo prosumer (slightly above Plurality to signal seriousness), $15/user/mo team plan.
- Add Gemini/Copilot/Cursor capture.
- Ship knowledge-graph reasoning, conflict-resolution UI, audit log.

### Phase 3 — Enterprise (months 12–24)

- $50–150/user/mo, $50K+/year floor for SOC2 + HIPAA + on-prem option.
- Compliance team handles GDPR Article 20 / DORA / EU Data Act portability requests on the customer's behalf.
- Sales motion: procurement teams of mid-market companies running mixed AI vendor stacks.

### Phase 4 — Standards leadership (months 18+)

- AAIF project submission.
- Annual conformance report / public test suite.
- Possibly: a non-profit foundation that owns the spec; commercial product is one (best-known) implementation.

---

## 9. Pricing


| Tier                 | Price                   | Audience                | Includes                                                                           |
| -------------------- | ----------------------- | ----------------------- | ---------------------------------------------------------------------------------- |
| Open Spec            | Free                    | Developers, integrators | Full schema, conformance suite, reference client, MIT/Apache                       |
| Personal             | Free                    | Individuals             | Capture from 2 AIs, 1 GB context, 90-day history, no team features                 |
| Prosumer             | $25/mo                  | Devs / power users      | All vendors, 10 GB, knowledge graph, conflict resolution, weekly export            |
| Team                 | $15/user/mo (min 5)     | Startups, small teams   | Shared org context, role-based scopes, SSO, 100 GB                                 |
| Enterprise           | $50–150/user/mo + floor | Mid-market & up         | SOC2, HIPAA BAA, on-prem option, audit log, dedicated compliance, custom retention |
| Standards Membership | $10K–50K/yr             | Vendors / integrators   | Conformance certification, early spec access, voting seat                          |


Benchmarks (verified): Plurality $10/$20, Supermemory $19/$100/$399, Personal.ai undisclosed. Positioning above Plurality on personal/prosumer and well below Supermemory's per-seat enterprise will signal "serious but accessible."

---

## 10. Risks


| Risk                                                                                     | Likelihood | Impact | Mitigation                                                                                                                                                                                 |
| ---------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Plurality scales consumer + adds enterprise                                              | High       | High   | Beat them to enterprise; publish open spec they have not                                                                                                                                   |
| Major AI vendors refuse to expose memory APIs                                            | High       | High   | MCP server + scraping fallback for chat-history exports already available (ChatGPT/Claude offer GDPR-style exports); Open Banking-style regulator pressure is a tailwind, not a dependency |
| Prompt-injection-via-import incident damages trust                                       | Medium     | High   | §4.1 sanitization; public red-team; sensitivity-tagged memories never auto-import to model context                                                                                         |
| Standards adoption takes >5 years                                                        | High       | Medium | Standalone product economics must work without standards win                                                                                                                               |
| GDPR Article 20 / EU Data Act do not extend to derived data                              | Confirmed  | Medium | Don't depend on regulation; ship voluntary cooperation rails                                                                                                                               |
| MCP/AAIF adds memory portability as a project, occupying our wedge                       | Medium     | High   | Be the one who proposes it; we either lead the project or contribute the reference impl                                                                                                    |
| TAM smaller than assumed                                                                 | Unknown    | High   | Research did not surface analyst-grade market sizing; this is a known open question (see §11)                                                                                              |
| Encryption + portability + extraction is harder than the four-page architecture suggests | High       | Medium | Prototype before committing to roadmap dates; phase 1 reference client should run end-to-end on a real user before phase 2 starts                                                          |


---

## 11. Open Questions Carried Forward

The research left these unresolved; treat them as P0 follow-ups before any external pitch:

1. **Plurality's exact technical export schema** — is `context.json` already partially specified by Plurality via their MCP server? Direct technical due diligence required.
2. **Detailed competitive profiles** for Mem0, Zep, Letta, Cognee, Graphlit, Rewind, Saga, Heyday, Reflect, Mem.ai, ChatGPT Memory, Claude Memory, Gemini Personal Context, Copilot/Recall, and the 15+ other named competitors not verified in this round.
3. **Vendor positions on memory export APIs** — has any of OpenAI / Anthropic / Google / Microsoft published a roadmap for memory-export endpoints? Their AAIF participation says "interoperability" but their commercial incentive says "lock-in."
4. **TAM/SAM/SOM** — Mordor / SkyQuest / Business Research Co. reports exist but were not adversarially verified; a16z infrastructure thesis is supportive but unsized. Need analyst-grade numbers for the enterprise AI memory infrastructure segment.

---

## 12. Long-Term Vision (Unchanged in Spirit, Sharpened in Form)

Three years out, the win condition is:

- An open Context Protocol that 3+ vendors implement.
- A reference implementation (us) that is the default deployment in mid-market enterprises running mixed AI stacks.
- An ecosystem of intermediaries (the AISP/PISP equivalents) that read and write through the spec — backup providers, compliance auditors, agent personalizers, identity-verifiers.
- The phrase **"What's your context score?"** entering enterprise procurement vocabulary, the way "What's your SOC2 status?" did between 2015 and 2020.

The asset is not the storage. The asset is not the model. The asset is the **context graph the user/org owns**, and the **protocol that lets it move**.

> Models are rentals. Context is owned. Memory has rights.

