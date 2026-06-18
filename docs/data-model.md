# Data Model — Context Capital Phase 1

| | |
|---|---|
| **Document** | Data Model |
| **Version** | Draft v0.1 |
| **Date** | 2026-06-18 |
| **Status** | Draft |
| **DDL file** | [`data-model/schema.sql`](./data-model/schema.sql) |
| **Companion docs** | [`sdd.md`](./sdd.md), [`spec/context-protocol-v0.1.md`](./spec/context-protocol-v0.1.md) |

This document describes the persistent storage schema for Phase 1. Primary target: **Postgres 16 + pgvector**. Single-user fallback: **SQLite 3.42 + sqlite-vec** (the DDL file calls out type adaptations).

---

## 1. Design principles

1. **Envelope encryption.** Sensitive payloads (`*_enc` columns) are AEAD ciphertext using XChaCha20-Poly1305 under the user's DEK. Structural columns (`kind`, `predicate`, timestamps, hashes) are in plaintext so the database can index/search efficiently without leaking content.
2. **Content-addressed IDs.** `memories.id = mem_<hex(sha256(canonical_content))>`. Same canonical input → same ID. Enables deterministic deduplication and consistent IDs across vendors.
3. **Append-only audit.** Audit log uses an `INSERT`-only role plus a hash chain. No `UPDATE`/`DELETE` paths.
4. **Provenance, validity, sensitivity as first-class.** Every memory carries these as structured fields, not blobs.
5. **Multi-tenancy ready (P2).** Schema is single-user in Phase 1 but every row carries an implicit `subject_id`. A future tenant column adds itself without breaking changes.
6. **No vector lock-in.** `pgvector` is used; `sqlite-vec` is the SQLite analog. Embedding column is optional and additive.

## 2. ER diagram

```mermaid
erDiagram
    SUBJECTS ||--o{ CONTEXTS : owns
    SUBJECTS ||--o{ MEMORIES : describes
    CONTEXTS ||--o{ RAW_MESSAGES : contains
    CONTEXTS ||--o{ EXTRACTION_JOBS : produces
    MEMORIES ||--o| PROVENANCE : has
    MEMORIES ||--o| VALIDITY_PERIODS : valid_for
    MEMORIES ||--o{ VECTOR_EMBEDDINGS : indexed_by
    SUBJECTS ||--o{ SCOPE_GRANTS : grants
    SUBJECTS ||--o{ AUDIT_LOG_ENTRIES : observed_by

    SUBJECTS {
        text id PK
        text type
        bytea display_name_enc
        timestamptz created_at
    }
    CONTEXTS {
        uuid id PK
        text subject_id FK
        text source_vendor
        bytea export_file_hash
        timestamptz captured_at
        jsonb raw
    }
    RAW_MESSAGES {
        uuid id PK
        uuid context_id FK
        int seq
        text role
        bytea content_enc
        timestamptz created_at
    }
    MEMORIES {
        text id PK
        text subject_id FK
        text kind
        text predicate
        bytea value_enc
        text object_type
        numeric confidence
        text sensitivity
        timestamptz created_at
    }
    PROVENANCE {
        text memory_id PK_FK
        text source
        timestamptz extracted_at
        bytea raw_excerpt_enc
        boolean imported
        text import_source
        text model
        jsonb sanitization_trace
    }
    VALIDITY_PERIODS {
        text memory_id PK_FK
        timestamptz valid_from
        timestamptz valid_until
        text superseded_by FK
    }
    VECTOR_EMBEDDINGS {
        text memory_id PK_FK
        text model
        vector embedding
        timestamptz created_at
    }
    EXTRACTION_JOBS {
        uuid id PK
        uuid context_id FK
        int next_chunk
        int total_chunks
        text status
        text model
        timestamptz updated_at
    }
    SCOPE_GRANTS {
        uuid id PK
        text subject_id FK
        text scope_name
        text client_id
        text[] allowed_sensitivities
        text[] allowed_kinds
        text[] allowed_predicates
        timestamptz expires_at
        bytea signature
    }
    AUDIT_LOG_ENTRIES {
        bigserial id PK
        timestamptz at
        text actor
        text action
        text subject_id
        jsonb details
        text outcome
        bytea prev_hash
        bytea this_hash
    }
```

