# ADR-006: MCP transport — Anthropic `mcp` Python SDK over stdio + Streamable HTTP

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-18 |
| **Deciders** | Phase-1 engineering lead |
| **Tags** | mcp, transport, integration |

## Context and Problem Statement

The Phase-1 product integrates with AI tools via the Model Context Protocol. We must pick a server library and a transport (stdio vs HTTP variants). The MCP ecosystem is moving fast (10,000+ servers as of Dec 2025; MCP 2026 roadmap names Streamable HTTP as the transport future).

## Decision Drivers

- Claude Desktop (the canonical Phase-1 client) supports stdio out of the box.
- The MCP 2026 roadmap promotes Streamable HTTP for non-stdio scenarios (long-running tasks, browsers).
- Anthropic's `mcp` Python SDK is the reference implementation; using it tracks spec evolution.
- We don't want a custom transport that locks us out of the ecosystem.

## Considered Options

1. **Custom JSON-RPC server over WebSocket / SSE.**
2. **Official `mcp` Python SDK, stdio only.**
3. **Official `mcp` Python SDK, stdio + Streamable HTTP.**
4. **`mcp` TypeScript SDK** — if we shifted the server to Node.

## Decision Outcome

**Chosen: Option 3 — official `mcp` Python SDK with stdio (default for Claude Desktop) and Streamable HTTP (for the future and for browser-side clients).**

### Consequences

- ✅ Zero compatibility surprises with Claude Desktop.
- ✅ Spec evolution arrives via SDK updates; we don't maintain JSON-RPC plumbing.
- ✅ Streamable HTTP supports long-running ops without WebSocket overhead.
- ⚠️ MCP is pre-1.0; surface area can shift. Dependency pinned by version; CI re-runs the conformance suite on bumps.
- ❌ Spec changes may force minor refactors quarterly. Acceptable.

## Pros and Cons of the Options

### Option 1 — Custom JSON-RPC
- ✅ Maximum control.
- ❌ Loses ecosystem integration; reinvents what the SDK already provides.

### Option 2 — Official SDK, stdio only
- ✅ Simpler.
- ❌ Cuts off browser-side / long-running consumers.

### Option 3 — Official SDK, stdio + HTTP (chosen)
- ✅ Future-proof; canonical transports.
- ❌ Two code paths to test.

### Option 4 — TS SDK
- ✅ One language with the extension.
- ❌ Server stack is Python per ADR-002.

## More Information

- SDD §2.7 — MCP server design.
- SRS §F-7, §NFR-PRF-5.
- threat model §2.7 — server threat surface.
- Watch the MCP 2026 roadmap quarterly; flag breaking changes.
