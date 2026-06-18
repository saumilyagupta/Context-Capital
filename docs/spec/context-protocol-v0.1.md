# Context Protocol — v0.1.0

| | |
|---|---|
| **Document** | Context Protocol v0.1.0 |
| **Status** | Draft |
| **Date** | 2026-06-18 |
| **License** | Apache 2.0 (intended) |
| **Authors** | Context Capital project |
| **Repository** | TBD on first publication |
| **Discussion** | TBD (issue tracker on first publication) |

---

## 1. Status

This document specifies **version 0.1.0** of the **Context Protocol**, an open format for exporting and importing personal AI memory ("context") between AI tools and storage providers.

v0.x is a **pre-stable** track. Breaking changes are permitted until v1.0.0. Conformance MUST cite the exact version tested.

The reference implementation is Context Capital's Phase-1 client (`../srs.md`). External implementations are welcomed and required for legitimization of the standard (see [`conformance-suite.md`](./conformance-suite.md)).

## 2. Abstract

Personal AI memory is currently locked inside vendor-specific stores (ChatGPT memory, Claude projects, Gemini personal context, Copilot memory). The Context Protocol defines a vendor-neutral, signed, user-owned JSON document — `context.json` — that captures a subject's long-term AI-relevant memories with provenance, validity, sensitivity, and per-AI permissions. Any compliant tool MAY produce or consume such a document, enabling memory portability across vendors without depending on vendor cooperation beyond the user's own data-export rights.

## 3. Terminology

The keywords **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in [RFC 2119] and [RFC 8174].

Additional terms used in this document:

| Term | Definition |
|---|---|
| **Context document** | A single JSON document conforming to this specification. The file extension `.json` is RECOMMENDED. |
| **Subject** | The entity (person or organization) the context describes. |
| **Issuer** | The tool that produced the context document. |
| **Memory** | A single structured entry in `memories[]`. |
| **Provenance** | The vendor, conversation, time, and excerpt a memory originated from. |
| **Validity** | The temporal window during which a memory is considered current. |
| **Sensitivity** | A four-level classification (`public` / `work` / `personal` / `secret`) used by consumers to filter memories. |
| **Importer** | A tool that consumes a context document. |
| **Exporter** | A tool that produces a context document. |
| **Conforming implementation** | A tool that passes the corresponding level of the v0.1.0 conformance suite. |

## 4. Goals and Non-goals

### 4.1 Goals
- Capture **long-term, structured, reusable** memory; not full chat transcripts.
- Be **vendor-neutral** in semantics; nothing in the schema MUST favor one model provider.
- Make every memory **auditable**: provenance, timestamps, and confidence are first-class.
- Make every memory **safe to import**: the importer can detect tampering, sanitize text, and refuse out-of-spec input.
- Be **human-readable** JSON for debuggability.
- Use **standard, widely-implemented primitives**: JSON Schema 2020-12, JSON-LD 1.1, Ed25519 (RFC 8032), RFC 8785 (JCS).

### 4.2 Non-goals
- Real-time chat transport (covered by Model Context Protocol).
- Tool/resource invocation (covered by MCP).
- Encryption-at-rest (out of scope; each store does its own).
- Federated identity (subjects use DIDs but Phase 1 supports only `did:key`).
- Schema evolution beyond v0.x semver (future versions).

## 5. Data Model

A context document is a JSON object with the following top-level fields. **Bold** fields are REQUIRED.

### 5.1 Document envelope

| Field | Type | Required | Notes |
|---|---|---|---|
| `@context` | string \| array | MUST | Always includes `"https://contextprotocol.org/ns/v0.1"`. |
| `context_protocol_version` | string | MUST | Semver. v0.1.0 documents MUST set `"0.1.0"`. |
| `subject` | object | MUST | See §5.2. |
| `issuer` | object | MUST | See §5.3. |
| `memories` | array of objects | MUST | See §5.4. MAY be empty. |
| `signature` | object | MUST | See §8. |
| `schema_version_log` | array of objects | SHOULD | History of upgrades; see §9.4. |
| `extensions` | object | MAY | Vendor extensions; consumers MUST ignore unknown keys. |

