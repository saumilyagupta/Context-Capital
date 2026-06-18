-- ============================================================================
-- Context Capital — Phase 1 Postgres schema (v0.1.0)
-- Companion narrative: ../data-model.md
-- Target: Postgres 16 + pgvector ≥ 0.7 + pgcrypto.
-- SQLite fallback: adaptations are documented in ../data-model.md §7.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- ----------------------------------------------------------------------------
-- Schema versioning
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_versions (
    version       text PRIMARY KEY,
    applied_at    timestamptz NOT NULL DEFAULT now(),
    tool_version  text NOT NULL
);

INSERT INTO schema_versions (version, tool_version)
    VALUES ('0.1.0', 'context-capital@0.1.0')
ON CONFLICT (version) DO NOTHING;

-- ----------------------------------------------------------------------------
-- subjects
-- ----------------------------------------------------------------------------
CREATE TABLE subjects (
    id                 text PRIMARY KEY,
    type               text NOT NULL CHECK (type IN ('person', 'organization', 'agent')),
    display_name_enc   bytea,
    created_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE subjects IS 'Identities the system stores memories about (DID-keyed).';
COMMENT ON COLUMN subjects.display_name_enc IS 'XChaCha20-Poly1305 ciphertext under user DEK.';

-- ----------------------------------------------------------------------------
-- contexts (one row per capture event)
-- ----------------------------------------------------------------------------
CREATE TABLE contexts (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id         text NOT NULL REFERENCES subjects(id),
    source_vendor      text NOT NULL CHECK (source_vendor IN ('chatgpt', 'claude', 'manual', 'import')),
    export_file_hash   bytea NOT NULL,
    captured_at        timestamptz NOT NULL DEFAULT now(),
    raw                jsonb NOT NULL,
    UNIQUE (subject_id, export_file_hash)
);

CREATE INDEX contexts_subject_idx       ON contexts (subject_id);
CREATE INDEX contexts_source_time_idx   ON contexts (source_vendor, captured_at DESC);

-- ----------------------------------------------------------------------------
-- raw_messages (captured turns; ciphertext bodies)
-- ----------------------------------------------------------------------------
CREATE TABLE raw_messages (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id    uuid NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    seq           int NOT NULL,
    role          text NOT NULL CHECK (role IN ('user', 'assistant', 'tool', 'system', 'other')),
    content_enc   bytea NOT NULL,
    created_at    timestamptz NOT NULL,
    UNIQUE (context_id, seq)
);

CREATE INDEX raw_messages_context_seq_idx ON raw_messages (context_id, seq);

-- ----------------------------------------------------------------------------
-- memories
-- ----------------------------------------------------------------------------
CREATE TABLE memories (
    id            text PRIMARY KEY CHECK (id ~ '^mem_[a-f0-9]{32}$'),
    subject_id    text NOT NULL REFERENCES subjects(id),
    kind          text NOT NULL CHECK (kind IN ('preference', 'fact', 'decision', 'project', 'workflow', 'skill')),
    predicate     text NOT NULL CHECK (char_length(predicate) BETWEEN 1 AND 64),
    value_enc     bytea NOT NULL,
    object_type   text,
    confidence    numeric(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    sensitivity   text NOT NULL CHECK (sensitivity IN ('public', 'work', 'personal', 'secret')),
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX memories_subject_kind_idx       ON memories (subject_id, kind);
CREATE INDEX memories_subject_predicate_idx  ON memories (subject_id, predicate);
CREATE INDEX memories_subject_sens_time_idx  ON memories (subject_id, sensitivity, created_at DESC);

-- ----------------------------------------------------------------------------
-- provenance (1:1 with memories)
-- ----------------------------------------------------------------------------
CREATE TABLE provenance (
    memory_id              text PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    source                 text NOT NULL,
    extracted_at           timestamptz NOT NULL,
    raw_excerpt_enc        bytea,
    imported               boolean NOT NULL DEFAULT FALSE,
    import_source          text,
    model                  text,
    sanitization_trace     jsonb
);

CREATE INDEX provenance_source_idx    ON provenance (source);
CREATE INDEX provenance_imported_idx  ON provenance (imported);

-- ----------------------------------------------------------------------------
-- validity_periods
-- ----------------------------------------------------------------------------
CREATE TABLE validity_periods (
    memory_id        text PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    valid_from       timestamptz,
    valid_until      timestamptz,
    superseded_by    text REFERENCES memories(id)
);

CREATE INDEX validity_supersedes_idx ON validity_periods (superseded_by);
CREATE INDEX validity_bounded_idx    ON validity_periods (memory_id) WHERE valid_until IS NOT NULL;

-- ----------------------------------------------------------------------------
-- vector_embeddings
-- ----------------------------------------------------------------------------
CREATE TABLE vector_embeddings (
    memory_id    text NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    model        text NOT NULL,
    embedding    vector(1024) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (memory_id, model)
);

-- HNSW for cosine-based semantic recall.
CREATE INDEX vector_embeddings_hnsw_idx
    ON vector_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- ----------------------------------------------------------------------------
-- extraction_jobs
-- ----------------------------------------------------------------------------
CREATE TABLE extraction_jobs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id      uuid NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    next_chunk      int NOT NULL DEFAULT 0,
    total_chunks    int,
    status          text NOT NULL CHECK (status IN ('queued', 'running', 'paused', 'done', 'failed')),
    model           text NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (context_id)
);

CREATE INDEX extraction_jobs_status_idx ON extraction_jobs (status, updated_at DESC);

-- ----------------------------------------------------------------------------
-- scope_grants
-- ----------------------------------------------------------------------------
CREATE TABLE scope_grants (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id               text NOT NULL REFERENCES subjects(id),
    scope_name               text NOT NULL,
    client_id                text NOT NULL,
    allowed_sensitivities    text[] NOT NULL,
    allowed_kinds            text[] NOT NULL DEFAULT ARRAY['preference','fact','decision','project','workflow','skill'],
    allowed_predicates       text[] NOT NULL DEFAULT ARRAY['*'],
    expires_at               timestamptz,
    signature                bytea NOT NULL,
    created_at               timestamptz NOT NULL DEFAULT now(),
    revoked_at               timestamptz,
    CHECK (
        allowed_sensitivities <@ ARRAY['public','work','personal','secret']
    )
);

CREATE UNIQUE INDEX scope_grants_active_idx
    ON scope_grants (subject_id, client_id)
    WHERE revoked_at IS NULL;

-- ----------------------------------------------------------------------------
-- audit_log_entries
-- ----------------------------------------------------------------------------
CREATE TABLE audit_log_entries (
    id           bigserial PRIMARY KEY,
    at           timestamptz NOT NULL DEFAULT now(),
    actor        text NOT NULL,
    action       text NOT NULL CHECK (action IN (
                     'capture','extract:chunk','extract:done','export',
                     'import:ok','import:rejected','query','get_memory',
                     'record_observation','grant:create','grant:revoke',
                     'lock','unlock','delete','verify'
                 )),
    subject_id   text REFERENCES subjects(id),
    details      jsonb NOT NULL DEFAULT '{}'::jsonb,
    outcome      text NOT NULL CHECK (outcome IN ('success', 'denied', 'error')),
    prev_hash    bytea,
    this_hash    bytea NOT NULL
);

CREATE INDEX audit_at_idx              ON audit_log_entries (at);
CREATE INDEX audit_action_time_idx     ON audit_log_entries (action, at DESC);
CREATE INDEX audit_actor_time_idx      ON audit_log_entries (actor, at DESC);
CREATE INDEX audit_subject_time_idx    ON audit_log_entries (subject_id, at DESC) WHERE subject_id IS NOT NULL;

-- Append-only enforcement: refuse UPDATE/DELETE at the trigger level. This
-- complements (but does not replace) using a least-privileged role that lacks
-- those permissions in deployment.
CREATE OR REPLACE FUNCTION audit_log_no_mutation() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log_entries is append-only';
END
$$;

CREATE TRIGGER audit_log_no_update
    BEFORE UPDATE ON audit_log_entries
    FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutation();

CREATE TRIGGER audit_log_no_delete
    BEFORE DELETE ON audit_log_entries
    FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutation();

-- ----------------------------------------------------------------------------
-- Optional: a least-privileged role for the application to use.
-- The application MUST connect as cc_app, NOT as the schema owner.
-- ----------------------------------------------------------------------------
-- CREATE ROLE cc_app LOGIN PASSWORD '<set-at-install>';
-- GRANT USAGE ON SCHEMA public TO cc_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON
--     subjects, contexts, raw_messages, memories, provenance,
--     validity_periods, vector_embeddings, extraction_jobs, scope_grants
--     TO cc_app;
-- GRANT SELECT, INSERT ON audit_log_entries TO cc_app;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO cc_app;

-- ----------------------------------------------------------------------------
-- End of schema 0.1.0.
-- ----------------------------------------------------------------------------
