"""
node_fanout — Find nodes via vector similarity, then activate all their edges.

1. Vector search → seed edges (deduped, chain-of-title)
2. Collect unique nodes from seeds
3. Pull all edges touching those nodes (deduped, chain-of-title)
4. Seeds first, then fanout by confidence
5. Return top_k total

Each edge carries: observations, first_seen, last_seen
"""

from .common import seed_edges, fanout_edges, collect_nodes, merge


def attend(prompt_vec, conn, top_k=12, min_sim=0.30):
    seeds = seed_edges(conn, prompt_vec, seed_k=5, min_sim=min_sim)
    if not seeds:
        return []

    nodes = collect_nodes(seeds)
    fanout = fanout_edges(conn, nodes, order="MAX(confidence) DESC")
    return merge(seeds, fanout, top_k=top_k)
