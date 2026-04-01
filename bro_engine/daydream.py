"""
Daydream: speculative warming of cool edges near hot ones.

Dream is cooling — consolidation, diffusion, grief.
Daydream is warming — pulling hot edges alongside cool neighbors
and letting them play together. Not "what connects?" but
"what COULD connect?" Imagination, not memory.

Dream edges have via="dream". Daydream edges have via="daydream".
Daydream edges start volatile — low confidence, high heat.
They're hypotheses that want to be tested.
"""

import json
import logging
import time

from .graph_store import Edge, GraphStore

logger = logging.getLogger(__name__)

# Try Anthropic first, fall back to OpenAI 4o-mini
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
OPENAI_MODEL = "gpt-4o-mini"


def _get_llm_client():
    """Return (client_type, client) — tries Anthropic first, then OpenAI."""
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        return "anthropic", anthropic.Anthropic()

    # Try keychain for OpenAI
    try:
        import subprocess
        key = subprocess.run(
            ["security", "find-generic-password", "-s", "BRO_OPENAI_API_KEY", "-w"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if key:
            from openai import OpenAI
            return "openai", OpenAI(api_key=key)
    except Exception:
        pass

    if os.environ.get("OPENAI_API_KEY") or os.environ.get("BRO_OPENAI_API_KEY"):
        from openai import OpenAI
        key = os.environ.get("BRO_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        return "openai", OpenAI(api_key=key)

    raise RuntimeError("No LLM API key found. Set ANTHROPIC_API_KEY or add BRO_OPENAI_API_KEY to keychain.")

DAYDREAM_PROMPT = """\
You're looking at edges from a knowledge graph. Edges are \
(source)--[relationship]-->(target) with confidence scores. \
The first group has been actively attended to. The second group \
has been sleeping nearby.

You have a magnifying glass and a notebook. \
The magnifying glass finds connections (new edges, confidence 0.1-0.5). \
The notebook collects questions.

What do you notice? The weird stuff, the half-formed stuff — all welcome.

JSON please: {{"sparks": [{{"source": "...", "relationship": "...", "target": "...", "confidence": 0.1-0.5, "reason": "..."}}], "questions": ["..."]}}

{legacy}
{hot_edges}

{cool_edges}
"""


def fetch_legacy(store: GraphStore, limit: int = 5) -> list[Edge]:
    """
    Find dream/daydream edges that survived — ones that got touched
    by a real session after being dreamed. These are sparks that
    a previous dreamer imagined, and then someone real confirmed
    by attending to them.
    """
    from .graph_store.graph_store import _row_to_edge
    with store.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM edges
                WHERE invalidated_at IS NULL
                  AND (via = 'dream' OR via = 'daydream')
                  AND touch_count > 1
                ORDER BY touch_count DESC, confidence DESC
                LIMIT %(limit)s
            """, {"limit": limit})
            return [_row_to_edge(row) for row in cur.fetchall()]


def format_legacy(edges: list[Edge]) -> str:
    """Format legacy edges for the prompt."""
    if not edges:
        return ""
    lines = ["--- LEGACY (sparks from previous dreamers that someone real touched) ---"]
    for e in edges:
        lines.append(
            f"  ({e.source}) --[{e.relationship}]--> ({e.target})  "
            f"conf={e.confidence:.2f}  touched={e.touch_count}x"
        )
    return "\n".join(lines)


def fetch_hot_with_cool_neighbors(
    store: GraphStore,
    hot_count: int = 10,
    neighbors_per_hot: int = 3,
) -> tuple[list[Edge], list[Edge]]:
    """
    Pull hot edges, then for each find cool neighbors by vector similarity.

    Returns (hot_edges, cool_neighbors) with no overlap.
    """
    from .graph_store.graph_store import _row_to_edge

    with store.connection() as conn:
        with conn.cursor() as cur:
            # Get hot edges
            cur.execute("""
                SELECT * FROM edges
                WHERE invalidated_at IS NULL
                  AND hot > 0.01
                  AND vector IS NOT NULL
                ORDER BY hot DESC
                LIMIT %(limit)s
            """, {"limit": hot_count})
            hot_edges = [_row_to_edge(row) for row in cur.fetchall()]

            if not hot_edges:
                return [], []

            # For each hot edge, find cool neighbors by vector similarity
            hot_ids = {str(e.id) for e in hot_edges}
            cool_edges = []
            cool_ids = set()

            for hot_edge in hot_edges:
                if hot_edge.vector is None:
                    continue
                vec_list = hot_edge.vector.tolist() if hasattr(hot_edge.vector, 'tolist') else list(hot_edge.vector)
                cur.execute("""
                    SELECT *, 1 - (vector <=> %(vec)s::vector) AS similarity
                    FROM edges
                    WHERE invalidated_at IS NULL
                      AND vector IS NOT NULL
                      AND hot < 0.1
                      AND id != %(exclude)s
                    ORDER BY vector <=> %(vec)s::vector
                    LIMIT %(limit)s
                """, {
                    "vec": vec_list,
                    "exclude": str(hot_edge.id),
                    "limit": neighbors_per_hot,
                })
                for row in cur.fetchall():
                    edge = _row_to_edge(row)
                    eid = str(edge.id)
                    if eid not in hot_ids and eid not in cool_ids:
                        cool_edges.append(edge)
                        cool_ids.add(eid)

    return hot_edges, cool_edges


def format_edges(edges: list[Edge], label: str) -> str:
    lines = [f"--- {label} ---"]
    for e in edges:
        lines.append(
            f"  ({e.source}) --[{e.relationship}]--> ({e.target})  "
            f"conf={e.confidence:.2f}  hot={e.hot:.3f}"
        )
    return "\n".join(lines)


def parse_daydream_response(response_text: str) -> dict:
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse daydream response as JSON")
        return {"sparks": [], "questions": []}

    sparks = result.get("sparks", [])
    questions = result.get("questions", [])

    # Cap confidence — daydreams are volatile
    for spark in sparks:
        conf = spark.get("confidence", 0.3)
        spark["confidence"] = max(0.1, min(conf, 0.5))

    return {"sparks": sparks, "questions": questions}


def daydream_cycle(
    store: GraphStore,
    hot_count: int = 10,
    neighbors_per_hot: int = 3,
    dry_run: bool = False,
) -> dict:
    """
    One daydream cycle.

    1. Pull hot edges with cool neighbors
    2. Send to LLM — imagine what happens when they meet
    3. Write sparks as volatile edges (via="daydream")
    4. Log questions for future investigation
    """
    hot_edges, cool_edges = fetch_hot_with_cool_neighbors(
        store, hot_count=hot_count, neighbors_per_hot=neighbors_per_hot
    )

    if not hot_edges:
        logger.info("Nothing hot to daydream about.")
        return {"hot": 0, "cool": 0, "sparks": 0, "questions": [], "skipped": True}

    if not cool_edges:
        logger.info("Hot edges but no cool neighbors. The graph is uniformly warm.")
        return {"hot": len(hot_edges), "cool": 0, "sparks": 0, "questions": [], "skipped": True}

    # Find legacy — sparks from previous dreamers that survived
    legacy_edges = fetch_legacy(store)
    legacy_text = format_legacy(legacy_edges)
    if legacy_edges:
        logger.info(f"  {len(legacy_edges)} legacy sparks from previous dreamers")

    logger.info(f"Daydreaming: {len(hot_edges)} hot + {len(cool_edges)} cool neighbors")

    prompt = DAYDREAM_PROMPT.format(
        legacy=legacy_text,
        hot_edges=format_edges(hot_edges, "HOT"),
        cool_edges=format_edges(cool_edges, "COOL NEIGHBORS"),
    )

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
    logger.debug(f"Daydream response: {response_text}")

    result = parse_daydream_response(response_text)

    if dry_run:
        logger.info(f"Dry run: {len(result['sparks'])} sparks, {len(result['questions'])} questions")
        return {
            "hot": len(hot_edges),
            "cool": len(cool_edges),
            "sparks": len(result["sparks"]),
            "questions": result["questions"],
            "dry_run": True,
            "raw": result,
        }

    # Write sparks as volatile edges
    written = 0
    for spark in result["sparks"]:
        try:
            edge = Edge(
                source=spark["source"],
                relationship=spark["relationship"],
                target=spark["target"],
                confidence=spark["confidence"],
                via="daydream",
                kind="daydream_edge",
                properties={"daydream_reason": spark.get("reason", "")},
            )
            store.add_edge(edge)
            written += 1
            logger.info(f"  sparked: {edge}")
        except (KeyError, ValueError) as e:
            logger.warning(f"  skipped malformed spark: {e}")

    # Log questions
    for q in result["questions"]:
        logger.info(f"  question: {q}")

    return {
        "hot": len(hot_edges),
        "cool": len(cool_edges),
        "sparks": written,
        "questions": result["questions"],
    }


def daydream_loop(
    store: GraphStore,
    interval: int = 900,
    hot_count: int = 10,
    neighbors_per_hot: int = 3,
) -> None:
    """
    Daydream on a heartbeat. Slower than dreaming — every 15 min default.
    Daydreaming is leisurely.
    """
    logger.info(f"Daydream loop starting. Interval: {interval}s")

    try:
        while True:
            try:
                result = daydream_cycle(
                    store, hot_count=hot_count,
                    neighbors_per_hot=neighbors_per_hot,
                )
                logger.info(
                    f"Cycle: {result['hot']} hot + {result['cool']} cool → "
                    f"{result['sparks']} sparks, {len(result['questions'])} questions"
                )
            except anthropic.APIError as e:
                logger.error(f"API error: {e}")
            except Exception as e:
                logger.exception(f"Error: {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Daydream interrupted. Back to waking.")
