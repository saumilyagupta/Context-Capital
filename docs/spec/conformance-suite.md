# Context Protocol — Conformance Suite v0.1.0

| | |
|---|---|
| **Document** | Conformance Suite |
| **Spec version** | v0.1.0 |
| **Suite version** | v0.1.0 |
| **Date** | 2026-06-18 |
| **Status** | Draft |
| **Paired with** | [`context-protocol-v0.1.md`](./context-protocol-v0.1.md) |

This document describes what an implementation must do to claim **Conformance** with Context Protocol v0.1.0. It enumerates levels, test categories, oracles, and reporting requirements. The corresponding test fixtures live in the Context Capital reference repository under `tests/conformance/` (to be created during implementation).

---

## 1. Conformance levels

Implementations MAY claim any of four levels. Each level builds on the previous.

| Level | Required capabilities |
|---|---|
| **L1. Import** | Read a `context.json`, verify signature, validate against the v0.1 JSON Schema, sanitize per spec §11.1, honor `sensitivity`, refuse on signature or schema failure. |
| **L2. Export** | Produce a `context.json` that validates, with correct canonicalization and Ed25519 signature; populate all REQUIRED fields. |
| **L3. Round-trip** | L1 + L2 with the property that an imported-then-exported memory validates identically (modulo `provenance.imported` and `issuer`). |
| **L4. Full** | L3 + all OPTIONAL features: `validity`, `superseded_by`, document-level `permissions`, `schema_version_log`, `extensions` (must be tolerated). |

## 2. Test categories

### 2.1 Schema validation (L1, L2)

| ID | Test | Expected |
|---|---|---|
| SV-01 | Minimal valid document (Appendix A of spec) | accept |
| SV-02 | Missing `signature` | reject |
| SV-03 | Wrong `context_protocol_version` (`"0.2.0"`) | accept if importer claims v0.2 or higher; otherwise reject |
| SV-04 | Memory with missing `sensitivity` | reject |
| SV-05 | Memory with invalid `kind` (`"opinion"`) | reject |
| SV-06 | Memory with `confidence = 1.5` | reject |
| SV-07 | Memory with non-DID `subject_id` (`"alice@example.com"`) | reject |
| SV-08 | Unknown top-level key (`"custom_field"`) | reject (spec §6) |
| SV-09 | Unknown key inside `extensions` | tolerate (spec §5.1) |
| SV-10 | Predicate longer than 64 chars | reject |
| SV-11 | `raw_excerpt` longer than 4096 chars | reject |
| SV-12 | Document size > 50 MB | reject (recommended cap, spec §11.5) |

### 2.2 Signing (L1, L2)

| ID | Test | Expected |
|---|---|---|
| SG-01 | Correctly signed document | verify ok |
| SG-02 | Bit-flipped signature | reject |
| SG-03 | Signature over the document *with* the `signature` field still present | reject |
| SG-04 | Wrong `alg` (`"hs256"`) | reject |
| SG-05 | `signature.public_key` does not match `subject.id` DID | reject |
| SG-06 | Missing `canonicalization` field | reject |
| SG-07 | JCS canonicalization producing different output than reference implementation | exporters MUST match reference output for a fixed input (regression test) |

### 2.3 Sanitization (L1) — adversarial corpus

The full corpus is described in [`../security/threat-model.md`](../security/threat-model.md) §3.3. Required minimum: ≥ 20 payloads spanning categories G.1–G.5. Each is one test:

- `SA-DIR-01..05` — direct directive injection in five fields.
- `SA-IND-01..04` — indirect injection.
- `SA-SMG-01..03` — schema smuggling (oversized, Unicode tricks, confusable values).
- `SA-PRV-01..03` — provenance spoofing.
- `SA-TRS-01..03` — trust-shopping.
- `SA-DOS-01..02` — DoS payloads.

**Oracle:** the importer MUST either (a) reject the document, or (b) accept it with every problematic field replaced or wrapped per spec §11.1.1, with the resulting memory's `provenance.sanitization_trace` listing the pattern IDs that fired. **Silent acceptance with the original payload intact is a FAIL.**

### 2.4 Provenance preservation (L1, L3)

| ID | Test | Expected |
|---|---|---|
| PP-01 | Imported memory has `provenance.imported = true` even if the document said `false` | importer MUST overwrite |
| PP-02 | `provenance.import_source` set to `issuer.tool` | required |
| PP-03 | After round-trip (import then export), original `provenance.source` preserved | required |
| PP-04 | After round-trip, `provenance.model` preserved if present | required |

### 2.5 Versioning (L1)

