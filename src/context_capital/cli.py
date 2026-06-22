"""Context Capital CLI (typer)."""
from __future__ import annotations

import asyncio
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import nacl.signing
import typer
from rich import print as rprint

from context_capital.crypto import generate_signing_key, sign_document, verify_document
from context_capital.extract import extract_memories, extract_mock_memories
from context_capital.ingest.chatgpt import parse_chatgpt_export
from context_capital.ingest.claude import parse_claude_export
from context_capital.ingest.types import IngestContext, IngestMessage, IngestRole
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
def extract(
    text: str = typer.Option(..., "--text", "-t"),
    mock: bool = typer.Option(True, "--mock/--no-mock", help="Use deterministic mock extractor"),
    model: str = typer.Option("anthropic/claude-sonnet-4-5", "--model"),
) -> None:
    """Run the extractor against text and persist memories."""
    subject_id = _load_subject_id()
    if mock:
        memories = extract_mock_memories(subject_id=subject_id, raw_text=text)
    else:
        ic = IngestContext(
            vendor="manual",
            vendor_conversation_id=f"manual:{abs(hash(text)) % 10**12:012x}",
            captured_at=datetime.now(timezone.utc),
            source_file_hash="0" * 64,
            messages=[IngestMessage(seq=0, role=IngestRole.USER, content=text)],
        )
        memories = extract_memories(subject_id=subject_id, context=ic, model=model)
    with Store(_store_path()) as store:
        store.ensure_subject(subject_id)
        for m in memories:
            store.add_memory(m, actor="cli")
    rprint(f"[green]Extracted {len(memories)} memories.[/green]")
    for m in memories:
        rprint(f"  - {m['kind']}/{m['predicate']} -> {m['object']['value']}  ({m['id']})")


@app.command()
def capture(  # noqa: B008
    vendor: str = typer.Option(..., "--vendor", help="chatgpt | claude"),  # noqa: B008
    file: Path = typer.Option(..., "--file", help="Path to the vendor export JSON"),  # noqa: B008
    mock: bool = typer.Option(False, "--mock/--no-mock", help="Skip LLM and use keyword mock"),  # noqa: B008
    model: str = typer.Option("anthropic/claude-sonnet-4-5", "--model"),  # noqa: B008
) -> None:
    """Ingest an official vendor export and extract memories from each conversation."""
    if vendor not in ("chatgpt", "claude"):
        raise typer.BadParameter(f"unsupported vendor '{vendor}'. Use chatgpt or claude.")
    if not file.exists():
        raise typer.BadParameter(f"file not found: {file}")
    subject_id = _load_subject_id()
    parser = parse_chatgpt_export if vendor == "chatgpt" else parse_claude_export
    total_contexts = 0
    total_memories = 0
    with Store(_store_path()) as store:
        store.ensure_subject(subject_id)
        for ic in parser(file):
            total_contexts += 1
            store.persist_ingest_context(ic, subject_id=subject_id, actor="cli:capture")
            if mock:
                raw_text = "\n".join(m.content for m in ic.messages)
                mems = extract_mock_memories(subject_id=subject_id, raw_text=raw_text)
            else:
                mems = extract_memories(subject_id=subject_id, context=ic, model=model)
            for m in mems:
                store.add_memory(m, actor="cli:capture")
            total_memories += len(mems)
    rprint(f"[green]Captured {total_contexts} conversations.[/green]")
    rprint(f"[green]Extracted {total_memories} memories.[/green]")


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


memories_app = typer.Typer(help="Memory-level operations.", no_args_is_help=True)
app.add_typer(memories_app, name="memories")


