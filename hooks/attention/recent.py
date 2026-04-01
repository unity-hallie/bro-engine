"""
recent — Like node_fanout, but ranks by recency (ts) with a confidence floor.

Newer edges float up. Good for "what have we been thinking about lately?"
Uses exponential decay: score = confidence × exp(-age_days / half_life)
"""

SEED_K = 5
HALF_LIFE_DAYS = 14  # edges half as relevant every two weeks


def attend(prompt_vec, conn, top_k=12, min_sim=0.25):
    # Seed
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source, relationship, target, confidence,
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

    # Fan out, ranked by recency-weighted confidence
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT source, relationship, target, confidence, ts,
                   confidence * exp(-0.693 * EXTRACT(EPOCH FROM (NOW() - ts)) / 86400.0 / %s)
                       AS recency_score
            FROM edges
            WHERE invalidated_at IS NULL
              AND (source = ANY(%s) OR target = ANY(%s))
            ORDER BY recency_score DESC
        """, (HALF_LIFE_DAYS, list(nodes), list(nodes)))
        fanout = cur.fetchall()

    seed_keys = {(s["source"], s["relationship"], s["target"]) for s in seeds}
    result = [{**s, "layer": "seed"} for s in seeds]
    for f in fanout:
        key = (f["source"], f["relationship"], f["target"])
        if key not in seed_keys:
            result.append({**f, "similarity": 0.0, "layer": "fanout"})

    return result[:top_k]
