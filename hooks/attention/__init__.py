"""
Attention strategies for bro-engine prompt context hook.

Each strategy is a function:
    (prompt_vec, conn, top_k, min_sim) → list[dict]

Returns dicts with: source, relationship, target, confidence, similarity, layer
where layer is "seed" or "fanout" (or strategy-specific).
"""
