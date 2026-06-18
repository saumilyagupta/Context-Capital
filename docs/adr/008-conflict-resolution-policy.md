# ADR-008: Conflict resolution policy — surface-only default, user-resolved, no last-write-wins

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-18 |
| **Deciders** | Phase-1 engineering lead + product |
| **Tags** | semantics, ux, import |

## Context and Problem Statement

When a user imports a `context.json` (or extracts new memories), the new memories can disagree with existing memories on the same predicate ("I prefer Python" vs "I prefer Rust"). The system must define what happens.

Wrong choice here causes silent rewrites of the user's identity. This is a UX problem masquerading as a data-model problem.

## Decision Drivers

- The user owns the memory; the system MUST NOT silently overwrite.
- Imported documents come from semi-trusted authors (threat model §1.3); we cannot grant them last-write privileges.
- Conflict resolution must be auditable.
- Phase 1 has no rich UI for conflict resolution; we still need a defensible default.

## Considered Options

1. **Last-write-wins** — newest memory replaces older on same `(subject, predicate)`.
2. **First-write-wins** — first memory holds; new ones are dropped.
3. **Surface-only (default)** — both memories persist; conflicts surface in the audit log and `cc memory diff`.
4. **User-resolve** — system stops and asks the user which memory to keep.
5. **Confidence-weighted** — keep the higher-confidence memory.

## Decision Outcome

**Chosen: combination — Option 3 (surface-only) as the default; Option 4 (user-resolve) as an opt-in mode (`--interactive`).** Option 1 (last-write-wins) is **explicitly off** and not configurable.

Behavior:
- Both memories persist; the older keeps `superseded_by = null`; the new one is independent.
- An `audit_log_entries(action='import:ok', details={…, conflicts: [...]})` row is created.
- `cc memory diff --predicate <p>` shows the conflict.
- Phase 2 will add a UI to resolve conflicts (set `superseded_by` and hide); for Phase 1, the user does this via CLI or by deleting one of the memories.

### Consequences

- ✅ No silent rewrites; user controls the truth of their context.
- ✅ Conflicts are durable and visible — easier to debug and trust.
- ⚠️ The store can accumulate parallel facts for the same predicate; queries surface multiple memories until the user resolves them.
- ❌ The Phase-1 UX for resolution is CLI-only; non-developers will need Phase-2 UI before this is friendly.

## Pros and Cons of the Options

### Option 1 — Last-write-wins
- ✅ Simple, no UI.
- ❌ Lets an imported document overwrite the user's authoritative memory. Unacceptable.

### Option 2 — First-write-wins
- ✅ Stable.
- ❌ Stale facts win forever; people change their minds.

### Option 3 — Surface-only (chosen default)
- ✅ Both facts visible; no silent loss; minimal UX.
- ❌ Defers resolution; query results may return both.

### Option 4 — User-resolve (chosen opt-in)
- ✅ Explicit choice; high trust.
- ❌ Friction at import time; not great for batch imports.

### Option 5 — Confidence-weighted
- ✅ Automatic.
- ❌ Confidence scores are model-dependent; can be gamed by an imported document.

## More Information

- SRS §FR-6.5.
- spec/context-protocol-v0.1.md §14.5 — open question reserving the v0.2 policy block.
- conformance-suite.md PP-* — provenance preservation tests around merge.
- Next review: when Phase-2 UI lands and we can ship Option 4 as a first-class flow.