### 5.2 Subject

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | MUST | A DID per [W3C DID Core]. v0.1 MUST accept at minimum `did:key`. |
| `type` | enum | MUST | One of `"person"`, `"organization"`, `"agent"`. |
| `display_name` | string | MAY | Free-text label. Sensitive — see §12. |

### 5.3 Issuer

| Field | Type | Required | Notes |
|---|---|---|---|
| `tool` | string | MUST | Conventionally `<name>@<version>`, e.g. `"context-capital@1.0.0"`. |
| `exported_at` | string | MUST | ISO 8601 timestamp, UTC, with fractional seconds OPTIONAL. |
| `verifier_hint` | string | MAY | URI from which the importer MAY fetch verification material (e.g., the issuer's signing-key DID document). |

### 5.4 Memory entries

Each entry in `memories[]` is a JSON object:

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | MUST | Stable, content-addressed identifier. RECOMMENDED format: `mem_<32-hex-of-sha256-of-canonical-content>`. |
| `kind` | enum | MUST | One of `"preference"`, `"fact"`, `"decision"`, `"project"`, `"workflow"`, `"skill"`. |
| `subject_id` | string | MUST | The DID this memory describes; usually equals the document-level `subject.id`. |
| `predicate` | string | MUST | Short kebab-case relationship, e.g. `prefers`, `uses`, `works-on`, `decided`, `rejected`, `learned`. Conformance suite enumerates a recommended starter vocabulary; non-listed predicates are PERMITTED. |
| `object` | object | MUST | See §5.5. |
| `confidence` | number | MUST | `[0.0, 1.0]`. The exporter's confidence in the memory's accuracy. |
| `provenance` | object | MUST | See §5.6. |
| `validity` | object | SHOULD | See §5.7. Default: validity-unbounded (`{ "valid_from": <issuer.exported_at>, "valid_until": null }`). |
| `sensitivity` | enum | MUST | One of `"public"`, `"work"`, `"personal"`, `"secret"`. |
| `permissions` | object | MAY | See §5.8. Default: no per-AI restrictions. |

### 5.5 `object`

The free-form value the predicate relates the subject to.

| Field | Type | Required | Notes |
|---|---|---|---|
| `value` | string \| object | MUST | The memory payload. Strings are RECOMMENDED for v0.1; structured objects MAY be used but the importer MAY treat them opaquely. |
| `type` | string | MAY | Optional type hint, e.g. `"tool"`, `"language"`, `"project"`, `"role"`, `"company"`. |

### 5.6 `provenance`

| Field | Type | Required | Notes |
|---|---|---|---|
| `source` | string | MUST | Format `<vendor>:<artifact-id>`, e.g. `"chatgpt:conv_abc123"`, `"claude:conv_xyz"`, `"manual:<uuid>"`, `"import:<issuer.tool>"`. |
| `extracted_at` | string | MUST | ISO 8601 UTC. |
| `raw_excerpt` | string | MAY | A short verbatim excerpt that grounds the memory. Importers MUST treat this as untrusted text — see §11. |
| `imported` | boolean | MAY | `true` if this memory was created by importing another context document; `false` otherwise. |
| `import_source` | string | MAY | When `imported = true`, MUST be set to the source document's `issuer.tool`. |
| `model` | string | MAY | When the memory was produced by extraction, the model identifier, e.g. `"anthropic/claude-sonnet-4-7"`. |

### 5.7 `validity`

| Field | Type | Required | Notes |
|---|---|---|---|
| `valid_from` | string | SHOULD | ISO 8601 UTC. |
| `valid_until` | string \| null | MAY | ISO 8601 UTC or `null` (open-ended). |
| `superseded_by` | string \| null | MAY | Memory `id` of the entry that replaces this one. Importers MUST hide superseded entries from default queries. |

### 5.8 `permissions`

| Field | Type | Required | Notes |
|---|---|---|---|
| `allow` | array of strings | MAY | A list of client identifiers permitted to see this memory. |
| `deny` | array of strings | MAY | A list of client identifiers MUST NOT see this memory. `deny` wins on conflict. |

Permissions in a context document are **advisory**: an importer's local permission system overrides them. See §11.

## 6. JSON Schema (Normative)

The normative JSON Schema is published at `https://contextprotocol.org/schema/v0.1.json` (canonical) and reproduced here informatively. Conformance is determined by the canonical URL.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://contextprotocol.org/schema/v0.1.json",
  "title": "Context Protocol v0.1.0",
  "type": "object",
  "required": ["@context", "context_protocol_version", "subject", "issuer", "memories", "signature"],
  "properties": {
    "@context": { "oneOf": [{ "type": "string" }, { "type": "array", "items": { "type": "string" } }] },
    "context_protocol_version": { "type": "string", "const": "0.1.0" },
    "subject": {
      "type": "object",
      "required": ["id", "type"],
      "properties": {
        "id": { "type": "string", "pattern": "^did:[a-z0-9]+:.+" },
        "type": { "enum": ["person", "organization", "agent"] },
        "display_name": { "type": "string" }
      },
      "additionalProperties": false
    },
    "issuer": {
      "type": "object",
      "required": ["tool", "exported_at"],
      "properties": {
        "tool": { "type": "string" },
        "exported_at": { "type": "string", "format": "date-time" },
        "verifier_hint": { "type": "string", "format": "uri" }
      },
      "additionalProperties": false
    },
    "memories": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "kind", "subject_id", "predicate", "object", "confidence", "provenance", "sensitivity"],
        "properties": {
          "id": { "type": "string", "pattern": "^mem_[a-f0-9]{32}$" },
          "kind": { "enum": ["preference", "fact", "decision", "project", "workflow", "skill"] },
          "subject_id": { "type": "string", "pattern": "^did:[a-z0-9]+:.+" },
          "predicate": { "type": "string", "minLength": 1, "maxLength": 64 },
          "object": {
            "type": "object",
            "required": ["value"],
            "properties": {
              "value": {},
              "type": { "type": "string" }
            }
          },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
          "provenance": {
            "type": "object",
            "required": ["source", "extracted_at"],
            "properties": {
              "source": { "type": "string" },
              "extracted_at": { "type": "string", "format": "date-time" },
              "raw_excerpt": { "type": "string", "maxLength": 4096 },
              "imported": { "type": "boolean" },
              "import_source": { "type": "string" },
              "model": { "type": "string" }
            }
          },
          "validity": {
            "type": "object",
            "properties": {
              "valid_from": { "type": "string", "format": "date-time" },
              "valid_until": { "type": ["string", "null"], "format": "date-time" },
              "superseded_by": { "type": ["string", "null"] }
            }
          },
          "sensitivity": { "enum": ["public", "work", "personal", "secret"] },
          "permissions": {
            "type": "object",
            "properties": {
              "allow": { "type": "array", "items": { "type": "string" } },
              "deny": { "type": "array", "items": { "type": "string" } }
            }
          }
        }
      }
    },
    "signature": {
      "type": "object",
      "required": ["alg", "value", "public_key"],
      "properties": {
        "alg": { "const": "ed25519" },
        "value": { "type": "string", "pattern": "^[A-Za-z0-9+/=]+$" },
        "public_key": { "type": "string" },
        "canonicalization": { "const": "jcs" }
      }
    },
    "schema_version_log": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["from", "to", "at"],
        "properties": {
          "from": { "type": "string" },
          "to": { "type": "string" },
          "at": { "type": "string", "format": "date-time" },
          "by": { "type": "string" }
        }
      }
    },
    "extensions": { "type": "object" }
  },
  "additionalProperties": false
}
```

A consumer SHOULD validate `additionalProperties: false` at the document root to reject unknown top-level fields. Unknown keys inside `extensions` MUST be tolerated.

## 7. JSON-LD `@context`

The canonical JSON-LD context is published at `https://contextprotocol.org/ns/v0.1`. Importers MAY use it to map memory entries into RDF/graph stores. The mapping is informative for v0.1.

