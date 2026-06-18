"""MCP server (stdio) — ADR-006.

Tools:
  - query_memories(kind?, predicate?, sensitivity?, limit?) → list[Memory]
Resources:
  - subject_summary://current → plain-text summary

Per spec §11.1.3 and FR-7.5, sensitivity=secret is always filtered out of
MCP responses in Phase 1 (no scope-grant system yet to opt-in to secret).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool
from pydantic import AnyUrl

from context_capital.storage import Store

DEFAULT_SENSITIVITIES = ["public", "work"]


def make_server(store_path: Path, active_subject_id: str) -> Server:
    server: Server = Server("context-capital")

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def _list_tools() -> list[Tool]:
        return [
            Tool(
                name="query_memories",
                description=(
                    "Query memories for the active subject. Sensitivity=secret is never "
                    "returned (Phase-1 deny-by-default)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string"},
                        "predicate": {"type": "string"},
                        "sensitivity": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["public", "work", "personal"]},
                            "default": DEFAULT_SENSITIVITIES,
                        },
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                    },
                },
            )
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        args = arguments or {}
        if name != "query_memories":
            raise ValueError(f"Unknown tool: {name}")
        sens = list(args.get("sensitivity") or DEFAULT_SENSITIVITIES)
        sens = [s for s in sens if s != "secret"]
        limit = int(args.get("limit") or 20)
        with Store(store_path) as store:
            mems = store.list_memories(
                subject_id=active_subject_id,
                kind=args.get("kind"),
                sensitivity=sens,
            )
        return [TextContent(type="text", text=json.dumps({"memories": mems[:limit]}, default=str))]

    @server.list_resources()  # type: ignore[no-untyped-call,untyped-decorator]
    async def _list_resources() -> list[Resource]:
        return [
            Resource(
                uri=AnyUrl("subject_summary://current"),
                name="Current subject summary",
                description="Plain-text summary suitable for system-prompt injection.",
                mimeType="text/plain",
            )
        ]

    @server.read_resource()  # type: ignore[no-untyped-call,untyped-decorator]
    async def _read_resource(uri: str) -> str:
        if uri != "subject_summary://current":
            raise ValueError(f"Unknown resource: {uri}")
        with Store(store_path) as store:
            mems = store.list_memories(
                subject_id=active_subject_id, sensitivity=DEFAULT_SENSITIVITIES
            )
        if not mems:
            return f"No memories available for {active_subject_id}."
        lines = [f"Subject: {active_subject_id}"]
        for m in mems[:20]:
            lines.append(f"- ({m['kind']}) {m['predicate']}: {m['object']['value']}")
        return "\n".join(lines)

    return server


async def run_stdio(store_path: Path, active_subject_id: str) -> None:
    server = make_server(store_path, active_subject_id)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
