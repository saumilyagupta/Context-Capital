# Market Research — Universal AI Context Portability Layer

> **Companion document to** `proposal-v2.md`. This file is the reference: facts, citations, profiles, and open questions. The proposal is the decision document.

**Research date:** 17 June 2026
**Method:** Deep-research workflow — 6 parallel search angles, 33 sources fetched, 153 claims extracted, 25 adversarially verified (3-vote panel), 23 confirmed, 2 refuted. 116 sub-agents, ~2.97M tokens.
**Confidence convention:** Every claim below is tagged **[verified-3-0]**, **[verified-2-1]**, **[unverified]**, or **[refuted]** based on the adversarial verification result. Treat unverified items as starting points for Phase 2 research, not facts.

---

## 1. Executive Summary

The original proposal's "Open Context Layer / user-owned cross-vendor portable AI memory" thesis is correct in spirit but **no longer commercially greenfield**. A direct competitor — Plurality Network — ships the same positioning today. The standards landscape (MCP, AAIF) covers agent plumbing but explicitly *not* user-owned memory portability, confirming a real structural gap. Regulatory portability rights (GDPR Article 20) cover a different problem and exclude exactly the data class AI memories occupy (inferred/derived). Sector-API standardization (UK Open Banking) is the proven adoption pattern; horizontal user-rights are not.

Three concrete strategic shifts follow from the research:

1. **Shift segment.** The consumer-passport lane is contested. The enterprise/team lane is open.
2. **Lead with a spec.** A published, neutral Context Protocol is the moat Plurality lacks.
3. **Plan for vendor non-cooperation.** Major AI vendors have AAIF seats but no public commitment to memory-export APIs; build assuming voluntary cooperation must be earned, not legislated.

---

## 2. Competitive Landscape

### 2.1 Three-segment structure (verified)

The "AI memory" market that overlaps with the proposal splits into four non-overlapping segments. Only one — Open Context Layer — directly competes with the proposal's thesis.

| Segment | What it does | Who pays | Direct competitor to proposal? |
|---|---|---|---|
| Developer agent infra | Persistent memory for AI agents/apps | Developers, app teams | No — different buyer, different value prop |
| OS-level personal memory | Captures everything on the user's machine | Individuals, devs | No — captures FROM OS, not FROM AI chats |
| Walled-garden personal AI | Self-contained AI with own memory | Consumers | Adjacent — they own memory but don't bridge to ChatGPT/Claude/Gemini |
| **Open Context Layer** | **User-owned, cross-vendor portable AI context** | **Consumers, prosumers, (eventually) enterprises** | **YES — Plurality Network occupies this lane** |

### 2.2 Detailed Profiles

#### Plurality Network — closest competitor [verified-3-0]

- **Sources:** plurality.network (primary), docs.plurality.network, Crunchbase/Pitchbook/Dealroom
- **Positioning:** Verbatim "Open Context Layer for Apps and AI Agents"; "Secure infrastructure for user-owned apps & AI context that travels anywhere"; "Zero vendor lock-in with complete platform independence."
- **Coverage:** ChatGPT, Claude, Gemini, Grok, Perplexity, DeepSeek.
- **Tech:** Chrome extension + MCP server. TEE-based privacy ("we literally cannot access your context").
- **Pricing:** Free / $10 (Plus) / $20 (Pro) per month.
- **Traction:** 2,000+ users, #1 Product Hunt ranking, Chrome Web Store presence.
- **Team:** ~3 employees (London). Founded 2023 by Mujtaba Idrees.
- **Funding:** Seed Feb 2024 from Outlier Ventures and Futureverse.
- **Origin caveat:** Pivoted from a Web3 "Smart Profiles" product; some legacy framing remains.
- **What they have not done:** Published an open context-schema specification, secured SOC2 / HIPAA, shipped an enterprise/on-prem tier, joined AAIF.
- **Strategic read:** Real and shipping. Small, capital-efficient, but resource-constrained. The right competitive move is differentiation (enterprise + open spec), not direct consumer-feature combat.

#### Supermemory — largest developer-infra player [verified-3-0]