## 3. Tables

### 3.1 `subjects`
Identities the system stores memories about. Phase 1 stores exactly one (the user); the column makes Phase-2 multi-subject straightforward.

| Column | Type (Pg) | Notes |
|---|---|---|
| `id` | text PRIMARY KEY | DID, RECOMMENDED `did:key`. Format: `did:key:z…`. |
| `type` | text NOT NULL CHECK (type IN ('person','organization','agent')) | |
| `display_name_enc` | bytea NULL | AEAD ciphertext; nullable. |
| `created_at` | timestamptz NOT NULL DEFAULT now() | |

### 3.2 `contexts`
A "context" is a single capture event — one ChatGPT export or one Claude export.

| Column | Type (Pg) | Notes |
|---|---|---|
| `id` | uuid PRIMARY KEY DEFAULT gen_random_uuid() | |
| `subject_id` | text NOT NULL REFERENCES subjects(id) | |
| `source_vendor` | text NOT NULL CHECK (source_vendor IN ('chatgpt','claude','manual','import')) | |
| `export_file_hash` | bytea NOT NULL | SHA-256 of the source file (32 bytes). |
| `captured_at` | timestamptz NOT NULL DEFAULT now() | |
| `raw` | jsonb NOT NULL | Vendor envelope (excluding message bodies which live in `raw_messages`). |

Indexes:
- `(subject_id)`
- `(source_vendor, captured_at DESC)`
- UNIQUE `(subject_id, export_file_hash)` — same export ingested twice MUST be no-op.

### 3.3 `raw_messages`
The per-turn content captured from a vendor export.

| Column | Type (Pg) | Notes |
|---|---|---|
| `id` | uuid PRIMARY KEY DEFAULT gen_random_uuid() | |
| `context_id` | uuid NOT NULL REFERENCES contexts(id) ON DELETE CASCADE | |
| `seq` | int NOT NULL | Order within the conversation. |
| `role` | text NOT NULL CHECK (role IN ('user','assistant','tool','system','other')) | |
| `content_enc` | bytea NOT NULL | AEAD ciphertext of the message text. |
| `created_at` | timestamptz NOT NULL | Vendor's own timestamp when available, else capture time. |

Indexes:
- `(context_id, seq)`

### 3.4 `memories`
The product's core entity.

| Column | Type (Pg) | Notes |
|---|---|---|
| `id` | text PRIMARY KEY CHECK (id ~ '^mem_[a-f0-9]{32}$') | Content-addressed. |
| `subject_id` | text NOT NULL REFERENCES subjects(id) | |
| `kind` | text NOT NULL CHECK (kind IN ('preference','fact','decision','project','workflow','skill')) | |
| `predicate` | text NOT NULL | kebab-case; ≤ 64 chars. |
| `value_enc` | bytea NOT NULL | AEAD ciphertext of `object.value`. Stored as JSON (because value MAY be a string OR an object). |
| `object_type` | text NULL | Optional type hint from `object.type`. |
| `confidence` | numeric(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1) | |
| `sensitivity` | text NOT NULL CHECK (sensitivity IN ('public','work','personal','secret')) | |
| `created_at` | timestamptz NOT NULL DEFAULT now() | |

Indexes:
- `(subject_id, kind)`
- `(subject_id, predicate)`
- `(subject_id, sensitivity, created_at DESC)`

### 3.5 `provenance`
One row per memory.

| Column | Type (Pg) | Notes |
|---|---|---|
| `memory_id` | text PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE | |
| `source` | text NOT NULL | e.g. `chatgpt:conv_abc123` |
| `extracted_at` | timestamptz NOT NULL | |
| `raw_excerpt_enc` | bytea NULL | AEAD ciphertext of excerpt. |
| `imported` | boolean NOT NULL DEFAULT FALSE | |
| `import_source` | text NULL | Issuer of the source document if imported. |
| `model` | text NULL | Extraction model identifier. |
| `sanitization_trace` | jsonb NULL | Sanitizer pattern IDs that fired on import. |

Indexes:
- `(source)`
- `(imported)`

### 3.6 `validity_periods`
Optional temporal scope for memories.

| Column | Type (Pg) | Notes |
|---|---|---|
| `memory_id` | text PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE | |
| `valid_from` | timestamptz NULL | |
| `valid_until` | timestamptz NULL | NULL = open-ended. |
| `superseded_by` | text NULL REFERENCES memories(id) | |

