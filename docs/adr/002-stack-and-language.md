# ADR-002: Stack and language — TypeScript (extension) + Python (server)

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-18 |
| **Deciders** | Phase-1 engineering lead |
| **Tags** | stack, language, build |

## Context and Problem Statement

Phase 1 has two long-lived runtimes: the Chrome MV3 extension and the local server (which hosts the MCP server, CLI, capture, extraction, storage). Picking the languages once locks in build, test, and deployment tooling for the next year.

## Decision Drivers

- **Anthropic's `mcp` Python SDK** is the canonical MCP server library; using it removes an entire class of compatibility issues.
- The team's strongest language depth is in Python and TypeScript.
- The extension must be TypeScript (or JavaScript) by virtue of running in the browser; choosing TS is non-controversial.
- The extraction layer is a thin orchestration wrapper around LLM APIs — Python ecosystem (`litellm`, `instructor`, `pynacl`, `argon2-cffi`, `pgvector`/`pgvector-python`) is excellent here.
- Cryptography libraries: `libsodium` is available in both languages but the Python binding (`pynacl`) is more battle-tested than equivalent JS at this stack layer.
- Phase-1 ships local-only — no need for Rust-level performance.

## Considered Options

1. **TypeScript everywhere (Node server)** — single language, shared types via Zod / TypeBox.
2. **Python everywhere with Pyodide-compiled extension** — single language but adds an experimental browser runtime.
3. **Go server + TS extension** — performance + portable single-binary.
4. **TS extension + Python server** — language per layer of the stack.
5. **Rust core (crypto, sanitization) + Python orchestration + TS extension** — extra safety for the security-critical layers.

## Decision Outcome

**Chosen: Option 4 — TypeScript for the extension, Python 3.12 for the server.**

### Consequences

- ✅ MCP integration via the official Anthropic Python SDK with no shimming.
- ✅ Best-in-class extraction libraries (`litellm`, `instructor`, `pydantic`).
- ✅ Extension is conventional MV3 TS + React; no exotic runtime.
- ⚠️ Two languages to maintain — duplicate type definitions across the boundary (mitigated by codegen from JSON Schema).
- ⚠️ Python startup time is slower than Go/Rust; mitigated by `cc serve` long-running process.
- ❌ Rules out a single-binary distribution; we ship a PyInstaller package as a workaround.

## Pros and Cons of the Options

### Option 1 — TS everywhere
- ✅ One language, one tooling.
- ❌ MCP Python SDK is more mature than the TS SDK in early-2026; libraries for extraction are weaker.

### Option 2 — Python via Pyodide in browser
- ✅ One language.
- ❌ Experimental, bundle size huge, debugging miserable.

### Option 3 — Go server
- ✅ Single binary, fast startup, strong concurrency.
- ❌ MCP Go SDK is less mature; extraction layer needs a Python sidecar anyway for `instructor`/`litellm`.

### Option 4 — TS + Python (chosen)
- ✅ Pragmatic, leverages each layer's strongest ecosystem.
- ❌ Cross-language schema sharing requires discipline.

### Option 5 — Rust core
- ✅ Memory-safe + fast for crypto / sanitization.
- ❌ Overkill for Phase 1; `libsodium` via Python binding is sufficient and already battle-tested.

## More Information

- SDD §2 — components.
- SRS §NFR-PRT-1, §NFR-PRT-2 — portability targets.
- Reconsider in Phase 2 if a hosted backend would benefit from Go or Rust services.
