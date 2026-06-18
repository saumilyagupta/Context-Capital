"""Context Capital CLI (typer)."""
from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import nacl.signing
import typer
from rich import print as rprint

from context_capital.crypto import generate_signing_key, sign_document, verify_document
from context_capital.extract import extract_mock_memories
from context_capital.mcp_server import run_stdio
from context_capital.sanitize import SanitizationMode, sanitize_memory
from context_capital.storage import Store

app = typer.Typer(help="Context Capital — Phase-1 reference client.", no_args_is_help=True)

DATA_DIR = Path.home() / ".context-capital"


def _data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _store_path() -> Path:
    return _data_dir() / "store.db"


def _key_path() -> Path:
    return _data_dir() / "signing.key"


def _subject_path() -> Path:
    return _data_dir() / "subject_did"


def _load_signing_key() -> nacl.signing.SigningKey:
    p = _key_path()
    if not p.exists():
        raise typer.BadParameter("No signing key. Run `cc init` first.")
    return nacl.signing.SigningKey(p.read_bytes())


def _load_subject_id() -> str:
    p = _subject_path()
    if not p.exists():
        raise typer.BadParameter("No subject DID. Run `cc init` first.")
    return p.read_text().strip()


@app.command()
def init() -> None:
    """Initialize a new install: generate Ed25519 keys + subject DID."""
    _data_dir()
    if _key_path().exists():
        rprint("[yellow]Already initialized. Refusing to overwrite.[/yellow]")
        raise typer.Exit(1)
    sk = generate_signing_key()
    _key_path().write_bytes(bytes(sk))
    _key_path().chmod(0o600)
    pk_b64 = base64.urlsafe_b64encode(bytes(sk.verify_key)).decode("ascii").rstrip("=")
    did = f"did:key:z{pk_b64}"
    _subject_path().write_text(did)
    rprint(f"[green]Initialized.[/green]\n  Data dir: {_data_dir()}\n  Subject:  {did}")


@app.command()
def extract(text: str = typer.Option(..., "--text", "-t")) -> None:
    """Run the mock extractor against text and persist memories."""
    subject_id = _load_subject_id()
    memories = extract_mock_memories(subject_id=subject_id, raw_text=text)
    with Store(_store_path()) as store:
        store.ensure_subject(subject_id)
        for m in memories:
            store.add_memory(m, actor="cli")
    rprint(f"[green]Extracted {len(memories)} memories.[/green]")
    for m in memories:
        rprint(f"  - {m['kind']}/{m['predicate']} -> {m['object']['value']}  ({m['id']})")


@app.command("list")
def list_memories(
    kind: str | None = typer.Option(None, "--kind", "-k"),  # noqa: B008
    sensitivity: list[str] | None = typer.Option(None, "--sensitivity", "-s"),  # noqa: B008
) -> None:
    """List stored memories with optional filters."""
    subject_id = _load_subject_id()
    with Store(_store_path()) as store:
        mems = store.list_memories(
            subject_id=subject_id, kind=kind, sensitivity=sensitivity or None
        )
    if not mems:
        rprint("[yellow]No memories.[/yellow]")
        return
    for m in mems:
        rprint(
            f"  {m['id']}  ({m['kind']}/{m['predicate']})  -> {m['object']['value']}"
        )


@app.command()
def export(out: Path = typer.Option(..., "--out", "-o")) -> None:  # noqa: B008
    """Export a signed context.json (excludes sensitivity=secret by default)."""
    subject_id = _load_subject_id()
    sk = _load_signing_key()
    with Store(_store_path()) as store:
        mems = store.list_memories(
            subject_id=subject_id, sensitivity=["public", "work", "personal"]
        )
    exported_at = datetime.now(timezone.utc).isoformat()
    doc = {
        "@context": "https://contextprotocol.org/ns/v0.1",
        "context_protocol_version": "0.1.0",
        "subject": {"id": subject_id, "type": "person"},
        "issuer": {"tool": "context-capital@0.1.0", "exported_at": exported_at},
        "memories": mems,
    }
    signed = sign_document(doc, sk)
    out.write_text(json.dumps(signed, indent=2, default=str))
    rprint(f"[green]Wrote {out} ({len(mems)} memories, signed).[/green]")


@app.command("import")
def import_doc(
    in_path: Path = typer.Option(..., "--in", "-i"),  # noqa: B008
    mode: SanitizationMode = typer.Option(SanitizationMode.WRAP, "--mode"),  # noqa: B008
) -> None:
    """Import a signed context.json — verifies signature, sanitizes memories."""
    subject_id = _load_subject_id()
    doc = json.loads(in_path.read_text())
    if not verify_document(doc):
        rprint("[red]Signature verification failed — refusing import.[/red]")
        raise typer.Exit(2)
    imported = refused = sanitized = 0
    issuer_tool = doc.get("issuer", {}).get("tool", "unknown")
    with Store(_store_path()) as store:
        store.ensure_subject(subject_id)
        for m in doc.get("memories", []):
            clean = sanitize_memory(m, mode=mode)
            if clean is None:
                refused += 1
                continue
            if clean["provenance"].get("sanitization_trace"):
                sanitized += 1
            clean["provenance"]["imported"] = True
            clean["provenance"]["import_source"] = issuer_tool
            store.add_memory(clean, actor="cli:import")
            imported += 1
    rprint(f"[green]Imported {imported}, sanitized {sanitized}, refused {refused}.[/green]")


@app.command()
def serve() -> None:
    """Start the MCP server on stdio."""
    subject_id = _load_subject_id()
    asyncio.run(run_stdio(_store_path(), subject_id))


@app.command("verify-audit")
def verify_audit_cmd() -> None:
    """Print the recent audit log."""
    with Store(_store_path()) as store:
        entries = store.audit_log(limit=200)
    if not entries:
        rprint("[yellow]No audit entries.[/yellow]")
        return
    for e in entries:
        rprint(f"  {e['at']}  {e['actor']:12}  {e['action']:20}  {e['outcome']}")
