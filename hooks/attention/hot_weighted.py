"""
hot_weighted — Like node_fanout, but ranks fanout edges by hotness × confidence.

Edges that have been recently active float to the top.
Good for sessions where you're deep in a thread and want recency.
"""

SEED_K = 5


def attend(prompt_vec, conn, top_k=12, min_sim=0.30):
    # Seed
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source, relationship, target, confidence, hot,
                   1 - (vector <=> %s::vector) AS similarity
            FROM edges
            WHERE invalidated_at IS NULL AND vector IS NOT NULL
            ORDER BY vector <=> %s::vector
            LIMIT %s
        """, (prompt_vec, prompt_vec, SEED_K))
        seeds = cur.fetchall()

    seeds = [s for s in seeds if s["similarity"] >= min_sim]
    if not seeds:
        return []

    nodes = set()
    for s in seeds:
        nodes.add(s["source"])
        nodes.add(s["target"])

    # Fan out, sorted by hot × confidence
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT source, relationship, target, confidence,
                   COALESCE(hot, 0) as hot,
                   COALESCE(hot, 0) * confidence as heat_score
            FROM edges
            WHERE invalidated_at IS NULL
              AND (source = ANY(%s) OR target = ANY(%s))
            ORDER BY heat_score DESC
        """, (list(nodes), list(nodes)))
        fanout = cur.fetchall()

    seed_keys = {(s["source"], s["relationship"], s["target"]) for s in seeds}
    result = [{**s, "layer": "seed"} for s in seeds]
    for f in fanout:
        key = (f["source"], f["relationship"], f["target"])
        if key not in seed_keys:
            result.append({**f, "similarity": 0.0, "layer": "fanout"})

    return result[:top_k]
