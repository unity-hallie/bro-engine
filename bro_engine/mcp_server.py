"""
bro-engine MCP Server

Exposes the graph to Claude via Model Context Protocol.
Tools: wake, add_edge, query_edges, touch_edge
"""

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .graph_store import Edge, GraphStore
from .session import begin_session, continue_session, end_session

ATTENTION_FILE = Path.home() / '.bro_attention'
ATTENTION_STRATEGIES = ['vector_only', 'node_fanout', 'hot_weighted', 'recent']
HOOKS_DIR = Path(__file__).parent.parent / 'hooks'


def get_store() -> GraphStore:
    conn_string = os.environ.get('BRO_ENGINE_DB', 'postgresql:///bro_engine')
    return GraphStore(conn_string)


def _current_strategy() -> str:
    if ATTENTION_FILE.exists():
        return ATTENTION_FILE.read_text().strip() or "node_fanout"
    return "node_fanout"


def _fmt_edge(r, layer=None):
    """Format an edge dict or Edge object for display. One line, deduped-aware."""
    if hasattr(r, 'source'):
        # Edge object
        conf = f"{r.confidence:.2f}"
        return f"  [{conf}conf] {r.source} —{r.relationship}→ {r.target}"
    # dict from raw query
    conf = f"{r['confidence']:.2f}"
    obs = r.get('observations', 1)
    obs_str = f" ({obs}x)" if obs > 1 else ""
    sim = ""
    if layer:
        sim_val = f"{r.get('similarity', 0):.2f}"
        sim = f"{layer} {sim_val}~"
    return f"  [{sim}{conf}conf{obs_str}] {r['source']} —{r['relationship']}→ {r['target']}"


# Chain-of-title neighbor query — deduped, with observation count
NEIGHBORS_SQL = """
    SELECT source, relationship, target,
           MAX(confidence) as confidence,
           COUNT(*) as observations,
           MIN(ts) as first_seen,
           MAX(ts) as last_seen,
           MAX(COALESCE(hot, 0)) as hot
    FROM edges
    WHERE invalidated_at IS NULL
      AND (source = %(node)s OR target = %(node)s)
    GROUP BY source, relationship, target
    ORDER BY MAX(confidence) DESC
    LIMIT %(limit)s
"""


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
            description="Add an edge to the knowledge graph. Requires an active session (call bro_begin first). An edge is a triple (source, relationship, target) with confidence.",
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
                    "session_id": {
                        "type": "string",
                        "description": "Active session ID from bro_begin. Required — edges must be grounded in a session.",
                    },
                },
                "required": ["source", "relationship", "target", "session_id"],
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
            name="bro_attend",
            description="Set or show the attention strategy. Controls how the graph activates when searching. Strategies: vector_only (pure cosine), node_fanout (vector seeds → all neighbor edges), hot_weighted (fan-out ranked by recency × confidence).",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {
                        "type": "string",
                        "description": "Strategy name. Omit to see current.",
                        "enum": ATTENTION_STRATEGIES,
                    },
                },
            },
        ),
        Tool(
            name="bro_search",
            description="Semantic search: embed a query and run the active attention strategy. Returns edges the graph surfaces for that query. Use this to actively pull context when something feels relevant.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                    "top_k": {"type": "integer", "description": "Max edges to return", "default": 12},
                    "strategy": {
                        "type": "string",
                        "description": "Override strategy for this search. Omit to use current.",
                        "enum": ATTENTION_STRATEGIES,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="bro_neighbors",
            description="Get all edges touching a node. Pull a node's full neighborhood.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "Node name (source or target)"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20},
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="bro_begin",
            description="Begin a session with three true edges. The opening stretch - orient through what you notice as true. Each truth is an edge: source, relationship, target.",
            inputSchema={
                "type": "object",
                "properties": {
                    "truths": {
                        "type": "array",
                        "description": "Three truths, each as [source, relationship, target]",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                        "minItems": 3,
                        "maxItems": 3,
                    },
                    "session_name": {"type": "string", "description": "Optional session name"},
                },
                "required": ["truths"],
            },
        ),
        Tool(
            name="bro_truth",
            description="Add a new truth edge to an ongoing session. As truths accumulate, more edges resonate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Session ID"},
                    "source": {"type": "string", "description": "Edge source"},
                    "relationship": {"type": "string", "description": "Edge relationship"},
                    "target": {"type": "string", "description": "Edge target"},
                },
                "required": ["session_id", "source", "relationship", "target"],
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
        elif name == "bro_attend":
            result = _handle_attend(arguments)
        elif name == "bro_search":
            result = _handle_search(store, arguments)
        elif name == "bro_neighbors":
            result = _handle_neighbors(store, arguments)
        elif name == "bro_begin":
            result = _handle_begin(store, arguments)
        elif name == "bro_truth":
            result = _handle_truth(store, arguments)
        else:
            result = f"Unknown tool: {name}"
    finally:
        store.close()

    return [TextContent(type="text", text=result)]


