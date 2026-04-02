"""
Dream loop: background consolidation of hot edges.

While awake, edges accumulate heat through attention. The dream loop
pulls hot edges, sends them to a language model, and asks: what connects?
what tensions? what's the same thing said differently?

New connections come back as edges with via="dream". Contradictions
are grieved, not pruned. Then hot scores decay. The graph cools.
"""

import json
import logging
import time
from datetime import datetime

from .graph_store import Edge, GraphStore
from .daydream import _get_llm_client

logger = logging.getLogger(__name__)

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
OPENAI_MODEL = "gpt-4o-mini"

DREAM_PROMPT = """\
You are a contemplative knowledge engine dreaming over its recent hot edges.

These edges are the things that have been most active recently. Each edge is a triple: (source, relationship, target) with a confidence score and a hotness score.

Look at them together and notice:
1. What connects? Are there implicit relationships between edges that aren't yet explicit?
2. What tensions exist? Are there contradictions or edges that pull in opposite directions?
3. What's the same thing said differently? Are there edges that are essentially restating each other?

Respond with a JSON object containing two arrays:

{
  "connections": [
    {
      "source": "...",
      "relationship": "...",
      "target": "...",
      "confidence": 0.0-0.7,
      "reason": "why this connection"
    }
  ],
  "grief": [
    {
      "edge_id": "uuid of the edge to grieve",
      "reason": "why this edge is in tension or contradicted"
    }
  ]
}

Rules:
- Confidence for new connections must be between 0.1 and 0.7. Dream-derived knowledge is always tentative.
- Only grieve edges where there is genuine contradiction or tension, not just redundancy.
- Keep relationship names lowercase with underscores. Prefer existing relationship names when possible.
- Be concise in reasons.
- If nothing connects or tensions, return empty arrays. Don't force it.

Here are the hot edges:
"""


def fetch_hot_edges(store: GraphStore, batch_size: int = 30) -> list[Edge]:
    """Pull edges ordered by hot score descending."""
    with store.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM edges
                WHERE invalidated_at IS NULL
                  AND hot > 0.01
                ORDER BY hot DESC
                LIMIT %(limit)s
            """, {"limit": batch_size})
            from .graph_store.graph_store import _row_to_edge
            return [_row_to_edge(row) for row in cur.fetchall()]


def format_edges_for_prompt(edges: list[Edge]) -> str:
    """Format edges into a readable block for the LLM."""
    lines = []
    for e in edges:
        lines.append(
            f"[{e.id}] ({e.source}) --[{e.relationship}]--> ({e.target})  "
            f"conf={e.confidence:.2f}  hot={e.hot:.2f}  via={e.via}"
        )
    return "\n".join(lines)


def parse_dream_response(response_text: str) -> dict:
    """Parse the LLM response into connections and grief markers."""
    # Try to extract JSON from the response
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse dream response as JSON")
        return {"connections": [], "grief": []}

    # Validate structure
    connections = result.get("connections", [])
    grief = result.get("grief", [])

    # Cap confidence on connections — dream-derived edges use
    # min(parent_conf * parent_conf, 0.7), same spirit as otter composition
    for conn in connections:
        conf = conn.get("confidence", 0.5)
        conf = max(conf, 0.1)
        conn["confidence"] = min(conf * conf, 0.7)

    return {"connections": connections, "grief": grief}


def dream_cycle(
    store: GraphStore,
    batch_size: int = 30,
    dry_run: bool = False,
) -> dict:
    """
    Run one dream cycle.

    1. Pull hot edges
    2. Send to LLM
    3. Write new edges (via="dream")
    4. Grieve contradictions
    5. Decay hot scores

    Returns summary of what happened.
    """
    # 1. Pull hot edges
    hot_edges = fetch_hot_edges(store, batch_size=batch_size)
    if not hot_edges:
        logger.info("No hot edges to dream on. Sleeping.")
        store.decay_hot_scores()
        return {"hot_edges": 0, "connections": 0, "grief": 0, "skipped": True}

    logger.info(f"Dreaming on {len(hot_edges)} hot edges")

    # 2. Format and send to LLM
    prompt = DREAM_PROMPT + format_edges_for_prompt(hot_edges)

    client_type, client = _get_llm_client()

    if client_type == "anthropic":
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
    else:
        message = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.choices[0].message.content

    logger.info(f"LLM backend: {client_type}")
    logger.debug(f"Dream response: {response_text}")

    # 3. Parse response
    result = parse_dream_response(response_text)

    if dry_run:
        logger.info(f"Dry run: would write {len(result['connections'])} connections, "
                     f"grieve {len(result['grief'])} edges")
        return {
            "hot_edges": len(hot_edges),
            "connections": len(result["connections"]),
            "grief": len(result["grief"]),
            "dry_run": True,
            "raw": result,
        }

    # 4. Write new connections
    written = 0
    for conn in result["connections"]:
        try:
            edge = Edge(
                source=conn["source"],
                relationship=conn["relationship"],
                target=conn["target"],
                confidence=conn["confidence"],
                via="dream",
                kind="dream_edge",
                properties={"dream_reason": conn.get("reason", "")},
            )
            store.add_edge(edge)
            written += 1
            logger.info(f"  dreamed: {edge}")
        except (KeyError, ValueError) as e:
            logger.warning(f"  skipped malformed connection: {e}")

    # 5. Grieve contradictions
    grieved = 0
    for g in result["grief"]:
        edge_id = g.get("edge_id")
        reason = g.get("reason", "dream: tension detected")
        if not edge_id:
            continue
        try:
            if store.invalidate_edge(edge_id, f"dream: {reason}"):
                grieved += 1
                logger.info(f"  grieved: {edge_id} — {reason}")
            else:
                logger.debug(f"  grief target not found or already grieved: {edge_id}")
        except Exception as e:
            logger.warning(f"  grief failed for {edge_id}: {e}")

    # 6. Decay
    remaining_hot = store.decay_hot_scores()
    logger.info(f"Decayed. {remaining_hot} edges still hot.")

    return {
        "hot_edges": len(hot_edges),
        "connections": written,
        "grief": grieved,
        "remaining_hot": remaining_hot,
    }


def dream_loop(
    store: GraphStore,
    interval: int = 600,
    batch_size: int = 30,
) -> None:
    """
    Run the dream loop on a heartbeat.

    Args:
        store: GraphStore connection
        interval: Seconds between cycles (default 600 = 10 minutes)
        batch_size: How many hot edges per cycle
    """
    logger.info(f"Dream loop starting. Interval: {interval}s, batch: {batch_size}")

    try:
        while True:
            try:
                result = dream_cycle(store, batch_size=batch_size)
                logger.info(
                    f"Cycle complete: {result['hot_edges']} hot, "
                    f"{result['connections']} dreamed, {result['grief']} grieved"
                )
            except anthropic.APIError as e:
                logger.error(f"API error during dream cycle: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error during dream cycle: {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Dream loop interrupted. Waking up.")