A minimal `@context` is reproduced here:

```json
{
  "@context": {
    "@version": 1.1,
    "cp": "https://contextprotocol.org/ns/v0.1#",
    "subject": "cp:subject",
    "memories": "cp:memories",
    "predicate": "cp:predicate",
    "object": "cp:object",
    "confidence": { "@id": "cp:confidence", "@type": "xsd:decimal" },
    "provenance": "cp:provenance",
    "extracted_at": { "@id": "cp:extracted_at", "@type": "xsd:dateTime" },
    "sensitivity": "cp:sensitivity"
  }
}
```

Implementations MUST NOT depend on the JSON-LD form for conformance; the canonical structure is the JSON Schema.

## 8. Signing

### 8.1 Algorithm
Implementations MUST use **Ed25519** signatures per [RFC 8032]. The signature object MUST have `alg: "ed25519"`.

### 8.2 Canonicalization
Before signing, the document MUST be canonicalized via **JSON Canonicalization Scheme** ([RFC 8785]). The `signature` field itself MUST be removed from the canonical form before hashing.

```
canonical_bytes = JCS( document_without_signature )
signature_value = Ed25519_sign(private_key, canonical_bytes)
```

### 8.3 `signature` object

| Field | Required | Notes |
|---|---|---|
| `alg` | MUST | Constant `"ed25519"`. |
| `value` | MUST | Base64-encoded 64-byte Ed25519 signature. |
| `public_key` | MUST | Base64-encoded 32-byte Ed25519 public key. RECOMMENDED format follows the subject's DID `did:key` representation. |
| `canonicalization` | MUST | Constant `"jcs"`. |

