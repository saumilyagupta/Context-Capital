# ADR-004: Encryption — age + libsodium, user-held keys, OS-keystore wrap

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-18 |
| **Deciders** | Phase-1 engineering lead + security reviewer |
| **Tags** | crypto, security, keys |

## Context and Problem Statement

Memories, raw chat content, and the audit log all live encrypted at rest, under keys that **no operator** can recover. The user must be able to lock and unlock the store routinely, recover gracefully across reboots, and avoid losing data on passphrase mistakes.

## Decision Drivers

- User-held keys are non-negotiable (proposal-v2 §6; threat model §1).
- Phase 1 is local-only — no escrow service possible.
- The system must work for both passphrase-only and OS-keystore-backed setups.
- Crypto primitives must be widely reviewed, with mature library implementations in Python.

## Considered Options

1. **AES-256-GCM + Argon2id, custom file format.**
2. **age (X25519 + ChaCha20-Poly1305) for file-level + libsodium AEAD for row-level + Argon2id for KDF + Ed25519 for signing.**
3. **NaCl Secret Box for everything, with no KDF (raw key only).**
4. **OS-managed encryption only (FileVault / BitLocker) — no application-level encryption.**

## Decision Outcome

**Chosen: Option 2 — age + libsodium + Argon2id + Ed25519.**

Specifically:
- **AEAD at rest:** XChaCha20-Poly1305 via `libsodium` for row-level encryption.
- **KDF:** Argon2id with parameters `time=3, memory=64 MiB, parallelism=4`.
- **File-level backups:** `age` for whole-tree encrypted backups.
- **Signing:** Ed25519 via `pynacl` for context-document signing.
- **Key hierarchy:** passphrase or hardware-key → Argon2id → KEK → wraps DEK → DEK encrypts row payloads.
- **Wrap material storage:** OS keystore (macOS Keychain, Windows DPAPI, Linux Secret Service) with a file-based fallback for headless installs.

### Consequences

- ✅ Battle-tested primitives with constant-time reference implementations.
- ✅ Key never leaves user-controlled storage.
- ✅ `age` gives users a portable encrypted-backup workflow.
- ⚠️ Argon2id parameters need periodic re-tuning as hardware improves; benchmarked in CI.
- ⚠️ Passphrase loss is unrecoverable by design — communicated explicitly to users.
- ❌ No quantum resistance in v0.1; spec's `alg` field is the migration point.

## Pros and Cons of the Options

### Option 1 — AES-GCM + custom format
- ✅ NIST-blessed.
- ❌ Reimplements what `age`/`libsodium` already provide; nonce reuse is an easy footgun.

### Option 2 — age + libsodium + Argon2id + Ed25519 (chosen)
- ✅ Each tool best-in-class; bindings mature; constant-time.
- ❌ Multiple libraries to track.

### Option 3 — NaCl Secret Box only
- ✅ Simple.
- ❌ Skips a KDF; passphrase-based use cases regress.

### Option 4 — OS encryption only
- ✅ Zero in-app crypto.
- ❌ Doesn't survive backups, doesn't allow per-app key management, doesn't support cross-host portability.

## More Information

- SDD §2.6 — implementation.
- SRS §F-4, §NFR-SEC-1..7.
- threat model §5 — crypto threats.
- Crypto-agility: spec §8.1 reserves the `alg` field for future migration.
- Next review: when post-quantum signing primitives are FIPS-blessed.