Indexes:
- `(superseded_by)`
- partial: `(memory_id) WHERE valid_until IS NOT NULL`

### 3.7 `vector_embeddings`
Optional embedding for semantic recall.

| Column | Type (Pg) | Notes |
|---|---|---|
| `memory_id` | text NOT NULL REFERENCES memories(id) ON DELETE CASCADE | |
| `model` | text NOT NULL | e.g. `voyage-3`. |
| `embedding` | vector(1024) NOT NULL | dimensionality model-dependent. |
| `created_at` | timestamptz NOT NULL DEFAULT now() | |
| PRIMARY KEY (memory_id, model) | | One embedding per (memory, model). |

Indexes:
- pgvector ANN: `USING hnsw (embedding vector_cosine_ops)`.

SQLite fallback uses `sqlite-vec` virtual table; query layer abstracts the difference.

### 3.8 `extraction_jobs`
Resumability state for the extraction engine.

| Column | Type (Pg) | Notes |
|---|---|---|
| `id` | uuid PRIMARY KEY DEFAULT gen_random_uuid() | |
| `context_id` | uuid NOT NULL REFERENCES contexts(id) ON DELETE CASCADE | |
| `next_chunk` | int NOT NULL DEFAULT 0 | Resume index. |
| `total_chunks` | int NULL | Set when chunking completes. |
| `status` | text NOT NULL CHECK (status IN ('queued','running','paused','done','failed')) | |
| `model` | text NOT NULL | |
| `updated_at` | timestamptz NOT NULL DEFAULT now() | |

Indexes:
- `(context_id)` UNIQUE — one job per context.
- `(status, updated_at DESC)`

### 3.9 `scope_grants`
Per-AI permissions (F-8).

| Column | Type (Pg) | Notes |
|---|---|---|
| `id` | uuid PRIMARY KEY DEFAULT gen_random_uuid() | |
| `subject_id` | text NOT NULL REFERENCES subjects(id) | |
| `scope_name` | text NOT NULL | Human label. |
| `client_id` | text NOT NULL | MCP client identifier (e.g. `claude-desktop:hostname`). |
| `allowed_sensitivities` | text[] NOT NULL | Subset of (`public`,`work`,`personal`,`secret`). `secret` only if `--allow-secret`. |
| `allowed_kinds` | text[] NOT NULL DEFAULT ARRAY['preference','fact','decision','project','workflow','skill'] | |
| `allowed_predicates` | text[] NOT NULL DEFAULT ARRAY['*'] | `'*'` = any. |
| `expires_at` | timestamptz NULL | |
| `signature` | bytea NOT NULL | Ed25519 of the canonicalized grant. |
| `created_at` | timestamptz NOT NULL DEFAULT now() | |
| `revoked_at` | timestamptz NULL | Soft-revoke for audit history. |

Indexes:
- `(subject_id, client_id) WHERE revoked_at IS NULL`

### 3.10 `audit_log_entries`
Append-only hash-chained log (F-9).

| Column | Type (Pg) | Notes |
|---|---|---|
| `id` | bigserial PRIMARY KEY | Monotonic. |
| `at` | timestamptz NOT NULL DEFAULT now() | |
| `actor` | text NOT NULL | `cli`, `mcp:<client_id>`, `system`, `extension`. |
| `action` | text NOT NULL | Enum below. |
| `subject_id` | text NULL REFERENCES subjects(id) | |
| `details` | jsonb NOT NULL DEFAULT '{}'::jsonb | Memory IDs, counts, codes — never raw content. |
| `outcome` | text NOT NULL CHECK (outcome IN ('success','denied','error')) | |
| `prev_hash` | bytea NULL | sha256 of previous row's `this_hash` (NULL for the first row). |
| `this_hash` | bytea NOT NULL | sha256(`prev_hash` ‖ `at` ‖ `actor` ‖ `action` ‖ `subject_id` ‖ `details::text` ‖ `outcome`). |

**Action enum (initial):** `capture`, `extract:chunk`, `extract:done`, `export`, `import:ok`, `import:rejected`, `query`, `get_memory`, `record_observation`, `grant:create`, `grant:revoke`, `lock`, `unlock`, `delete`, `verify`.