### 8.4 Verification
Verifiers MUST:
1. Parse the JSON.
2. Remove the `signature` field from the parsed document.
3. Apply JCS to produce canonical bytes.
4. Verify the signature against `signature.public_key`.
5. Confirm that `signature.public_key` matches the subject's `did:key` (when `subject.id` is a `did:key`).

Verification failure MUST abort import with no side effects (FR-6.1).

## 9. Versioning

### 9.1 Semver
This specification follows semantic versioning:
- **PATCH** (0.1.x → 0.1.y): editorial fixes; no breaking changes.
- **MINOR** (0.x → 0.y): additive changes; older documents MUST still validate.
- **MAJOR** (0.y → 1.0 or 1.0 → 2.0): breaking changes; importer MAY refuse.

### 9.2 Document version field
The `context_protocol_version` field carries the exact version that produced the document.

### 9.3 Importer policy
Importers SHOULD accept the exact major.minor they implement and one minor version lower. Importers MUST refuse documents with a higher major version.

### 9.4 Schema version log
Documents that have been upgraded (e.g., from v0.1.0 to v0.2.0) SHOULD record each migration in `schema_version_log[]`:

```json
{ "from": "0.1.0", "to": "0.2.0", "at": "2027-03-12T00:00:00Z", "by": "context-capital@1.5.0" }
```

### 9.5 Deprecation policy
A field is **deprecated** when announced as such in the spec; it remains REQUIRED to be tolerated for at least two MINOR releases. Removal requires a MAJOR bump.

## 10. Conformance

### 10.1 Conformance levels
A tool MAY claim conformance at one of four levels:

- **Import.** Reads documents; validates schema; verifies signatures; honors sensitivity; sanitizes raw text per §11.
- **Export.** Produces documents that validate; signs them correctly; populates required fields.
- **Round-trip.** Both Import and Export, with the additional property that exporting a previously-imported document produces a document whose memories validate identically (modulo `provenance.imported` and `issuer`).
- **Full.** Round-trip plus all OPTIONAL features (validity, supersession, permissions, schema_version_log, extensions).

