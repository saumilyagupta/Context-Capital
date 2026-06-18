# ADR-005: Extraction model — `litellm` pluggable, default Claude with prompt caching

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-18 |
| **Deciders** | Phase-1 engineering lead |
| **Tags** | extraction, llm, cost, privacy |

## Context and Problem Statement

The extraction engine converts raw chat content into structured memories. The choice of LLM dominates extraction quality, cost, and privacy footprint. Locking to one provider creates vendor lock-in; supporting every provider creates a quality matrix nightmare. We need a sensible default with an escape hatch.

## Decision Drivers

- Extraction throughput target ≥ 500 memories/hour (SRS §NFR-PRF-2).
- Cost — capture passes a chunk through the LLM once; we expect ≤ $0.05/conversation for a typical user.
- Privacy — users SHOULD be able to extract without sending chat content to a third party (i.e., local model option).
- Quality — Phase-1 extraction templates assume good instruction-following.
- Prompt caching — proposal-v2 §4.5 calls out caching as a cost lever.

## Considered Options

1. **Single provider (Anthropic)** — opinionated, simple, locked in.
2. **`litellm`-fronted pluggable layer with sensible defaults.**
3. **Direct integration with three providers via separate SDKs (Anthropic, OpenAI, Ollama).**
4. **Local-only via Ollama** — privacy-maximal, but quality regression at small parameter sizes.

## Decision Outcome

**Chosen: Option 2 — `litellm`-fronted pluggable layer; default `anthropic/claude-sonnet-4-7` with prompt caching; opt-in `openai/gpt-4-mini` and `ollama/*`.**

Configuration:
- Default model: `anthropic/claude-sonnet-4-7` (the latest Sonnet at decision time, per project context).
- Prompt caching: ON by default for Anthropic (cacheable prefix = system prompt + schema definition + extraction instructions).
- Embedding model placeholder: `voyage-3` or equivalent 1024-dim model; finalized in Phase-2 implementation when the embeddings index goes live.

### Consequences

- ✅ Users can opt for cost (cheaper OpenAI), quality (Anthropic), or privacy (Ollama) by editing one config line.
- ✅ `litellm` normalizes streaming / structured-output APIs across providers.
- ✅ Prompt caching gives a ~50–80% cost reduction on the cacheable prefix.
- ⚠️ Quality varies by model; extraction templates may need per-model tuning. Tests pick this up as quality regressions.
- ⚠️ `litellm` is a third-party orchestrator — pinned and audited like any other dep.
- ❌ Local Ollama models routinely under-extract; Phase-1 tests cover this expectation.

## Pros and Cons of the Options

### Option 1 — Anthropic only
- ✅ Simplest, best quality.
- ❌ Lock-in; users without an Anthropic account can't use the tool.

### Option 2 — litellm pluggable (chosen)
- ✅ One config option to swap providers; matches the cross-vendor ethos.
- ❌ Dependency surface widens.

### Option 3 — Three SDKs side-by-side
- ✅ Maximum control per provider.
- ❌ Triple the maintenance; structured-output abstractions diverge across SDKs.

### Option 4 — Ollama only
- ✅ No data leaves the user's machine.
- ❌ Quality and throughput unacceptable at consumer-laptop scale.

## More Information

- SDD §2.4 — extraction pipeline.
- SRS §F-3, §NFR-PRF-2.
- runbook §1.4 — model config.
- threat model §2.4 — data sent to LLM providers.
- Re-review when a Claude or OpenAI release shifts the cost / quality frontier materially.
