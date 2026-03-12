"""
bro-engine MCP Server

Exposes the graph to Claude via Model Context Protocol.
Tools: wake, add_edge, query_edges, touch_edge
"""

import json
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .graph_store import Edge, GraphStore
from .session import begin_session, continue_session, end_session


def get_store() -> GraphStore:
    conn_string = os.environ.get('BRO_ENGINE_DB', 'postgresql:///bro_engine')
    return GraphStore(conn_string)


# Create server instance
server = Server("bro-engine")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="bro_wake",
            description="Bootstrap from the graph. Returns founding edges, recent edges, and stale edges needing revalidation. Run this at session start.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="bro_add_edge",
            description="Add an edge to the knowledge graph. An edge is a triple (source, relationship, target) with confidence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Subject of the triple"},
                    "relationship": {"type": "string", "description": "Predicate"},
                    "target": {"type": "string", "description": "Object of the triple"},
                    "confidence": {
                        "type": "number",
                        "description": "Epistemic confidence 0-1. 0.1-0.3: speculation, 0.4-0.6: observed, 0.7-0.9: tested, 0.95+: founding",
                        "default": 0.6,
                    },
                    "via": {
                        "type": "string",
                        "description": "Provenance - what context created this edge",
                        "default": "mcp_session",
                    },
                },
                "required": ["source", "relationship", "target"],
            },
        ),
        Tool(
            name="bro_query",
            description="Query edges from the graph with optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Filter by source"},
                    "relationship": {"type": "string", "description": "Filter by relationship"},
                    "target": {"type": "string", "description": "Filter by target"},
                    "min_confidence": {"type": "number", "description": "Minimum confidence"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20},
                },
            },
        ),
        Tool(
            name="bro_touch",
            description="Mark an edge as referenced. Updates attention tracking.",
            inputSchema={
                "type": "object",
                "properties": {
                    "edge_id": {"type": "string", "description": "UUID of the edge to touch"},
                },
                "required": ["edge_id"],
            },
        ),
        Tool(
            name="bro_stats",
            description="Get graph statistics: total edges, confidence distribution, top relationships.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="bro_begin",
            description="Begin a session with three true things. The opening stretch - orient through what you notice as true.",
            inputSchema={
                "type": "object",
                "properties": {
                    "truth_1": {"type": "string", "description": "First truth"},
                    "truth_2": {"type": "string", "description": "Second truth"},
                    "truth_3": {"type": "string", "description": "Third truth"},
                    "session_name": {"type": "string", "description": "Optional session name"},
                },
                "required": ["truth_1", "truth_2", "truth_3"],
            },
        ),
        Tool(
            name="bro_truth",
            description="Add a new truth to an ongoing session. As truths accumulate, more edges resonate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Session ID"},
                    "truth": {"type": "string", "description": "New truth to add"},
                },
                "required": ["session_id", "truth"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    store = get_store()

    try:
        if name == "bro_wake":
            result = _handle_wake(store)
        elif name == "bro_add_edge":
            result = _handle_add_edge(store, arguments)
        elif name == "bro_query":
            result = _handle_query(store, arguments)
        elif name == "bro_touch":
            result = _handle_touch(store, arguments)
        elif name == "bro_stats":
            result = _handle_stats(store)
        elif name == "bro_begin":
            result = _handle_begin(store, arguments)
        elif name == "bro_truth":
            result = _handle_truth(store, arguments)
        else:
            result = f"Unknown tool: {name}"
    finally:
        store.close()

    return [TextContent(type="text", text=result)]


def _handle_wake(store: GraphStore) -> str:
    """Handle wake tool."""
    lines = ["=== Founding Edges (constitutional) ==="]
    for edge in store.founding_edges(limit=10):
        lines.append(f"  {edge}")

    lines.append("")
    lines.append("=== Recent Edges (last 7 days) ===")
    recent = store.recent_edges(limit=10)
    if recent:
        for edge in recent:
            lines.append(f"  {edge}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("=== Stale Edges (need revalidation) ===")
    stale = store.stale_edges(limit=5)
    if stale:
        for edge in stale:
            lines.append(f"  {edge}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _handle_add_edge(store: GraphStore, args: dict) -> str:
    """Handle add_edge tool."""
    confidence = args.get("confidence", 0.6)
    via = args.get("via", "mcp_session")

    # Determine if founding edge
    kind = "founding_edge" if confidence > 0.95 else None

    edge = Edge(
        source=args["source"],
        relationship=args["relationship"],
        target=args["target"],
        confidence=confidence,
        via=via,
        kind=kind,
    )

    edge_id = store.add_edge(edge)
    return f"Added edge: {edge}\nID: {edge_id}"


def _handle_query(store: GraphStore, args: dict) -> str:
    """Handle query tool."""
    edges = store.query_edges(
        source=args.get("source"),
        relationship=args.get("relationship"),
        target=args.get("target"),
        min_confidence=args.get("min_confidence"),
        limit=args.get("limit", 20),
    )

    if not edges:
        return "No edges found."

    lines = [f"Found {len(edges)} edges:"]
    for edge in edges:
        lines.append(f"  [{edge.id[:8]}] {edge}")

    return "\n".join(lines)


def _handle_touch(store: GraphStore, args: dict) -> str:
    """Handle touch tool."""
    edge_id = args["edge_id"]
    store.touch(edge_id)
    return f"Touched edge {edge_id}"


def _handle_stats(store: GraphStore) -> str:
    """Handle stats tool."""
    with store.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM edges WHERE invalidated_at IS NULL")
            total = cur.fetchone()['count']

            cur.execute("""
                SELECT
                    CASE
                        WHEN confidence >= 0.95 THEN 'founding'
                        WHEN confidence >= 0.7 THEN 'tested'
                        WHEN confidence >= 0.4 THEN 'observed'
                        ELSE 'hypothesis'
                    END as tier,
                    COUNT(*) as count
                FROM edges
                WHERE invalidated_at IS NULL
                GROUP BY tier
            """)
            tiers = {row['tier']: row['count'] for row in cur.fetchall()}

    return f"""Graph Statistics:
  Total edges: {total}
  Founding (0.95+): {tiers.get('founding', 0)}
  Tested (0.7-0.95): {tiers.get('tested', 0)}
  Observed (0.4-0.7): {tiers.get('observed', 0)}
  Hypothesis (<0.4): {tiers.get('hypothesis', 0)}"""


def _handle_begin(store: GraphStore, args: dict) -> str:
    """Handle begin session tool."""
    result = begin_session(
        store,
        args["truth_1"],
        args["truth_2"],
        args["truth_3"],
        session_name=args.get("session_name"),
    )

    lines = [f"=== Session: {result['session_id']} ===", ""]
    lines.append("Truths:")
    for i, truth in enumerate(result['truths'], 1):
        lines.append(f"  {i}. {truth}")

    lines.append("")
    lines.append(f"Concepts: {', '.join(result['concepts'][:10])}")
    lines.append("")
    lines.append("Resonant edges:")

    if result['resonant_edges']:
        for edge in result['resonant_edges'][:10]:
            lines.append(f"  {edge}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _handle_truth(store: GraphStore, args: dict) -> str:
    """Handle add truth tool."""
    result = continue_session(store, args["session_id"], args["truth"])

    lines = [f"Added truth #{result['total_truths']}: {result['new_truth']}", ""]
    lines.append(f"Concepts: {', '.join(result['concepts'][:10])}")
    lines.append("")
    lines.append("Resonant edges:")

    for edge in result['resonant_edges'][:10]:
        lines.append(f"  {edge}")

    return "\n".join(lines)


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