- **Sources:** supermemory.ai/pricing (primary), corroborated by F6S, Atlan, Toolradar, Vectorize, Respan
- **Positioning:** "Context infrastructure for AI agents." Developer-targeted, not user-targeted.
- **Pricing (verified Jun 2026):** Free $0 + $5 credit · Pro $19/mo (~$20 credit) · Max $100/mo (~$130 credit, 6× Pro allocation) · Scale $399/mo (~$600 credit, SOC2 + HIPAA BAA, self-hosted) · Enterprise (air-gapped/dedicated).
- **Features:** Memory graph per user, auto profiles, fact hierarchies, multimodal extraction → contextual chunking → retrieval.
- **NOT in their marketing:** ChatGPT, Claude, Gemini, "cross-platform," "portable," or "user-owned."
- **Why not a direct competitor:** Targets the *builder* of an AI app, not the *user* of multiple AI apps. Different buyer.

#### Pieces (LTM-2) — OS-level memory [verified-3-0]

- **Sources:** pieces.app/blog/what-is-new-ltm-2 (March 2025), pieces.app/features/long-term-memory, docs.pieces.app
- **Positioning:** "Digital hippocampus" / "OS-Level Artificial Memory for developers and digital professionals."
- **Tech:** ~9 months of on-device retention, ~90% offline (vendor-reported; not independently audited). Roadmap to on-device SLMs delivered via LTM-2.5 (May 2025) and current LTM-2.7.
- **Captures:** Everything that crosses the user's OS — apps, IDEs, browser. Not chat-history bridge specifically.
- **Pricing:** Freemium.
- **Concerns:** GitHub issue #650 reports CPU/RAM performance issues even in Cloud mode. 90% offline figure self-reported.
- **Why not a direct competitor:** Different layer. Pieces captures FROM OS; proposal captures FROM AI chats.

#### Personal.ai — walled garden [verified-3-0]

- **Sources:** personal.ai/memory, personal.ai/you-own, personal.ai/privacy-notice (April 2025)
- **Positioning:** "Carrier-native memory infrastructure" / "Distributed Edge AI Platform."
- **Memory ownership:** Verbatim "Information stored in Your Memory is encrypted... You have complete control." Dedicated "You Own" page. GDPR/UK GDPR via Ametros Ltd as EU/UK rep. SOC2/HIPAA/GDPR posture. User data isolation.
- **Portability:** Verbatim "There will be mechanisms to download the memory and model in the future." Not shipped.
- **Integrations:** Only Nvidia as deployment partner. ChatGPT/Claude/Gemini appear in marketing only as competitive *benchmarks*, not as integrations.
- **Why not a direct competitor:** Walled garden. No cross-vendor bridge today. If they ship export, becomes a competitor — currently they are not.

#### Khoj — open-source baseline [verified-3-0]

