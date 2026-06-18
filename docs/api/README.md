# API Reference — Context Capital Phase 1

| | |
|---|---|
| **Document** | API narrative |
| **OpenAPI** | [`openapi.yaml`](./openapi.yaml) (v0.1.0) |
| **Status** | Draft |
| **Companion docs** | [`../sdd.md`](../sdd.md), [`../security/threat-model.md`](../security/threat-model.md), [`../testing/test-plan.md`](../testing/test-plan.md) |

The Phase-1 reference client exposes **two** interfaces:

1. **REST over loopback** — used by the CLI and the browser extension's native-messaging host. Specified in `openapi.yaml`. This document is its narrative companion: authentication, errors, idempotency, versioning, and integration notes.
2. **MCP** — Model Context Protocol surface used by external AI clients (Claude Desktop, etc.). Specified in §4 below.

The REST and MCP surfaces share the storage layer but are NOT mirrors of each other. REST is for *administration*; MCP is for *querying memories from inside an AI tool*.

---

## 1. Network model

- The server binds **only to `127.0.0.1`** (loopback). It does not listen on `0.0.0.0`.
- Default REST port: `7843`. Configurable in `~/.context-capital/config.toml`.
- The MCP server uses **stdio** by default (preferred). It also offers a Streamable HTTP MCP endpoint at `/mcp` on the same loopback host:port, behind the same security model as REST.
- CORS: the server does NOT enable CORS. Browser tabs cannot call the API directly; the extension uses native messaging instead.

## 2. Authentication

Phase 1 uses a single per-install token:

- Generated at install time: 32 random bytes, base64 (`X-CC-Token` header).
- Stored in the OS keystore (Keychain / DPAPI / Secret Service).
- Required on every request **except** `GET /v1/control/status` (liveness).
- Native-messaging extension and the local CLI receive the token at register time.

There is **no remote authentication** in Phase 1 because there is no remote backend. Phase 2 will add OAuth-style flows for the hosted backend.

A missing or wrong token returns HTTP 401 with `code: AUTH_REQUIRED`.

## 3. Conventions

- **Versioning.** Path-prefixed: `/v1/…`. Breaking changes bump the major.
- **Content type.** Requests + responses are `application/json` (except multipart upload for `/captures`).
- **Errors.** RFC 7807 Problem Details (`application/problem+json`). Always includes `type`, `title`, `status`, plus a project-specific `code` for programmatic dispatch (`LOCKED`, `AUTH_REQUIRED`, `BAD_SIGNATURE`, etc.).
- **Idempotency.** `POST /captures` is idempotent by `(subject_id, file_hash)` — same export returns the same `capture_id` and HTTP 409.
- **Pagination.** Cursor-based. Endpoints that paginate return `next_cursor` (opaque string) or `null`. Pass it back as `?cursor=…`.
- **Time.** All timestamps are ISO 8601 UTC with `Z` suffix.
- **IDs.** UUIDv4 for transient entities (captures, jobs, scope grants), content-addressed `mem_<32hex>` for memories.
- **Locked behavior.** When the store is locked, *every* endpoint except `/control/status` and `/control/unlock` returns HTTP 423 with `code: LOCKED`.

## 4. MCP surface

The MCP server is implemented with Anthropic's official `mcp` Python SDK. It exposes the following capabilities.

### 4.1 Tools

| Tool | Arguments | Returns |
|---|---|---|
| `query_memories` | `subject_id` (str, optional, defaults to active subject), `kind`, `predicate`, `sensitivity` (subset), `q` (free text), `limit` (int ≤ 50) | Array of `Memory` (same shape as REST `Memory` schema, but per the active scope grant, never including `secret` unless the grant authorizes it). |
| `get_memory` | `memory_id` (str) | One `Memory` or error if outside scope. |
| `record_observation` (P1) | `observation_text` (str) | A `Memory` proposed by the model; the user MUST confirm before persistence. The MCP server raises a UI notification through the extension. |

### 4.2 Resources

| Resource URI | Description |
|---|---|
| `subject_summary://current` | A ~300-token natural-language summary of the active subject, derived from the highest-confidence memories the calling client is permitted to read. Suitable for system-prompt injection. Regenerated on each read (no caching). |

### 4.3 Prompts

| Prompt name | Purpose |
|---|---|
| `memory-aware-system-prompt` | Returns a templated system prompt that wraps the calling model's instructions with `subject_summary` plus untrusted-content delimiters (consistent with the threat model §3). |

### 4.4 Scope resolution

Every MCP call is identified by an MCP `client_id`. The server:

1. Resolves the calling `client_id` to an **active** `scope_grant` (revoked grants are ignored).
2. If none exists, the call is denied with `SCOPE_DENIED`.
3. If a grant exists, only memories within `allowed_sensitivities ∩ allowed_kinds ∩ allowed_predicates` are returned.
4. Every call is logged as an `audit_log_entries.action = 'query' | 'get_memory' | 'record_observation'`.