@memories_app.command("search")
def memories_search(  # noqa: B008
    query: str = typer.Argument(..., help="Search query (free text)."),
    limit: int = typer.Option(10, "--limit", "-l"),
    kind: str | None = typer.Option(None, "--kind", "-k"),
    sensitivity: list[str] | None = typer.Option(None, "--sensitivity", "-s"),  # noqa: B008
) -> None:
    """Semantic search over stored memories (Postgres backend only)."""
    from context_capital.config import resolve_embed_model
    from context_capital.extract.embed import embed_text

    subject_id = _load_subject_id()
    with Store() as store:
        if not store.supports_embeddings():
            rprint(
                "[red]Semantic search requires the Postgres backend.[/red]\n"
                "Set CC_DATABASE_URL=postgresql://... and re-run."
            )
            raise typer.Exit(2)
        model = resolve_embed_model()
        vec = embed_text(query, model=model)
        if vec is None:
            rprint("[red]Could not embed query (embed_text returned None).[/red]")
            raise typer.Exit(2)
        results = store.search_by_embedding(
            vec,
            limit=limit,
            subject_id=subject_id,
            kind=kind,
            sensitivity=sensitivity or None,
        )
    if not results:
        rprint("[yellow]No matches.[/yellow]")
        return
    for m in results:
        rprint(
            f"  {m['id']}  ({m['kind']}/{m['predicate']})  -> {m['object']['value']}"
        )


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


