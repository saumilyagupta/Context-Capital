# Deployment Runbook — Context Capital Phase 1

| | |
|---|---|
| **Document** | Operations Runbook |
| **Version** | Draft v0.1 |
| **Date** | 2026-06-18 |
| **Status** | Draft |
| **Scope** | Phase-1 local-first reference client |
| **Companion docs** | [`../srs.md`](../srs.md), [`../sdd.md`](../sdd.md), [`../api/README.md`](../api/README.md) |

Phase 1 ships **local-first**. There is no hosted production tier yet — this runbook covers local dev, integration-test staging, and the slot reserved for Phase-2 production (stub only).

---

## 1. Local Dev

### 1.1 Prerequisites

| Tool | Min version | Notes |
|---|---|---|
| Python | 3.12 | Server, CLI, extraction engine |
| Node.js | 20 LTS | Extension build |
| Docker | 24 | Optional, for Postgres + integration tests |
| Postgres | 16 (with `pgvector ≥ 0.7`, `pgcrypto`) | Optional; SQLite is the fallback |
| `age` | 1.2 | File-level backup encryption |
| OS keystore | macOS Keychain / Win DPAPI / Linux Secret Service | Required |

### 1.2 One-command bootstrap

```bash
$ git clone <repo> context-capital && cd context-capital
$ make bootstrap          # creates venv, installs python deps, builds extension
$ cc init                 # creates ~/.context-capital/, generates keys, registers native-messaging host
$ cc serve --dev          # starts MCP server on 127.0.0.1:7843
```

### 1.3 Default file locations

| OS | Data dir | Keys / token |
|---|---|---|
| macOS | `~/Library/Application Support/Context Capital/` | Keychain entry `com.contextcapital.app` |
| Linux | `$XDG_DATA_HOME/context-capital/` (default `~/.local/share/context-capital/`) | Secret Service `context-capital` |
| Windows | `%LOCALAPPDATA%\Context Capital\` | DPAPI under per-user store |

Override with `CC_DATA_DIR=/some/path` for dev.

### 1.4 Configuration

`~/.context-capital/config.toml`:

```toml
[server]
host = "127.0.0.1"
port = 7843
log_level = "INFO"

[storage]
backend = "sqlite"           # or "postgres"
sqlite_path = "store.db"     # relative to data dir
# postgres_url = "postgresql://cc_app:...@127.0.0.1/contextcapital"

[extraction]
default_model = "anthropic/claude-sonnet-4-7"
prompt_cache = true

[telemetry]
enabled = false              # opt-in only
```

### 1.5 Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `cc unlock` fails immediately | OS keystore inaccessible | macOS: open Keychain.app once; Linux: ensure `secret-service` running; Windows: run as the install user |
| Extension cannot reach server | Native-messaging host not registered | Re-run `cc init`; verify `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.contextcapital.app.json` exists |
| Postgres `vector` extension missing | Old Postgres build | `apt install postgresql-16-pgvector` or compile from source |
| Slow extraction | Caching off | Set `[extraction].prompt_cache = true` and use Claude API |
| `argon2: cannot allocate memory` | Low-RAM container | Lower `memory_cost`; OR run on a machine ≥ 4 GB |

## 2. Staging (Phase 1.5)

The staging tier exists **only** for team-internal integration testing. It is not public-facing.

### 2.1 Docker Compose

```yaml
# infra/docker/compose.staging.yaml — sketch
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: cc_app
      POSTGRES_PASSWORD: <set-once>
      POSTGRES_DB: contextcapital
    volumes:
      - pg-data:/var/lib/postgresql/data
    ports: ["127.0.0.1:5432:5432"]

  cc-server:
    build: ../..
    environment:
      CC_DATA_DIR: /data
      CC_TOKEN_PATH: /run/secrets/cc-token
    secrets: [cc-token]
    volumes:
      - cc-data:/data
    ports: ["127.0.0.1:7843:7843"]
    depends_on: [postgres]

secrets:
  cc-token:
    file: ./secrets/cc-token

volumes:
  pg-data:
  cc-data:
```

### 2.2 Boot
```bash
$ make staging-up
$ cc --host http://127.0.0.1:7843 unlock --passphrase-from-stdin
```

### 2.3 Backup
```bash
$ cc backup --out backup.age   # encrypts the entire data dir under age
$ cc restore --in backup.age
```

Staging backups go to a team-shared encrypted bucket (out of repo).

## 3. Production (Phase 2 — STUB)

Phase 1 does **not** deploy a production hosted service. This section reserves the structure so the runbook can grow rather than be rewritten.

- Target cloud: TBD (per ADR-008 of Phase-2 build pack).
- HA topology: TBD.
- On-call rotation: TBD.
- SLOs: TBD.
- Incident response runbook: TBD.

Phase-2 work will populate this section.

## 4. Secrets management

- The Phase-1 product never stores secrets in the repo.
- The per-install token is **created on first run** and stored in the OS keystore.
- Extraction API keys (Anthropic, OpenAI) live in `~/.context-capital/secrets.toml` (mode 0600) or environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).
- An `.env-example` ships with the repo:

```
# Choose one extraction provider; multiple may be set.
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OLLAMA_BASE_URL=http://127.0.0.1:11434

# Storage (omit to use SQLite).
DATABASE_URL=
```

## 5. Observability

### 5.1 Logs
- Location:
  - macOS: `~/Library/Logs/Context Capital/server.log`
  - Linux: `$XDG_STATE_HOME/context-capital/server.log`
  - Windows: `%LOCALAPPDATA%\Context Capital\logs\server.log`
- Format: structured JSON, one event per line.
- Rotation: 10 MB × 5 files locally; deletes older.

### 5.2 Metrics
- `GET /metrics` on the MCP server (loopback) returns Prometheus text.
- For local dev, point `prometheus` at `127.0.0.1:7843/metrics` and grab a dashboard from the repo (`infra/grafana/`).

### 5.3 Tracing
- Disabled by default. To enable:
  ```bash
  $ cc serve --otel-endpoint http://127.0.0.1:4317
  ```

## 6. On-call (Phase 1)

Phase 1 has **no formal on-call**. Issues come through:
- GitHub Issues on the repo.
- The team's shared Slack channel (internal).
- The user's own local debugging.

The `cc verify` command is the front-line diagnostic:

```bash
$ cc verify --full
[crypto]   ok — keys present, unlock-able
[schema]   ok — Postgres v16, schema 0.1.0, all migrations applied
[audit]    ok — hash chain intact, 1,452 entries verified
[mcp]      ok — server reachable; tool surface as expected
```

## 7. Backup and recovery

- **User-driven.** No automatic cloud backup in Phase 1.
- `cc backup --out file.age` writes an age-encrypted tar of the data dir.
- Restore: `cc restore --in file.age` — requires the same passphrase / keystore.
- **Recovery shard (P2, opt-in):** users can split a recovery shard using SLIP-39 (deferred; this runbook reserves the section).

## 8. Upgrade and migration

```bash
# Stop server
$ cc stop

# Backup before upgrade
$ cc backup --out pre-upgrade-$(date +%Y%m%d).age

# Upgrade
$ pip install --upgrade context-capital
$ cc migrate           # applies any pending schema migrations
$ cc verify --full

# Restart
$ cc serve
```

Schema migrations are **forward-only**. A failed migration leaves the DB in a defined state with the old schema version still applied; rolling back means restoring the backup.

## 9. Uninstall

```bash
$ cc stop
$ pip uninstall context-capital
# Removes:
#   - the cc executable
#   - the Python package
# Does NOT remove (intentional):
#   - the data directory
#   - the OS keystore entries
# To purge:
$ cc nuke --yes-i-mean-it
```

## 10. Common operational tasks

| Task | Command |
|---|---|
| Check status | `cc status` |
| Unlock store | `cc unlock` |
| Lock store | `cc lock` |
| List scopes | `cc scope list` |
| Add a scope | `cc scope add work-coding --client claude-desktop --kinds preference,project,workflow,skill --sensitivity work,public` |
| Revoke scope | `cc scope revoke <id>` |
| Tail audit | `cc audit tail --follow` |
| Verify audit chain | `cc verify --audit` |
| Export | `cc export --subject did:key:... --out me.context.json` |
| Import | `cc import --in their.context.json` |
| Re-extract a capture | `cc extract --capture-id <id> --force` |
| Vacuum Postgres | `psql -c 'VACUUM ANALYZE;'` |

## 11. References

- [`../sdd.md`](../sdd.md) §5 (deployment topology), §7 (observability).
- [`../api/README.md`](../api/README.md) §2 (auth model).
- [`../security/threat-model.md`](../security/threat-model.md) §4 (supply chain).
- [`../adr/`](../adr/) — the load-bearing decisions referenced here.