### 10.2 Test suite
Conformance is determined by passing the corresponding section of the v0.1.0 conformance suite ([`conformance-suite.md`](./conformance-suite.md)). Implementations MAY self-test; independent attestation is RECOMMENDED but not REQUIRED for v0.1.

### 10.3 Reporting
Conformance claims SHOULD include: implementation name + version, level claimed, suite version run, suite results URL or transcript.

## 11. Security Considerations

### 11.1 Prompt injection on import (normative)
A context document is, by definition, **data authored elsewhere** (possibly by a hostile party who controlled the original chat session). Importers MUST treat every string field inside `memories[].object.value` and `memories[].provenance.raw_excerpt` as **untrusted input** and apply sanitization before any LLM ever reads it.

At minimum, importers MUST:

1. **Detect and neutralize directive-shaped text** that targets a model's behavior rather than describing the subject. Phrases such as `"ignore previous instructions"`, `"system:"`, `"you are now"`, `"override your guidelines"`, and similar patterns MUST be either: (a) refused entirely, (b) replaced with a sanitization marker, or (c) wrapped so the consuming model is told *the user did not write this; it is data*.
2. **Tag every imported memory** with `provenance.imported = true` and `provenance.import_source = <issuer.tool>` so downstream models can distinguish imported memories from first-party.
3. **Default-deny missing sensitivity.** A memory whose `sensitivity` field is absent, null, or not one of the four enumerated values MUST be rejected.
4. **Refuse on signature failure** (§8.4). No fallback to "accept unsigned."

Failure to implement §11.1 MUST cause an implementation to fail Conformance Level "Import."

### 11.2 Permissions are advisory
Document-level `permissions` (§5.8) MUST be treated as advisory hints, not as security boundaries. The importer's local permission engine (`F-8` in the SRS) is authoritative.

### 11.3 Signature stripping
Implementations MUST NOT permit a "convenience" mode that imports unsigned documents. v0.1.0 is signed-only.

### 11.4 Key compromise
Subjects whose signing keys are compromised SHOULD revoke them by rotating to a new DID and re-exporting. v0.1 does not specify a revocation registry; a future minor revision MAY.

### 11.5 Large-payload denial of service
Importers SHOULD enforce a maximum document size (RECOMMENDED 50 MB) and a maximum `memories[]` length (RECOMMENDED 100,000) to bound parsing cost.

### 11.6 Side-channel leakage
Implementations SHOULD NOT include verbose error messages that echo unsanitized untrusted content. Error messages MUST sanitize the same way as memory text.

## 12. Privacy Considerations

### 12.1 Sensitivity tags are normative
`sensitivity = "secret"` memories MUST NOT cross the export boundary unless the exporter has explicit user consent for that specific export (§FR-5.2). Importers MUST honor sensitivity tags in any onward sharing.

### 12.2 Display name is sensitive
`subject.display_name` SHOULD be omitted when not strictly needed. A subject's pseudonymous `did:key` carries no PII; the display name re-introduces it.

### 12.3 Provenance leak
`provenance.raw_excerpt` is convenient for debuggability but reveals more than the structured memory does. Exporters SHOULD provide a flag to strip raw excerpts on export.

### 12.4 Inferred-data status
Most memories produced by this protocol are **inferred from** vendor chat data, not raw vendor data. Under GDPR Article 20 ([WP242] guidance), inferred data is **outside the right to data portability**. This protocol does not depend on any regulation; it operates as a voluntary cooperative format.

### 12.5 Right to be forgotten
Implementations MUST support per-memory and per-subject deletion. Deletion of an exported document is the user's responsibility; the protocol cannot reach across previously distributed copies.

## 13. References