### 4.5 Transports

- **stdio** (default): one MCP server child process per MCP client.
- **Streamable HTTP**: same loopback host:port as the REST API, path `/mcp`. Uses the standard MCP HTTP framing. Auth: same `X-CC-Token` header as REST.

## 5. Quickstart

### 5.1 Capture and extract via CLI

```bash
# Unlock
$ cc unlock                       # prompts for passphrase

# Capture a ChatGPT export
$ cc capture --vendor chatgpt --file ~/Downloads/conversations.json
capture-id: 9b9c1a3e-... (chatgpt, 482 messages)

# Run extraction
$ cc extract --capture-id 9b9c1a3e-...
Extracted 127 memories in 6m12s.

# Export
$ cc export --subject did:key:z6Mk... --out ./me.context.json
Wrote ./me.context.json (signed; 127 memories).
```

### 5.2 Capture via REST

```bash
curl http://127.0.0.1:7843/v1/captures \
  -H "X-CC-Token: $CC_TOKEN" \
  -F vendor=chatgpt \
  -F file=@conversations.json
```

### 5.3 Import a context.json

```bash
curl http://127.0.0.1:7843/v1/context/import \
  -H "X-CC-Token: $CC_TOKEN" \
  -H "Content-Type: application/json" \
  --data @another-tool.context.json
```

Returns counts and any `conflicts` (predicate-level disagreements; user-resolved per spec §FR-6.5).

### 5.4 Wire Claude Desktop to the MCP server

Add to Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "context-capital": {
      "command": "cc",
      "args": ["mcp"],
      "env": { "CC_TOKEN_PATH": "~/.context-capital/token" }
    }
  }
}
```

Then in Claude Desktop, grant the **"work-coding"** scope (created via `cc scope add`) and queries like *"What do you know about my projects?"* will use `query_memories` + `subject_summary://current`.

## 6. Rate limiting

- REST endpoints: **240 requests/min per token**, burst 60. `Retry-After` header on 429.
- MCP calls: **60 calls/min per `client_id`**, burst 10.
- Unlock failures: 5 attempts per 60 seconds, then a 30-second cooldown.

## 7. Errors

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed input. |
| 400 | `SCHEMA_INVALID` | Imported `context.json` failed v0.1 schema check. |
| 401 | `AUTH_REQUIRED` | Missing or wrong `X-CC-Token`. |
| 401 | `BAD_SIGNATURE` | Imported document failed signature verification. |
| 403 | `SCOPE_DENIED` | MCP call outside the active grant. |
| 404 | `NOT_FOUND` | Resource doesn't exist (or is invisible due to scope). |
| 409 | `DUPLICATE` | Already-ingested export (same `file_hash`). |
| 423 | `LOCKED` | Store is locked. |
| 429 | `RATE_LIMITED` | Rate exceeded. |
| 429 | `UNLOCK_THROTTLED` | Too many wrong passphrases. |
| 500 | `INTERNAL` | Bug — file a report with the (synthetic) trace ID. |

Every error body follows RFC 7807:

```json
{
  "type": "about:blank",
  "title": "Store is locked",
  "status": 423,
  "code": "LOCKED",
  "detail": "Call /v1/control/unlock first."
}
```

## 8. Integration notes

### 8.1 Browser extension
- The extension does NOT make REST calls directly. It uses Chrome's `nativeMessaging` to send framed JSON to the MCP server's native-messaging entry point.
- The native-messaging manifest is registered at install time by the server installer (per OS).

### 8.2 CLI
- The CLI loads the token from the OS keystore at startup.
- A `--json` flag on every command emits machine-readable output.

### 8.3 Tests
- `tests/api/` includes:
  - OpenAPI conformance via `schemathesis` (or equivalent).
  - Auth + lock-state tests for every endpoint.
  - Round-trip export → import golden tests (see `../testing/test-plan.md`).

## 9. Versioning of the API itself

- The OpenAPI doc carries `info.version: 0.1.0`.
- Breaking changes bump the path prefix to `/v2`. Phase 1 ships only `/v1`.
- A `/v1/control/status` response includes `version` (server) and `schema_version` (data model) so clients can branch behavior.

## 10. Future work (not in Phase 1)

- WebSocket / SSE for live extraction progress.
- OpenAPI-generated SDKs (Python, TypeScript).
- Remote authentication (OAuth, mTLS) for hosted backend.
- A separate gRPC surface for high-volume MCP clients (deferred; the SDK already supports Streamable HTTP).

## References

- [`openapi.yaml`](./openapi.yaml) — the spec, source of truth.
- [`../sdd.md`](../sdd.md) §2.7 — server design.
- [`../srs.md`](../srs.md) §F-5, §F-6, §F-7, §F-8, §F-9 — requirements.
- [`../security/threat-model.md`](../security/threat-model.md) — attack model on these surfaces.
- [`../testing/test-plan.md`](../testing/test-plan.md) — contract + integration testing.
