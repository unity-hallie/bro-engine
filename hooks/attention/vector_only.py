"""
vector_only — Original behavior. Pure vector similarity, no fan-out.
"""


def attend(prompt_vec, conn, top_k=8, min_sim=0.35):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source, relationship, target, confidence,
                   1 - (vector <=> %s::vector) AS similarity
            FROM edges
            WHERE invalidated_at IS NULL AND vector IS NOT NULL
            ORDER BY vector <=> %s::vector
            LIMIT %s
        """, (prompt_vec, prompt_vec, top_k))
        rows = cur.fetchall()

    return [
        {**r, "layer": "seed"}
        for r in rows
        if r["similarity"] >= min_sim
    ]