def _section(title, edges, lines):
    """Append a titled section of edges to lines."""
    lines.append(f"=== {title} ===")
    if edges:
        for edge in edges:
            lines.append(_fmt_edge(edge))
    else:
        lines.append("  (none)")
    lines.append("")


def _handle_wake(store: GraphStore) -> str:
    """Handle wake tool."""
    lines = []
    _section("Founding Edges (constitutional)", store.founding_edges(limit=10), lines)
    _section("Recent Edges (last 7 days)", store.recent_edges(limit=10), lines)
    _section("Stale Edges (need revalidation)", store.stale_edges(limit=5), lines)

    open_sessions = store.open_sessions()
    if open_sessions:
        lines.append("=== Open Sessions ===")
        for s in open_sessions:
            status = "[orphaned]" if s["orphaned"] else "[active]"
            lines.append(f"  {status} {s['session_id']} — opened {s['age_hours']}h ago, {s['edge_count']} edges written")
        lines.append("")

    return "\n".join(lines)


def _handle_add_edge(store: GraphStore, args: dict) -> str:
    """Handle add_edge tool. Requires an active session."""
    session_id = args["session_id"]

    if not store.validate_session(session_id):
        return (
            f"No active session: '{session_id}'\n"
            "Call bro_begin with three true things to open a session first.\n"
            "Check bro_wake for any open sessions you may have left."
        )

    confidence = args.get("confidence", 0.6)
    kind = "founding_edge" if confidence > 0.95 else None

    edge = Edge(
        source=args["source"],
        relationship=args["relationship"],
        target=args["target"],
        confidence=confidence,
        via=session_id,
        kind=kind,
    )

    edge_id = store.add_edge(edge)

    # Link edge to its session (provenance chain)
    from .session import _write_created_during
    _write_created_during(store, str(edge_id), session_id)

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
        lines.append(_fmt_edge(edge))

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


def _handle_attend(args: dict) -> str:
    """Get or set attention strategy."""
    strategy = args.get("strategy")
    if strategy is None:
        return f"Attending: {_current_strategy()}\nAvailable: {', '.join(ATTENTION_STRATEGIES)}"

    if strategy not in ATTENTION_STRATEGIES:
        return f"Unknown: {strategy}\nAvailable: {', '.join(ATTENTION_STRATEGIES)}"

    ATTENTION_FILE.write_text(strategy)
    return f"Attending: {strategy}"


def _get_embed_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def _load_attention_strategy(name: str):
    """Load an attention strategy from hooks/attention/."""
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        mod = importlib.import_module(f"attention.{name}")
        return mod.attend
    finally:
        sys.path.pop(0)


def _handle_search(store: GraphStore, args: dict) -> str:
    """Semantic search using active attention strategy."""
    query = args["query"]
    top_k = args.get("top_k", 12)
    strategy_name = args.get("strategy") or _current_strategy()

    model = _get_embed_model()
    vec = model.encode(query, normalize_embeddings=True).tolist()

    attend = _load_attention_strategy(strategy_name)

    from psycopg.rows import dict_row
    with store.connection() as conn:
        old_factory = conn.row_factory
        conn.row_factory = dict_row
        edges = attend(vec, conn, top_k=top_k, min_sim=0.20)
        conn.row_factory = old_factory

    if not edges:
        return f"No edges activated for: {query}"

    lines = [f"Search: \"{query}\" ({strategy_name}, {len(edges)} edges):"]
    for e in edges:
        lines.append(_fmt_edge(e, layer=e.get("layer", "?")))

    return "\n".join(lines)


def _handle_neighbors(store: GraphStore, args: dict) -> str:
    """Get all edges touching a node, deduped with chain-of-title."""
    node = args["node"]
    limit = args.get("limit", 20)

    with store.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(NEIGHBORS_SQL, {"node": node, "limit": limit})
            rows = cur.fetchall()

    if not rows:
        return f"No edges touching: {node}"

    lines = [f"Neighbors of {node} ({len(rows)} edges):"]
    for r in rows:
        lines.append(_fmt_edge(r))

    return "\n".join(lines)


def _handle_begin(store: GraphStore, args: dict) -> str:
    """Handle begin session tool."""
    truths = [tuple(t) for t in args["truths"]]

    result = begin_session(
        store,
        truths,
        session_name=args.get("session_name"),
    )

    lines = [f"=== Session: {result['session_id']} ===", ""]
    lines.append("Truths:")
    for edge in result['truth_edges']:
        lines.append(f"  {edge}")

    lines.append("")
    lines.append(f"Concepts: {', '.join(result['concepts'][:12])}")
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
    truth = (args["source"], args["relationship"], args["target"])
    result = continue_session(store, args["session_id"], truth)

    lines = [f"Added: {result['new_truth']}", ""]
    lines.append(f"Concepts: {', '.join(result['concepts'][:12])}")
    lines.append("")
    lines.append("Resonant edges:")

    for edge in result['resonant_edges'][:10]:
        lines.append(f"  {edge}")

    return "\n".join(lines)


async def _run():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for bro-engine-mcp."""
    import asyncio
    asyncio.run(_run())