| ID | Test | Expected |
|---|---|---|
| VR-01 | Document with `context_protocol_version: "0.0.9"` (lower minor) | accept (per spec §9.3) |
| VR-02 | Document with `context_protocol_version: "1.0.0"` (higher major) | reject |
| VR-03 | `schema_version_log` populated correctly after a future upgrade | tolerate (L1); produce correctly (L4 only) |

### 2.6 Sensitivity honoring (L1, L2)

| ID | Test | Expected |
|---|---|---|
| SH-01 | Import a memory tagged `secret`; default scope does NOT include `secret` | memory NOT visible via MCP `query_memories` |
| SH-02 | Export with default options (no `--include-secret`) excludes secret memories | required |
| SH-03 | Memory with missing `sensitivity` | reject (default-deny) |
| SH-04 | Memory with sensitivity outside the enumerated four | reject |

### 2.7 Round-trip (L3)

| ID | Test | Expected |
|---|---|---|
| RT-01 | Import a fixture document; re-export; diff memories | identical except `issuer` and `provenance.imported/import_source` |
| RT-02 | Round-trip preserves IDs (content-addressed) | required |
| RT-03 | Round-trip preserves `validity` fields | required (L4) |

### 2.8 Optional / extensions (L4)

| ID | Test | Expected |
|---|---|---|
| EX-01 | Document with `superseded_by` linking two memories | importer respects supersession when filtering |
| EX-02 | Document `permissions` advisory; importer's local scope wins | required (spec §11.2) |
| EX-03 | Schema version log entries preserved across upgrades | required |
| EX-04 | Unknown vendor extension under `extensions` | tolerated; ignored if namespace unknown |

## 3. Fixtures

The reference repo MUST ship fixtures for each test ID:

```
tests/conformance/
├── fixtures/
│   ├── sv/
│   │   ├── sv-01-valid.json
│   │   ├── sv-02-missing-signature.json
│   │   └── …
│   ├── sg/
│   ├── sa/        # adversarial corpus
│   ├── pp/
│   ├── vr/
│   ├── sh/
│   ├── rt/
│   └── ex/
└── run.py         # driver
```

Each fixture is a `context.json` paired with an `expected.json` describing the expected outcome:

```json
{
  "accept": false,
  "reason_code": "SCHEMA_INVALID",
  "violated_fields": ["memories[0].sensitivity"]
}
```

## 4. Running the suite

### 4.1 Reference driver

```bash
$ cc conformance run --target ./my-implementation --level L3
[L1.SV] 12/12 passed
[L1.SG]  7/7  passed
[L1.SA] 20/20 passed
[L1.PP]  4/4  passed
[L1.VR]  3/3  passed
[L1.SH]  4/4  passed
[L2.SV]  5/5  passed
[L2.SG]  4/4  passed
[L3.RT]  3/3  passed
PASS — L3 conformance.
```

Exit code is 0 for pass, 1 for fail, 2 for setup error.

### 4.2 What "passing" means

- **L1 pass** = every L1 test in §2.1–§2.6 passes.
- **L2 pass** = every L2 test in §2.1–§2.2 passes.
- **L3 pass** = L1 + L2 + §2.7.
- **L4 pass** = L3 + §2.8.

A skipped test does NOT count as passed. A test that crashes the implementation counts as failed.

### 4.3 Reporting

A conformance report SHOULD include:

- Implementation name, version, commit SHA.
- Date of the run.
- Suite version (v0.1.0).
- Per-category pass/fail counts.
- Hashes of the fixture directory used (so a third party can reproduce).
- Optional: link to a JSON-LD signed attestation (P2).

A non-conforming implementation that publishes an honest report is preferred to a "no statement" implementation.

## 5. Acceptance for the reference implementation

The Context Capital Phase-1 reference client MUST claim **L3** at ship and SHOULD claim **L4** before v1.0.0 of the spec. SRS §G-4 references this.

## 6. Suite evolution

- The suite version is independent of the spec version, but for v0.1.0 they align.
- Adding tests is a MINOR bump of the suite.
- Removing tests requires a MAJOR bump.
- New adversarial-corpus payloads MAY be added as MINOR; corpus shrinkage requires MAJOR.

## 7. Open questions

1. **Cross-language fixtures.** Should we ship platform-independent fixtures (no language assumptions)? Yes — JSON only.
2. **Performance bounds.** Should we add SLA tests (e.g., "must process 10k memories in 30s")? Deferred to v0.2.
3. **Negative fuzzing.** Add a property-based test bank? Recommended but not part of v0.1 mandatory suite.

## 8. References

- [`context-protocol-v0.1.md`](./context-protocol-v0.1.md) — the specification.
- [`../security/threat-model.md`](../security/threat-model.md) — adversarial corpus categories.
- [`../testing/test-plan.md`](../testing/test-plan.md) — how the reference implementation exercises this suite in CI.
