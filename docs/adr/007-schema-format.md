# ADR-007: Schema format — JSON Schema 2020-12 + JSON-LD + Ed25519 detached signature

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-18 |
| **Deciders** | Phase-1 engineering lead + spec author |
| **Tags** | schema, signing, interop |

## Context and Problem Statement

Context Protocol v0.1 defines `context.json`. The format choice determines what tooling exists, how easy implementations are to write, and what canonicalization rules the signature relies on.

## Decision Drivers

- Implementers in any modern language must be able to validate without exotic tools.
- The schema must be expressive enough for the v0.1 data model (subject, memories, provenance, validity, sensitivity, permissions, signature).
- Signing requires a stable, well-defined canonicalization.
- Future graph-store integrations (Phase 2) benefit from RDF-compatible semantics.

## Considered Options

1. **Plain JSON + custom validation rules in prose.**
2. **JSON Schema 2020-12, no JSON-LD.**
3. **JSON Schema 2020-12 + JSON-LD `@context` (RDF-compatible).**
4. **Protobuf / Cap'n Proto** — binary, schema-coupled.
5. **Custom JSON with embedded JWS-like signing** instead of detached Ed25519.

## Decision Outcome

**Chosen: Option 3 — JSON Schema 2020-12 as the normative validator, JSON-LD `@context` for graph-compatible mapping, Ed25519 detached signature with RFC 8785 (JCS) canonicalization.**

### Consequences

- ✅ Validators exist in every modern language (`ajv`, `jsonschema`, `Jschema`, etc.).
- ✅ JSON-LD opens an RDF/graph-store path without making it required for v0.1 conformance.
- ✅ Canonicalization (JCS) is widely implementable — small libraries exist for it.
- ✅ Ed25519 detached signature keeps the document plain JSON (no JWS framing).
- ⚠️ JSON-LD adoption is uneven; we use it lightly and never as the source of truth for v0.1.
- ❌ Binary formats would be smaller but lose human readability.

## Pros and Cons of the Options

### Option 1 — Prose-only validation
- ✅ Maximal flexibility.
- ❌ No mechanical conformance; every implementor diverges.

### Option 2 — JSON Schema only
- ✅ Simple.
- ❌ Closes the door to graph-store integration cleanly.

### Option 3 — JSON Schema + JSON-LD + Ed25519 + JCS (chosen)
- ✅ Canonical pieces; spec sticks together.
- ❌ More moving parts.

### Option 4 — Protobuf / Cap'n Proto
- ✅ Compact, typed.
- ❌ Not human-readable; the spec hides behind binary tooling.

### Option 5 — JWS-style signing
- ✅ One standard, one library.
- ❌ Wraps the JSON in base64url segments, hurting readability.

## More Information

- spec/context-protocol-v0.1.md §6 (JSON Schema), §7 (JSON-LD), §8 (Signing).
- conformance-suite.md SG-* — what signature tests catch.
- Re-review when JSON Schema or JCS publishes a new draft we should track.