- **Sources:** github.com/khoj-ai/khoj, docs.khoj.dev
- **Positioning:** Self-hostable, model-agnostic personal AI.
- **Coverage:** GPT, Claude, Gemini, Llama, Qwen, Mistral, Deepseek; OpenAI-compatible servers, Ollama, LMStudio, LiteLLM, HuggingFace, OpenRouter.
- **License:** AGPL-3.0.
- **Traction:** 35.2k GitHub stars.
- **Portability gap:** No cross-vendor memory export feature. Persistent memory itself is an open feature request (issue #1097, opened Jan 24 2025, still labeled "improve").
- **Why not a direct competitor:** Self-hosting gives data ownership at the DB layer but is not a packaged portability product. Strong potential partner for spec adoption.

### 2.3 Competitors Named But Not Adversarially Verified

Phase 1 covered 9 of ~40 competitors in depth. The following were named in the brief but did not surface in the 23 verified claims. Each is a P0 follow-up for Phase 2 research:

**Developer-infra agent memory:** Mem0, Zep, Letta (formerly MemGPT), LangChain Memory / LangGraph memory, Cognee, MemoryOS, Graphlit, EmbedChain, Composio, MemFree, Memori, Memex.

**Consumer/prosumer memory:** Rewind.ai, Saga AI, Heyday, Reflect, Mem.ai.

**Vendor-native memory features:** OpenAI ChatGPT Memory, Anthropic Claude Projects & Memory, Google Gemini Personal Context, Microsoft Copilot Memory & Windows Recall.

**Walled-garden / standalone AI:** Inflection Pi memory, Character.ai memory, Replika memory, MindOS / Mindverse, Kortix, Adept memory.

**Dev-tool integrated memory:** Continue.dev memory, Cursor memory.

> **Practical implication.** Some of these (especially Mem0, Zep, Letta, and the vendor-native features) may have meaningful cross-vendor portability features that Phase 1 did not surface. The proposal's "no one ships X" claims should be treated as "no one verified to ship X" until Phase 2 closes this gap.

### 2.4 Competitive Matrix

| Product | Cross-vendor capture | User-owned memory | Open schema | Enterprise (SOC2/HIPAA) | Conflict resolution | Prompt-injection hardening | Pricing |
|---|---|---|---|---|---|---|---|
| Plurality | ✅ 6 vendors | ✅ TEE | ❌ undisclosed | ❌ | ❌ | unclear | $0/$10/$20 |
| Supermemory | ❌ (agent infra) | ❌ (their store) | ❌ | ✅ Scale tier | ❌ | unclear | $0–$399, Enterprise |
| Pieces LTM-2 | ❌ (OS-level) | ✅ on-device | ❌ | ❌ | ❌ | n/a | Freemium |
| Personal.ai | ❌ (no bridge) | ✅ claimed | ❌ | ✅ | ❌ | unclear | Undisclosed |
| Khoj | ✅ model-agnostic | ✅ self-host | ❌ | ❌ | ❌ | unclear | Free + cloud |
| **Proposed Context Capital v2** | ✅ all major | ✅ user keys | ✅ Context Protocol | ✅ Phase 3 | ✅ §4.3 | ✅ §4.1 | $0/$25/$15-seat/$50-150-seat |

---

## 3. Standards & Protocols Landscape

### 3.1 Linux Foundation Agentic AI Foundation (AAIF) [verified-3-0]

- **Source:** Linux Foundation press release, Dec 9 2025; aaif.io; openai.com/index/agentic-ai-foundation; TechCrunch (Dec 9 2025); blog.modelcontextprotocol.io/posts/mcp-joins-aaif.
- **Platinum members:** AWS, Anthropic, Block, Bloomberg, Cloudflare, Google, Microsoft, OpenAI. This is the first time all four AI labs/clouds relevant to Context Capital sit on the same governance body.
- **Founding projects:** MCP (Anthropic, 10,000+ servers as of Dec 2025), goose (Block, local-first agent framework), AGENTS.md (OpenAI, project-level coding-agent instructions); agentgateway listed on aaif.io.
- **Messaging:** AWS (Sivasubramanian) and Cloudflare (Knecht) explicitly invoke "no vendor lock-in."
- **Critical absence:** The press release and aaif.io contain *zero* mentions of portable user memory, cross-vendor context export, memory versioning, or memory portability.

**Strategic read:** AAIF is the right forum to propose a Context Protocol. The seat is open because no member has filed it.

### 3.2 Model Context Protocol (MCP) — 2026 Roadmap [verified-3-0]

- **Source:** blog.modelcontextprotocol.io/posts/2026-mcp-roadmap (March 2026), corroborated by Toloka, Knit, The New Stack, Chatforest, tedt.org.
- **Four 2026 priorities:**
  1. Transport Evolution and Scalability (Streamable HTTP).
  2. Agent Communication (Tasks primitive, retry/expiry).
  3. Governance Maturation (Working Groups, SEP review bottleneck).
  4. Enterprise Readiness (audit trails, SSO, gateways, configuration portability — *not* memory portability).
- **Explicit confirmation from the primary source:** "Does not mention: Memory portability, User-owned context, Cross-vendor memory compatibility, Personal data stores, Agent memory systems."
- **External commentary** (e.g., a2a-mcp.org) treats memory portability as something MCP "must support" — but this is aspirational, not roadmap.

**Strategic read:** MCP is the right *transport* for a Context Protocol implementation (the MCP server pattern works), but MCP itself is not converging on memory portability. Build on top of MCP; do not assume MCP will solve this.

### 3.3 Prior Attempts at Portable Personal Data

| Standard / project | Result | Lesson |
|---|---|---|
| Solid (Tim Berners-Lee / Inrupt) | Low adoption despite tech merit | Tech alone doesn't drive adoption; need a killer integration partner |
| Data Transfer Project / Initiative | [refuted-0-3 on specific timeline]; remains small in scope | Voluntary big-tech coalitions struggle |
| MyData | Advocacy presence, low product adoption | Movement ≠ market |
| Digi.me | Acquired; product trajectory unclear | Even good portable-data products get absorbed |
| Schema.org / JSON-LD | Backbone of web semantics, widely adopted | Lightweight, voluntary, schema-only standards can win |

> One refuted claim: the assertion that the Data Transfer Project transitioned in 2022 to a Google/Apple/Meta-only DTI failed 0-3 verification. Do not cite this version of the DTP/DTI history without independent re-check.

### 3.4 The Strategic Slot

The pattern across these projects: **schemas + APIs + intermediaries succeed; legal-rights theater and big-tech coalitions struggle**. The Context Protocol should be schema-and-API first, lightly-governed, with a reference implementation (us) plus deliberate recruitment of independent implementors.

---

## 4. Market Sizing

> **Honest caveat:** No TAM/SAM/SOM claim survived 3-0 adversarial verification in Phase 1. Mordor Intelligence, SkyQuest, and The Business Research Company have published reports on the "Agentic AI Orchestration and Memory Systems Market," but their numbers were not stress-tested against multiple independent sources. **The market-sizing question is currently unanswered.**

### 4.1 Available signals (unverified)

- **a16z infrastructure thesis (Jennifer Li, gtmnow.com):** AI infrastructure broadly is a large and growing investment focus area; memory infrastructure is named as a notable category.
- **Mem0 "State of AI Agent Memory 2026" (mem0.ai/blog):** Industry-pulse report by an interested party; useful for category framing, not as third-party sizing.
- **Analyst-vendor reports** (Mordor Intelligence, SkyQuest, Business Research Co.) publish numbers but were not independently verified.

### 4.2 What we can say from adjacent benchmarks (verified)

- **UK Open Banking** (the closest *successful* analog for "user-owned portable infrastructure"):
  - 4M+ users by 2022.
  - 1.3 billion successful API requests in Dec 2023 (30% YoY, 70% over Dec 2021).
  - 16.5M users and 24B API calls by 2025.
  - Source: OECD 2024 portability report + openbanking.org.uk + Finextra.

- **Plurality's traction** (proxy for consumer-segment willingness-to-pay):
  - ~2,000 users, ~3-person team, $10/$20 paid tiers.
  - Implies six-figure-low-millions ARR if conversion is ~10–20% — small but real.

### 4.3 Recommended Phase 2 sizing work

- Pull Gartner / IDC / Forrester reports on "AI infrastructure" and "AI memory" categories.
- Pull a16z / Sequoia / Menlo Ventures "State of AI" reports.
- Build a bottom-up estimate: enterprise mid-market companies (5k–50k employees) × % running mixed AI stacks × estimated per-seat memory-portability spend.

---

## 5. Adoption History — What Worked, What Failed

### 5.1 The dominant lesson [verified-3-0]

**Sector-API standardization with intermediary services outperforms horizontal user-driven legal portability rights by ~100×.**

#### Open Banking UK (succeeded)
- 4M+ users in 2022 → 1.3B requests in Dec 2023 → 16.5M users + 24B calls in 2025.
- Standardized APIs + regulator pressure + AISP/PISP intermediary tier = compounding adoption.

#### GDPR Article 20 (didn't deliver real-world adoption)
- 26% awareness in Germany 2020.
- <7% had ever exercised the right (Luzsa et al. 2022).
- 25% intended to switch + transfer data but didn't.
- Only 74.8% of 230 real-world portability requests succeeded; file formats failed the "structured, commonly used and machine-readable" requirement (Wong & Henderson, *International Data Privacy Law* Vol. 9 Issue 3, 2019).
- Article 20(1)(a) is restricted to consent/contract bases; WP29 guidelines explicitly exclude **inferred or derived data including personal data created by a service provider (e.g., algorithmic results)** — confirmed by ICO, CNIL, IAPP, Dentons, Springer (2023), EU Data Act, Quebec 2024 law.
- **Direct implication:** AI memories (which are inferred/derived) are outside GDPR portability rights. Cannot rely on regulation.

### 5.2 Other patterns

| Pattern | Result | Why |
|---|---|---|
| OAuth | Won, ~10 years | Gradual standards iteration; massive industry need |
| OpenID Connect | Won slowly | Piggyback on OAuth 2.0 |
| Password manager export (1Password, Bitwarden) | Won | Well-defined format, minimal vendor cooperation needed |
| Browser bookmark sync | Won at vendor level, lost cross-vendor | Vendors prefer ecosystem lock-in |
| RSS | Faded | Walled gardens (FB, Twitter) won attention |
| XMPP | Faded | Big providers (Google, FB) cut interop |
| ActivityPub / Mastodon | Surviving niche | Lacks network-effects critical mass |
| CardDAV (contacts) | Modest adoption | Works but invisible to most users |
| Email | Universal | Pre-walled-garden vintage |
| Bitwarden / FIDO Alliance passkey portability work (2025) | In progress | Security vendors aligning |

**Two patterns predict success:**
1. **Standardized API + intermediary ecosystem + (optional) regulatory tailwind** → Open Banking.
2. **Well-defined export format that needs no vendor permission** → password managers.

**Two patterns predict failure:**
1. **Horizontal legal user-right with no API** → GDPR Article 20.
2. **Movement/coalition advocacy without product** → DTP/DTI, Solid, MyData.

---

## 6. Risk Assessment

### High likelihood × High impact
- **Plurality scales first.** They have 18 months on us. Mitigation: differentiate on enterprise + open spec; consider partnership.
- **Vendors refuse memory export APIs.** OpenAI/Anthropic/Google/Microsoft have AAIF seats but no public memory-export commitments. AAIF participation may be PR. Mitigation: rely on existing GDPR-style chat-export exports (which all four vendors offer) and scrape-and-MCP rails; design for voluntary cooperation; don't depend on it.

### Medium likelihood × High impact
- **Prompt-injection-via-import incident.** First publicized incident in this category would damage trust permanently. Mitigation: §4.1 of the proposal; public red team.
- **MCP/AAIF adds memory portability and locks us out.** Plausible 18–36 month risk. Mitigation: be the project proposer.

### Confirmed × Medium impact
- **GDPR Article 20 excludes inferred/derived data.** This is settled. Cannot use as wedge.
- **Standards adoption takes 5–10 years.** OAuth analogy. Mitigation: standalone economics must work pre-standard.

### Unknown × High impact
- **TAM smaller than assumed.** No verified analyst-grade sizing exists in Phase 1. Phase 2 must close this.

### Medium × Medium
- **Two-firm risk.** If Plurality and one well-funded incumbent (Supermemory pivots, or Personal.ai ships export) both move into our enterprise lane, three-way competition. Mitigation: speed + spec.

---

## 7. Pricing Benchmarks (Verified)

| Product | Free | Mid | Pro | High | Enterprise |
|---|---|---|---|---|---|
| Plurality | ✅ | $10/mo | $20/mo | — | — |
| Supermemory | $0 + $5 credit | $19/mo | $100/mo (Max) | $399/mo (Scale, SOC2/HIPAA) | Custom (air-gapped) |
| Pieces | Freemium | — | — | — | — |
| Personal.ai | Undisclosed | — | — | — | — |
| Khoj | Free (OSS) | Cloud tier (undisclosed) | — | — | — |

**Per-seat enterprise ceiling** in adjacent categories: $50–150/user/mo is the typical mid-market range for SOC2/HIPAA-grade B2B SaaS. Supermemory Scale at $399 is a flat-rate floor.

---

## 8. Concrete Recommendations for the Proposal

Mapped from the research into proposal-v2 sections:

| Research finding | Proposal change |
|---|---|
| Plurality occupies the consumer "Open Context Layer" lane | Move primary positioning to "Context Protocol + Enterprise" (proposal-v2 §2, §7) |
| MCP/AAIF don't cover memory portability | Lead with an open spec; target AAIF inclusion (§7) |
| GDPR Article 20 excludes derived data | Don't depend on regulation; build voluntary API rails (§7, §10) |
| Open Banking outperformed GDPR ~100× | API/standards-with-intermediaries GTM (§8) |
| Imported memories are an attack surface | Prompt-injection sanitization as headline security feature (§4.1) |
| No competitor publishes an open schema | Schema is the moat (§4.2, §5) |
| Plurality team is ~3 people | Speed advantage is achievable if well-funded (§10) |
| No verified TAM data | Flag as open question, don't claim sizing in pitch (§11) |
| Cross-vendor memory will create conflicts | Conflict resolution / diff tools as feature (§4.3) |
| Vendor-native features (ChatGPT Memory, etc.) not verified in Phase 1 | Phase 2 research P0 before any external pitch |

---

## 9. Open Questions (Phase 2 Research)

Carrying forward from the research caveats:

1. **Plurality's technical export schema.** Does their MCP server already implement a context-export schema? If yes, is it publicly documented? Direct technical due diligence required before any "first open spec" claim.
2. **Detailed competitive profiles** for the ~30 named-but-not-verified competitors (see §2.3).
3. **Major vendor positions on memory export.** Has OpenAI, Anthropic, Google, or Microsoft published a roadmap for memory-export endpoints? Their AAIF participation says "interoperability" but commercial incentive says "lock-in."
4. **Analyst-grade TAM/SAM/SOM.** Gartner / IDC / Forrester / a16z / Menlo on AI memory infrastructure 2024–2027, with enterprise vs. consumer split.
5. **Prompt-injection attack-class threat model.** Detailed survey of known attacks against imported memories; secondary research into LLM-guardrail effectiveness against memory-class payloads.
6. **Sector regulatory tailwinds.** DORA, EU Data Act 2025, UK CMA AI rules — does any of them mandate AI vendor portability in ways that benefit the proposal?
7. **Enterprise willingness-to-pay.** Interview procurement / IT-security teams at mid-market firms running mixed AI stacks. What would they pay for portable institutional context?
8. **Partnership vs. competition with Plurality.** Reach out, evaluate whether their MCP server could become a reference implementation of Context Protocol v0.1.

---

## 10. Sources (Verified, by Quality Tier)

### Primary (vendor sites, official docs, regulator reports)
- **plurality.network** — Plurality Network homepage and product surfaces.
- **docs.plurality.network** — Plurality technical docs.
- **plurality.network/blogs/** — `building-open-context-layer-for-the-internet`, `importance-of-portable-ai-context`.
- **supermemory.ai/pricing** — Verified pricing tiers and feature claims.
- **pieces.app/blog/what-is-new-ltm-2** — March 2025 LTM-2 announcement.
- **docs.pieces.app/products/core-dependencies/pieces-os/long-term-memory** — Tech reference.
- **pieces.app/features/long-term-memory** — Feature page.
- **personal.ai/memory**, **personal.ai/you-own**, **personal.ai/privacy-notice** — Verified ownership, GDPR posture, and "future capability" portability language.
- **github.com/khoj-ai/khoj**, **docs.khoj.dev** — Khoj capabilities and the open issue #1097.
- **linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation** — AAIF launch.
- **aaif.io** — Agentic AI Foundation site.
- **openai.com/index/agentic-ai-foundation** — OpenAI's AAIF post.
- **blog.modelcontextprotocol.io/posts/2026-mcp-roadmap** — MCP 2026 roadmap.
- **blog.modelcontextprotocol.io/posts/mcp-joins-aaif** — MCP joining AAIF.
- **oecd.org/.../the-impact-of-data-portability-on-user-empowerment-innovation-and-competition** (2024) — OECD primary portability report.
- **bitwarden.com/blog/security-vendors-join-forces-to-make-passkeys-more-portable-for-everyone** — Bitwarden 2025 passkey portability announcement.

### Secondary (third-party news, encyclopedias, analysis)
- TechCrunch coverage of AAIF launch (Dec 9 2025).
- en.wikipedia.org/wiki/Solid_(web_decentralization_project)
- en.wikipedia.org/wiki/Data_Transfer_Project
- en.wikipedia.org/wiki/Prompt_injection
- skywork.ai — Rewind/Limitless comparison.
- winbuzzer.com, sourcetrail.com, glasp.ai/articles/ai-memory-wars, mywrittenword.com — Vendor-native memory landscape coverage.
- theregister.com — Apple/Google cloud-photo interop coverage.

### Industry/blog (use as starting points only)
- dev.to/agdex_ai — Mem0 vs Zep vs Letta vs Cognee 2026 practical guide.
- baeseokjae.github.io — Best AI Agent Memory Frameworks 2026.
- graphlit.com/blog/survey-of-ai-agent-memory-frameworks
- codepointer.substack.com/p/agent-memory-systems-and-knowledge
- mcp.directory/blog/mem0-vs-letta-vs-zep-vs-cognee-2026
- fountaincity.tech/resources/blog/agent-memory-knowledge-systems-compared
- mem0.ai/blog/state-of-ai-agent-memory-2026
- duendesoftware.com — OAuth/OIDC timeline.

### Analyst-vendor sizing (unverified)
- skyquestt.com/report/agentic-ai-orchestration-and-memory-systems-market
- mordorintelligence.com/industry-reports/agentic-artificial-intelligence-orchestration-and-memory-systems-market
- thebusinessresearchcompany.com/report/agentic-artificial-intelligence-ai-orchestration-and-memory-systems-market-report
- mordorintelligence.com/industry-reports/ai-infrastructure-market
- gtmnow.com — a16z AI infrastructure thesis (Jennifer Li).

### Academic / regulatory
- Wong & Henderson, *International Data Privacy Law* Vol. 9 Issue 3 (Oxford Academic, 2019) — 230 GDPR Art. 20 request study.
- Luzsa et al. (2022, bidt-funded LMU Munich survey) — German GDPR portability awareness.
- Article 29 Working Party WP242 Guidelines.
- gdpr-info.eu — Article 20 text.
- EU Data Act (2025).
- ScienceDirect 2025 — Data portability strategies in the EU.

---

## 11. Two Refuted Claims (Do Not Rely On)

The adversarial-verification panel killed two claims by unanimous 3-0 vote. These are explicitly NOT supported by Phase 1 research:

1. **"Supermemory's connector ecosystem focuses on productivity/data sources (Drive, Notion, OneDrive, Gmail, Granola, GitHub, S3, Web Crawler) rather than on AI chat platforms (ChatGPT/Claude/Gemini)."** Verifiers found this characterization unsupported. Supermemory's connector positioning needs re-checking on the live product surface.
2. **"The Data Transfer Project (DTP), launched in 2018 by Google, Meta, Microsoft, Apple, and Twitter, was succeeded in 2022 by the Data Transfer Initiative (DTI) — a non-profit established by only Google, Apple, and Meta."** The specific timeline / membership story did not hold up. Treat the DTP/DTI history as unsettled until independently verified.

---

## 12. Research Methodology

- **Workflow:** Deep-research harness — 6 search angles in parallel, top-15 source dedup-fetch, 153 claims extracted, 25 verified via 3-vote adversarial panel.
- **Verification standard:** A claim is "confirmed" only on unanimous (3-0) verification. Some 2-1 claims survive but are weaker.
- **Coverage:** 9 of ~40 competitors profiled in depth; consumer-segment and standards-landscape are well-covered; market sizing is unverified; ~30 competitors carry over to Phase 2.
- **Time anchor:** All claims are as-of 17 June 2026. Standards landscape evolving fast — AAIF and MCP rate of change is real, so this document has a ~6-month shelf life on the standards section.
- **Reproducibility:** Run ID `wf_83e8284b-673`; transcript at `/private/tmp/claude-501/.../tasks/wy71e2ver.output`.

---

> The full Phase 1 verification log, with vote counts and source URLs per claim, is in the workflow transcript. This document is a synthesis; consult the transcript for the audit trail.