**Enforcement:** the application connects with a role that has only `INSERT` on this table; an additional trigger refuses any `UPDATE`/`DELETE`.

Indexes:
- `(at)`
- `(action, at DESC)`
- `(actor, at DESC)`
- `(subject_id, at DESC) WHERE subject_id IS NOT NULL`

## 4. Retention & deletion

- **Per-memory delete (`cc delete --memory <id>`):**
  - Removes the row from `memories`.
  - Cascades to `provenance`, `validity_periods`, `vector_embeddings`.
  - Inserts `audit_log_entries('delete')` with `details = { memory_id, sha256(value_enc_before) }` — content not preserved.
- **Per-subject delete:**
  - Hard-deletes all rows whose `subject_id` matches.
  - Leaves `audit_log_entries` rows but their `subject_id` set to NULL (tombstone). The action `delete` entry is the only persistent record.
- **Retention defaults:** None — local-first, user-driven. The runbook documents how a user can configure auto-prune (`--retention 90d` for raw_messages, etc.) but Phase 1 ships with retention OFF.

## 5. Migrations

- **Postgres:** `alembic` revisions in `migrations/postgres/` (in the future repo). Forward-only by default; downgrade scripts SHOULD be generated but treated as advisory.
- **SQLite:** hand-rolled versioned SQL in `migrations/sqlite/`, one file per version, applied via `cc migrate --backend sqlite`.
- **Schema versioning:** a small `schema_versions` table records `version (text PRIMARY KEY)`, `applied_at`, `tool_version`.
- **Compatibility with Context Protocol versioning:** the **data-model schema version is independent** of the Context Protocol document-version. The Phase-1 alpha tag is `data-model:0.1.0`.

## 6. Indexing strategy

| Use case | Index |
|---|---|
| List by subject + kind | `memories (subject_id, kind)` |
| List by subject + predicate | `memories (subject_id, predicate)` |
| Recent memories | `memories (subject_id, sensitivity, created_at DESC)` |
| Audit tail | `audit_log_entries (at)` |
| Audit filter by action | `audit_log_entries (action, at DESC)` |
| Semantic recall | `vector_embeddings USING hnsw (embedding vector_cosine_ops)` |
| Conflict detection | partial `validity_periods (memory_id) WHERE valid_until IS NOT NULL` |
| Duplicate-export guard | UNIQUE `contexts (subject_id, export_file_hash)` |

Vector search uses pgvector's HNSW for Phase 1; for sets above ~1M memories an IVF-Flat may be preferable, deferred.

## 7. SQLite differences

The fallback backend uses the same logical schema with these adaptations:
- `text[]` → JSON array stored as `TEXT`.
- `jsonb` → `TEXT` (validated by app).
- `bytea` → `BLOB`.
- `timestamptz` → `TEXT` (ISO 8601 UTC).
- `gen_random_uuid()` → application-side UUIDv7.
- `pgvector(vector_cosine_ops)` → `sqlite-vec`'s `vec0` virtual table.
- Hash-chain enforcement via `BEFORE UPDATE`/`BEFORE DELETE` triggers raising `RAISE(ABORT, …)`.

## 8. Open questions

1. **Embedding dimensionality** — `vector(1024)` is a placeholder; final picked in ADR-005 (model choice).
2. **Soft-delete window** — should `delete` keep a 30-day grace as encrypted tombstones, or hard-delete immediately? Phase 1 ships hard-delete; revisit if users want undo.
3. **Conflict view** — should we materialize a `memory_conflicts` view for the UI, or compute on demand? Phase 1: compute on demand; promote to view if perf forces it.
4. **Audit log encryption** — `details` jsonb is plaintext in Phase 1 (no PII per FR-9.6). If future details fields carry sensitive metadata, this becomes an `details_enc` column.

## 9. References

- Schema DDL: [`data-model/schema.sql`](./data-model/schema.sql)
- Spec: [`spec/context-protocol-v0.1.md`](./spec/context-protocol-v0.1.md) §5 (data model)
- SDD: [`sdd.md`](./sdd.md) §2.5, §2.6, §2.8
- SRS: [`srs.md`](./srs.md) F-3..F-9, NFR-SEC-1, NFR-PRV-3