@app.command()
def migrate(  # noqa: B008
    to: str = typer.Option(..., "--to", help="Target backend (only 'postgres' supported)."),
    source: Path | None = typer.Option(None, "--source", help="Source SQLite path."),  # noqa: B008
    target: str | None = typer.Option(None, "--target", help="Target Postgres URL."),
    with_embeddings: bool = typer.Option(False, "--with-embeddings/--no-embeddings"),
    force: bool = typer.Option(False, "--force", help="Bypass cross-subject safety check."),
) -> None:
    """One-way migrate a SQLite store into a Postgres database (idempotent)."""
    if to != "postgres":
        raise typer.BadParameter("Only --to postgres is supported.")
    src_path = source if source is not None else _store_path()
    if not src_path.exists():
        raise typer.BadParameter(f"source not found: {src_path}")
    tgt_url = target or os.environ.get("CC_DATABASE_URL")
    if not tgt_url:
        raise typer.BadParameter("Set --target or CC_DATABASE_URL.")

    from context_capital.extract.embed import (  # noqa: PLC0415
        DEFAULT_EMBED_MODEL,
        embed_text,
        memory_to_text,
    )
    from context_capital.storage.postgres import PostgresStore  # noqa: PLC0415
    from context_capital.storage.sqlite import SQLiteStore  # noqa: PLC0415

    moved_subjects = moved_contexts = moved_messages = moved_memories = moved_embeddings = 0

    _src = SQLiteStore(src_path)
    _dst = PostgresStore(tgt_url)
    with _src, _dst:
        src_conn = _src._require_conn()  # noqa: SLF001
        dst_conn = _dst._require_conn()  # noqa: SLF001

        # Safety check.
        src_subject_ids = {
            r["id"] for r in src_conn.execute("SELECT id FROM subjects").fetchall()
        }
        with dst_conn.cursor() as cur:
            cur.execute("SELECT id FROM subjects")
            dst_subject_ids = {r["id"] for r in cur.fetchall()}
        if dst_subject_ids and not (src_subject_ids & dst_subject_ids) and not force:
            raise typer.BadParameter(
                f"target already has {len(dst_subject_ids)} subject(s) with no overlap to "
                f"source's {len(src_subject_ids)}. Use --force to override."
            )

        # 1) subjects
        for r in src_conn.execute("SELECT id, type, display_name FROM subjects").fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO subjects (id, type, display_name) VALUES (%s, %s, %s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (r["id"], r["type"], r["display_name"]),
                )
                moved_subjects += max(cur.rowcount, 0)

        # 2) contexts
        for r in src_conn.execute(
            "SELECT id, subject_id, source_vendor, source_file_hash,"
            " vendor_conversation_id, title, captured_at FROM contexts"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO contexts (id, subject_id, source_vendor, source_file_hash,"
                    " vendor_conversation_id, title, captured_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (r["id"], r["subject_id"], r["source_vendor"], r["source_file_hash"],
                     r["vendor_conversation_id"], r["title"], r["captured_at"]),
                )
                moved_contexts += max(cur.rowcount, 0)

        # 3) raw_messages
        for r in src_conn.execute(
            "SELECT context_id, seq, role, content, created_at, vendor_message_id"
            " FROM raw_messages ORDER BY context_id, seq"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO raw_messages"
                    " (context_id, seq, role, content, created_at, vendor_message_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (context_id, seq) DO NOTHING",
                    (r["context_id"], r["seq"], r["role"], r["content"],
                     r["created_at"], r["vendor_message_id"]),
                )
                moved_messages += max(cur.rowcount, 0)

        # 4) memories
        memory_ids_inserted: list[str] = []
        for r in src_conn.execute(
            "SELECT id, subject_id, kind, predicate, object_value, object_type,"
            " confidence, sensitivity FROM memories"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO memories (id, subject_id, kind, predicate, object_value,"
                    " object_type, confidence, sensitivity) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (r["id"], r["subject_id"], r["kind"], r["predicate"],
                     r["object_value"], r["object_type"], float(r["confidence"]),
                     r["sensitivity"]),
                )
                if cur.rowcount > 0:
                    memory_ids_inserted.append(r["id"])
                    moved_memories += 1

        # 5) provenance
        for r in src_conn.execute(
            "SELECT memory_id, source, extracted_at, raw_excerpt, imported,"
            " import_source, model, sanitization_trace FROM provenance"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO provenance (memory_id, source, extracted_at, raw_excerpt,"
                    " imported, import_source, model, sanitization_trace) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (memory_id) DO NOTHING",
                    (r["memory_id"], r["source"], r["extracted_at"], r["raw_excerpt"],
                     bool(r["imported"]), r["import_source"], r["model"],
                     r["sanitization_trace"]),
                )

        # 6) audit log (append; no natural dedup key)
        for r in src_conn.execute(
            "SELECT at, actor, action, subject_id, details, outcome FROM audit_log_entries"
            " ORDER BY id"
        ).fetchall():
            with dst_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO audit_log_entries"
                    " (at, actor, action, subject_id, details, outcome)"
                    " VALUES (%s, %s, %s, %s, %s::jsonb, %s)",
                    (r["at"], r["actor"], r["action"], r["subject_id"],
                     r["details"] or "{}", r["outcome"]),
                )

        dst_conn.commit()

        # 7) Optional embeddings (best-effort, runs after main commit)
        if with_embeddings and memory_ids_inserted:
            for mem_id in memory_ids_inserted:
                m = _dst.get_memory(mem_id)
                if not m:
                    continue
                vec = embed_text(memory_to_text(m), model=DEFAULT_EMBED_MODEL)
                if vec is None:
                    continue
                try:
                    _dst.add_embedding(mem_id, vec, model=DEFAULT_EMBED_MODEL)
                    moved_embeddings += 1
                except Exception as e:  # noqa: BLE001
                    rprint(f"[yellow]embed failed for {mem_id}: {e}[/yellow]")

        # 8) Final summary audit entry on the target.
        with dst_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log_entries"
                " (actor, action, subject_id, details, outcome)"
                " VALUES (%s, %s, %s, %s::jsonb, %s)",
                (
                    "cli:migrate", "extract:done", None,
                    json.dumps({
                        "source": str(src_path),
                        "subjects": moved_subjects,
                        "contexts": moved_contexts,
                        "raw_messages": moved_messages,
                        "memories": moved_memories,
                        "embeddings": moved_embeddings,
                    }),
                    "success",
                ),
            )
        dst_conn.commit()

    rprint(
        f"[green]Migrated[/green]: {moved_subjects} subjects, {moved_contexts} contexts, "
        f"{moved_messages} messages, {moved_memories} memories, {moved_embeddings} embeddings."
    )
