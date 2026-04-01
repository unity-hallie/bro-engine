"""
Common queries for attention strategies.

All fanout queries return chain-of-title: latest instance of each triple,
plus observation count and time span.
"""


FANOUT_SQL = """
    SELECT source, relationship, target,
           MAX(confidence) as confidence,
           COUNT(*) as observations,
           MIN(ts) as first_seen,
           MAX(ts) as last_seen,
           MAX(COALESCE(hot, 0)) as hot
    FROM edges
    WHERE invalidated_at IS NULL
      AND (source = ANY(%(nodes)s) OR target = ANY(%(nodes)s))
    GROUP BY source, relationship, target
    ORDER BY {order}
"""


SEED_SQL = """
    SELECT source, relationship, target,
           MAX(confidence) as confidence,
           1 - MIN(vector <=> %(vec)s::vector) AS similarity,
           COUNT(*) as observations,
           MIN(ts) as first_seen,
           MAX(ts) as last_seen
    FROM edges
    WHERE invalidated_at IS NULL AND vector IS NOT NULL
    GROUP BY source, relationship, target
    ORDER BY MIN(vector <=> %(vec)s::vector)
    LIMIT %(seed_k)s
"""


def seed_edges(conn, vec, seed_k=5, min_sim=0.25):
    """Vector search with chain-of-title dedup."""
    with conn.cursor() as cur:
        cur.execute(SEED_SQL, {"vec": vec, "seed_k": seed_k})
        rows = cur.fetchall()
    return [r for r in rows if r["similarity"] >= min_sim]


def fanout_edges(conn, nodes, order="MAX(confidence) DESC"):
    """All edges touching nodes, deduped with chain-of-title."""
    with conn.cursor() as cur:
        cur.execute(
            FANOUT_SQL.format(order=order),
            {"nodes": list(nodes)},
        )
        return cur.fetchall()


def collect_nodes(seeds):
    nodes = set()
    for s in seeds:
        nodes.add(s["source"])
        nodes.add(s["target"])
    return nodes


def merge(seeds, fanout, top_k=12):
    """Seeds first, then fanout, deduped."""
    seed_keys = {(s["source"], s["relationship"], s["target"]) for s in seeds}
    result = [{**s, "layer": "seed"} for s in seeds]
    for f in fanout:
        key = (f["source"], f["relationship"], f["target"])
        if key not in seed_keys:
            result.append({**f, "similarity": 0.0, "layer": "fanout"})
    return result[:top_k]