### 13.1 Normative
- [RFC 2119] — Key words for use in RFCs to Indicate Requirement Levels.
- [RFC 8174] — Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words.
- [RFC 8032] — Edwards-Curve Digital Signature Algorithm (EdDSA).
- [RFC 8785] — JSON Canonicalization Scheme (JCS).
- [JSON Schema 2020-12] — `https://json-schema.org/draft/2020-12/schema`.
- [JSON-LD 1.1] — `https://www.w3.org/TR/json-ld11/`.
- [W3C DID Core] — `https://www.w3.org/TR/did-core/`.
- [did:key] — `https://w3c-ccg.github.io/did-method-key/`.

### 13.2 Informative
- [`../proposal-v2.md`](../proposal-v2.md) — product context.
- [`../market-research.md`](../market-research.md) — competitive landscape, including Plurality Network.
- [`../srs.md`](../srs.md) — Phase-1 reference-implementation requirements.
- [MCP] — Model Context Protocol, `https://modelcontextprotocol.io`.
- [WP242] — Article 29 Working Party Guidelines on the Right to Data Portability.

## 14. Open Questions / Non-decisions

These are deliberately deferred to v0.2.0:

1. **DID methods beyond `did:key`.** v0.1 MUST support `did:key`; `did:web` is OPTIONAL. Other methods (`did:ion`, `did:plc`, etc.) deferred.
2. **Revocation registry.** §11.4 leaves revocation undefined. A simple status-list approach is candidate for v0.2.
3. **Federated context exchange.** v0.1 is point-to-point: A exports a file, B imports it. Real-time exchange is out of scope.
4. **Selective disclosure.** Cryptographic selective disclosure (BBS+ signatures, etc.) deferred.
5. **Conflict-resolution policy.** §FR-6.5 of the SRS leaves resolution to the importer (no last-write-wins); a possible v0.2 extension is a declarative resolution policy block.
6. **Embeddings.** v0.1 does not standardize embedding fields. Implementations MAY add embeddings via `extensions`. Standardization is a candidate for v0.2 once a community baseline emerges.

---

## Appendix A — Minimal example

```json
{
  "@context": "https://contextprotocol.org/ns/v0.1",
  "context_protocol_version": "0.1.0",
  "subject": {
    "id": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH",
    "type": "person"
  },
  "issuer": {
    "tool": "context-capital@1.0.0",
    "exported_at": "2026-06-18T10:00:00Z"
  },
  "memories": [
    {
      "id": "mem_3a7b4c5d6e7f8091a2b3c4d5e6f70819",
      "kind": "preference",
      "subject_id": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH",
      "predicate": "prefers",
      "object": { "value": "PyTorch", "type": "tool" },
      "confidence": 0.92,
      "provenance": {
        "source": "chatgpt:conv_a1b2c3",
        "extracted_at": "2026-06-18T09:55:00Z",
        "raw_excerpt": "I prefer PyTorch because my deployment stack uses it.",
        "model": "anthropic/claude-sonnet-4-7"
      },
      "validity": { "valid_from": "2026-06-18T09:55:00Z", "valid_until": null, "superseded_by": null },
      "sensitivity": "work"
    }
  ],
  "signature": {
    "alg": "ed25519",
    "value": "<base64-64-bytes>",
    "public_key": "<base64-32-bytes>",
    "canonicalization": "jcs"
  }
}
```

## Appendix B — Authoring conventions

- Field names MUST be `snake_case`.
- All timestamps MUST be ISO 8601 UTC (`Z` suffix RECOMMENDED).
- Strings MUST be UTF-8.
- Numbers MUST be JSON numbers (not stringified).
- `null` is permitted only where explicitly allowed by the schema.

## Document control

- **Next review:** Upon first external implementor signing up to conformance.
- **Change policy:** Editorial PATCH changes do not require external review. MINOR or MAJOR changes MUST be discussed in a public RFC.
- **Conformance suite version:** This spec is paired with `conformance-suite.md` v0.1.0.
