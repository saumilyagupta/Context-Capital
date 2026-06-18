# ADR-003: Storage — Postgres 16 + pgvector primary, SQLite fallback

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-18 |
| **Deciders** | Phase-1 engineering lead |
| **Tags** | storage, vector, fallback |

## Context and Problem Statement

The Phase-1 store needs to hold encrypted memory rows, an append-only audit log, and (optionally) vector embeddings for semantic recall. Two deployment shapes matter: developer/team setups (Docker, real DB) and single-user laptops (no infrastructure dependencies).

## Decision Drivers

- Vector search is desirable now and required by Phase 2.
- Single-user install must work with **zero infra setup**.
- Append-only audit log requires DB-level guarantees (triggers, role separation).
- JSONB / JSON support needed for vendor `raw` envelopes.
- We don't want to maintain two divergent schemas.

## Considered Options

1. **SQLite only** — zero-config, perfect for single user.
2. **Postgres only** — no fallback; bootstrap script installs Docker if absent.
3. **Postgres primary + SQLite fallback** — same schema, parameterized DDL.
4. **Dedicated vector DB (Qdrant, Milvus)** + a relational DB.
5. **DuckDB** — embedded, fast, JSON-friendly.

## Decision Outcome

**Chosen: Option 3 — Postgres 16 + pgvector as primary, SQLite 3.42 + `sqlite-vec` as the fallback.**

### Consequences

- ✅ Both shapes covered: devs/teams use Postgres; lone users get SQLite with no install hassle.
- ✅ One logical schema with explicit type adaptations (`data-model.md` §7).
- ✅ pgvector at Postgres and `sqlite-vec` for SQLite means we keep vector recall in both modes.
- ⚠️ Slight maintenance cost for the two-backend layer; the access layer (sqlmodel + a small adapter) hides it.
- ❌ DuckDB's JSON ergonomics are tempting; we lose them. Revisit if Phase-2 analytics demand it.

## Pros and Cons of the Options

### Option 1 — SQLite only
- ✅ Zero setup.
- ❌ Vector indexes are weaker; harder to scale for teams; no role separation for audit-log enforcement.

### Option 2 — Postgres only
- ✅ One backend; mature; everything we need.
- ❌ Installing Postgres on a non-technical user's laptop kills onboarding.

### Option 3 — Both (chosen)
- ✅ Best onboarding + best capability.
- ❌ Two-backend test matrix.

### Option 4 — Dedicated vector DB
- ✅ Best-in-class vector search.
- ❌ Extra service to install; overkill for Phase 1 sizes (≤ 100k memories).

### Option 5 — DuckDB
- ✅ Single binary, columnar, fast JSON.
- ❌ Vector ecosystem less mature; trigger-based audit-log enforcement awkward.

## More Information

- `data-model.md` — the schema realization.
- `data-model/schema.sql` — Postgres DDL.
- SRS §NFR-PRF-3 — query latency targets.
- threat model §2.5 — what we protect at this layer.
