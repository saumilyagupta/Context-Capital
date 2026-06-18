# Test Plan — Context Capital Phase 1

| | |
|---|---|
| **Document** | Test Plan |
| **Version** | Draft v0.1 |
| **Date** | 2026-06-18 |
| **Status** | Draft |
| **Companion docs** | [`../srs.md`](../srs.md), [`../sdd.md`](../sdd.md), [`../security/threat-model.md`](../security/threat-model.md), [`../spec/conformance-suite.md`](../spec/conformance-suite.md) |

---

## 1. Testing Philosophy

- **Behavior-focused.** Tests assert on observable outputs (HTTP responses, on-disk artifacts, MCP responses), not on implementation internals.
- **Adversarial by default.** Every security-critical path has at least one adversarial test alongside the golden-path test.
- **TDD for the four security-critical layers.** Extraction, sanitization, crypto, and schema have tests written first.
- **No mocks for security boundaries.** Crypto + sanitization tests run against the real implementations; only external APIs (LLM) are mocked.
- **Determinism.** All tests pass with `temperature=0` extraction; flaky tests are quarantined within 24 h.

## 2. Test pyramid

```
                ▲  Acceptance / E2E
                │  ▲  Integration
                │  │  ▲  Unit
        (few)   │  │  │
                │  │  │
                │  │  │      (many)
                ▼  ▼  ▼
```

### 2.1 Unit tests
- **Coverage target:** ≥ 80 % overall; ≥ 90 % in `extract`, `sanitize`, `crypto`, `schema`.
- **Tools:** `pytest` + `pytest-asyncio` for Python; `vitest` for TypeScript.
- **Scope:** pure functions, schema validators, sanitizer pattern matching, JCS canonicalization, Argon2 wrapper, Ed25519 sign/verify.
- **Fixtures:** ship a `tests/fixtures/` directory with small JSON snippets per behavior.

### 2.2 Integration tests
- **Scope:** per pipeline stage end-to-end with a real local Postgres (via testcontainers or a Docker Compose dev stack) and real SQLite.
- **Tools:** `pytest`, `httpx` for REST, `mcp` SDK in client mode for MCP-server tests.
- **What to test:**
  - Capture parses a real ChatGPT export fixture.
  - Capture parses a real Claude export fixture.
  - Extraction with a mocked LLM client returns expected memories.
  - Storage round-trips encrypted rows.
  - MCP server returns memories under a real scope grant.
  - Audit log hash chain reconstructs after random insert order.

### 2.3 End-to-end tests
- **Scope:** the golden capture → extract → export → import → verify round-trip on real-but-anonymized export fixtures.
- **Tools:** `pytest` driving the CLI directly; Playwright for the extension UI (`@playwright/test`).
- **Cases:**
  - `e2e-golden-chatgpt`: capture an anonymized ChatGPT export of ≥ 200 conversations, extract, export, import into a clean instance, assert memory count + content parity (modulo provenance.imported).
  - `e2e-golden-claude`: same for Claude.
  - `e2e-extension-lock-unlock`: extension UI flow for unlock, capture, lock — verified via Playwright.
  - `e2e-mcp-claude-desktop` (manual until automated): script that boots a local MCP server and exercises `query_memories` from a scripted MCP client; counts memories returned.

### 2.4 Conformance tests
- **Tool:** the conformance suite from [`../spec/conformance-suite.md`](../spec/conformance-suite.md).
- **Levels gated for ship:** L3.
- **Fixtures:** under `tests/conformance/`.

### 2.5 Performance tests
- **Tool:** `k6` or `locust` for REST; bespoke `pytest`-asyncio benchmarks for extraction.
- **SLOs to verify (SRS §5.3):**
  - Capture 100 MB ChatGPT export in < 30 s.
  - Extraction throughput ≥ 500 memories/hour with cached prefix.
  - `query_memories` p50 < 100 ms, p95 < 500 ms on 100k memories.
  - Export 10k memories in < 5 s.
  - MCP cold-start < 2 s.
- **Reference machine:** 16 GB RAM, M-series ARM (or equivalent x86-64).

### 2.6 Adversarial tests
- **Drivers:** the conformance suite's adversarial corpus (§2.3 of conformance-suite.md) is the headline. Additional tests:
  - Random-bytes fuzzing of the parser (`hypothesis`).
  - Unicode-trick fuzzing of `display_name` and `raw_excerpt`.
  - Repeated wrong-passphrase brute attempts to verify lock-out timing.
  - Concurrent capture + extract + query loads to verify scope filter never leaks.

## 3. CI gates

A pull request MUST pass all of the following before merge:

| Gate | Tool | Threshold |
|---|---|---|
| Lint | `ruff`, `eslint` | zero errors |
| Format | `black`, `prettier` | clean |
| Types | `mypy --strict`, `tsc --strict` | zero errors |
| Unit | `pytest`, `vitest` | all pass; coverage ≥ 80 % |
| Integration | `pytest -m integration` | all pass |
| Conformance L1+L2 | suite driver | all pass |
| Dependency audit | `pip-audit`, `npm audit` | zero HIGH/CRITICAL |
| Build | per-package build | clean |

Nightly:

| Job | Tools | Action |
|---|---|---|
| Conformance L3 | suite driver | report; fail nightly if regressed |
| Perf SLO | `k6`/`locust` + bench | track p50/p95 over time |
| Adversarial fuzz | `hypothesis` | run for 30 minutes |
| Real-data E2E | Playwright + CLI | requires fixture corpus update gate |

## 4. Failure-mode coverage matrix

Every SDD §6 failure mode MUST have at least one test. Sample mapping:

| SDD failure | Test ID | Tier |
|---|---|---|
| Capture parser — malformed export | `tests/capture/test_parse_malformed.py::test_partial_json_rejected` | Unit |
| Sanitizer — directive fires | `tests/sanitize/test_directive.py::test_ignore_previous_wrapped` | Unit |
| Extraction — LLM timeout | `tests/extract/test_extraction.py::test_retries_then_marks_failed` | Integration (mocked LLM) |
| Storage — Postgres unreachable | `tests/storage/test_unavailable.py::test_storage_down_error` | Integration |
| Crypto — wrong passphrase | `tests/crypto/test_throttle.py::test_five_attempts_then_cooldown` | Unit |
| Signing — key missing | `tests/spec/test_export.py::test_missing_signing_key` | Integration |
| Import — bad signature | `tests/spec/test_import.py::test_bad_sig_no_side_effects` | Integration |
| Import — schema fail | conformance SV-02..SV-12 | Conformance |
| MCP — scope denied | `tests/mcp/test_scope.py::test_outside_scope_denied` | Integration |
| Audit — hash break | `tests/audit/test_chain.py::test_verify_detects_break` | Integration |

## 5. Regression strategy

- **Every shipped bug gets a regression test before the fix merges.**
- A pull-request template requires the author to point at the test that would have caught the bug.
- The conformance suite is the durable regression net for spec-level behavior.

## 6. Acceptance criteria for Phase-1 ship

These map 1:1 to SRS §7:

- [ ] **G-1** Round-trip on real ChatGPT + Claude exports: pass.
- [ ] **G-2** Sanitization corpus ≥ 20 payloads: 100 % pass.
- [ ] **G-3** MCP integration with Claude Desktop: verified manually.
- [ ] **G-4** External implementation passes L3 against our exports: verified once.
- [ ] **G-5** Lock/unlock behavior: pass.
- [ ] **Q-1** Coverage gate: pass.
- [ ] **Q-2** Type-check: pass.
- [ ] **Q-3** Dependency audit: clean.
- [ ] **Q-4** Threat-model mitigations: each implemented or explicitly accepted.
- [ ] **P-1** Performance SLOs: pass on the reference machine.

## 7. Test data management

- **Real chat exports** are sensitive; the project repo MUST NOT contain a user's real export. Test fixtures are synthetic or anonymized.
- **Anonymization process:** scripted (`tools/anonymize_export.py`) to strip names, emails, URLs, and rename projects to placeholders. The anonymized fixture is checked in alongside its anonymization seed for reproducibility.
- **Adversarial corpus:** lives under `tests/conformance/fixtures/sa/` and is the canonical reference for the threat-model attack tree.
- **Encrypted fixtures:** none. Crypto tests use ephemeral keys generated at test setup; nothing persistent.

## 8. Local dev loop

```bash
# fast loop (under 30 s)
$ make test-unit

# full loop (under 5 min)
$ make test

# include perf
$ make test-perf
```

## 9. Tooling decisions (see ADRs)

| Concern | Choice | ADR |
|---|---|---|
| Python test runner | `pytest` | — (default) |
| Property-based testing | `hypothesis` | — |
| Browser E2E | Playwright | — |
| Perf | `k6` (REST) + bespoke async bench (extraction) | — |
| Coverage | `coverage.py`, `c8` | — |

## 10. Open questions

1. **Real LLM in CI?** Probably not (cost + flakiness). Mock everywhere; cover one nightly real-LLM smoke run.
2. **GPU-accelerated tests?** Out of Phase 1 (no GPU dependency).
3. **Property-based testing for the schema.** Worth adding before GA; not blocker for L3 ship.

## 11. References

- [`../srs.md`](../srs.md) — requirements with `F-*`, `NFR-*`, `G-*`, `Q-*`, `P-*` IDs.
- [`../sdd.md`](../sdd.md) §6 — failure modes (matrix in §4 above).
- [`../security/threat-model.md`](../security/threat-model.md) §3.3 — adversarial corpus.
- [`../spec/conformance-suite.md`](../spec/conformance-suite.md) — conformance levels.
