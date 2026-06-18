# Context Capital — Phase 1 reference client

Phase-1 Python reference implementation of the **Context Protocol v0.1** — the open, user-owned, cross-vendor AI memory format defined under `docs/spec/context-protocol-v0.1.md`.

Phase 1 is local-first: a CLI + local MCP server, SQLite storage, mock extractor. No hosted backend. No real LLM calls (extraction is mocked; real extraction is Phase-1.5).

## Install (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
cc init                                                  # generate signing key + subject DID
cc extract --text "I prefer PyTorch and use Python."      # mock extractor
cc list                                                  # show stored memories
cc export --out my-context.json                           # signed Context Protocol v0.1 document
cc import --in my-context.json                            # round-trip through sanitization
cc serve                                                  # start MCP server on stdio
cc verify-audit                                          # tail the audit log
```

## Tests

```bash
pytest -v
pytest -v tests/test_sanitize.py
```

## Docs

- `docs/srs.md`, `docs/sdd.md` — requirements + design.
- `docs/spec/context-protocol-v0.1.md` — the open spec this client implements.
- `docs/security/threat-model.md` — prompt-injection attack tree.
- `docs/adr/` — load-bearing decisions.
