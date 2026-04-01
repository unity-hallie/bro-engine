"""
heat — Seed from vector similarity, then propagate heat through the graph.

1. Vector search → seed nodes, inject heat proportional to similarity
2. Build local subgraph around seed nodes (2-hop neighborhood)
3. Compute node mass = count(edges) × mean(confidence)
4. Diffusivity α = 1/mass
5. Run heat equation for N steps: T(t+1) = T(t) + dt * α * L @ T(t)
   where L is the graph Laplacian
6. Return edges touching the hottest nodes

Low-mass (volatile) nodes conduct fast. High-mass (salt) nodes are thermal sinks.
"""

import numpy as np

SEED_K = 5
DIFFUSION_STEPS = 3
DT = 0.3  # time step — small enough to stay stable


def attend(prompt_vec, conn, top_k=12, min_sim=0.25):
    # Step 1: seed edges via vector similarity
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

    # Collect seed nodes
    seed_nodes = set()
    seed_heat = {}
    for s in seeds:
        seed_nodes.add(s["source"])
        seed_nodes.add(s["target"])
        # Inject heat proportional to similarity
        for node in (s["source"], s["target"]):
            seed_heat[node] = max(seed_heat.get(node, 0), s["similarity"])

    # Step 2: build 2-hop local subgraph
    with conn.cursor() as cur:
        # Hop 1
        cur.execute("""
            SELECT DISTINCT source, target, confidence
            FROM edges
            WHERE invalidated_at IS NULL
              AND (source = ANY(%s) OR target = ANY(%s))
        """, (list(seed_nodes), list(seed_nodes)))
        hop1 = cur.fetchall()

    hop1_nodes = set()
    for row in hop1:
        hop1_nodes.add(row["source"])
        hop1_nodes.add(row["target"])

    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT source, target, confidence
            FROM edges
            WHERE invalidated_at IS NULL
              AND (source = ANY(%s) OR target = ANY(%s))
        """, (list(hop1_nodes), list(hop1_nodes)))
        hop2 = cur.fetchall()

    # Build adjacency
    all_edges_raw = hop1 + hop2
    all_nodes = set()
    edge_list = []
    for row in all_edges_raw:
        all_nodes.add(row["source"])
        all_nodes.add(row["target"])
        edge_list.append((row["source"], row["target"], row["confidence"]))

    if len(all_nodes) < 2:
        # Degenerate — fall back to seeds
        return [{**s, "layer": "seed"} for s in seeds][:top_k]

    # Step 3: compute mass per node = count(edges) × mean(confidence)
    node_list = sorted(all_nodes)
    node_idx = {n: i for i, n in enumerate(node_list)}
    n = len(node_list)

    edge_count = np.zeros(n)
    conf_sum = np.zeros(n)

    # Weighted adjacency matrix
    W = np.zeros((n, n))
    for src, tgt, conf in edge_list:
        i, j = node_idx[src], node_idx[tgt]
        W[i][j] = max(W[i][j], conf)
        W[j][i] = max(W[j][i], conf)
        edge_count[i] += 1
        edge_count[j] += 1
        conf_sum[i] += conf
        conf_sum[j] += conf

    # Mass and diffusivity
    mean_conf = np.where(edge_count > 0, conf_sum / edge_count, 0.5)
    mass = edge_count * mean_conf
    mass = np.maximum(mass, 0.1)  # floor to avoid division by zero
    alpha = 1.0 / mass  # diffusivity

    # Step 4: graph Laplacian  L = D - W
    D = np.diag(W.sum(axis=1))
    L = D - W

    # Step 5: initial temperature — inject heat at seed nodes
    T = np.zeros(n)
    for node, heat in seed_heat.items():
        if node in node_idx:
            T[node_idx[node]] = heat

    # Diffuse
    for _ in range(DIFFUSION_STEPS):
        # Element-wise: each node diffuses according to its own alpha
        dT = -alpha * (L @ T)
        T = T + DT * dT
        T = np.maximum(T, 0)  # no negative temperature

    # Step 6: rank nodes by final temperature, return their edges
    hot_indices = np.argsort(-T)
    hot_nodes = [node_list[i] for i in hot_indices if T[i] > 0][:top_k]

    if not hot_nodes:
        return [{**s, "layer": "seed"} for s in seeds][:top_k]

    # Fetch edges for hot nodes
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT source, relationship, target, confidence
            FROM edges
            WHERE invalidated_at IS NULL
              AND (source = ANY(%s) OR target = ANY(%s))
            ORDER BY confidence DESC
        """, (hot_nodes, hot_nodes))
        result_edges = cur.fetchall()

    # Label seed vs diffused
    seed_keys = {(s["source"], s["relationship"], s["target"]) for s in seeds}
    result = []
    for s in seeds:
        result.append({**s, "layer": "seed"})

    for e in result_edges:
        key = (e["source"], e["relationship"], e["target"])
        if key not in seed_keys:
            # Include temperature of the hotter endpoint
            src_temp = T[node_idx[e["source"]]] if e["source"] in node_idx else 0
            tgt_temp = T[node_idx[e["target"]]] if e["target"] in node_idx else 0
            temp = max(src_temp, tgt_temp)
            result.append({
                **e,
                "similarity": float(temp),
                "layer": "heat",
            })
            seed_keys.add(key)

    # Sort: seeds first, then by temperature
    def sort_key(e):
        if e["layer"] == "seed":
            return (0, -e.get("similarity", 0))
        return (1, -e.get("similarity", 0))

    result.sort(key=sort_key)
    return result[:top_k]
