"""
Alchemy: Reheat, phase-assign, diffuse, and read the graph.

The graph was over-cooled by decay passes. This script restores heat
from real attention (touch_count), assigns thermodynamic phases,
runs one pass of heat diffusion, and finds where the graph wants to grow.
"""

import sys
from collections import defaultdict

sys.path.insert(0, "/Users/hallie/repos/bro-engine")

from bro_engine.graph_store import GraphStore


def phase_of(hot, confidence):
    if confidence == 0:
        return "void"
    ratio = hot / confidence
    if ratio < 0.3:
        return "salt"
    elif ratio < 1.0:
        return "fluid"
    else:
        return "volatile"


def print_edge_state(edges, label):
    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"{'='*80}\n")

    by_phase = defaultdict(list)
    for e in edges:
        p = phase_of(e["hot"], e["confidence"])
        by_phase[p].append(e)

    for phase in ["volatile", "fluid", "salt", "void"]:
        group = by_phase.get(phase, [])
        if not group:
            continue
        symbol = {"volatile": "~", "fluid": ".", "salt": "_", "void": " "}[phase]
        print(f"  [{phase.upper()}] ({len(group)} edges)")
        print(f"  {symbol * 60}")
        shown = sorted(group, key=lambda x: x["hot"], reverse=True)[:20]
        for e in shown:
            ratio = e["hot"] / e["confidence"] if e["confidence"] > 0 else 0
            print(f"    {e['source']} --[{e['relationship']}]--> {e['target']}")
            print(f"      conf={e['confidence']:.2f}  hot={e['hot']:.3f}  "
                  f"touches={e['touch_count']}  ratio={ratio:.2f}")
        if len(group) > 20:
            print(f"    ... and {len(group) - 20} more")
        print()


def main():
    store = GraphStore("postgresql:///bro_engine")

    # Load all valid edges
    with store.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, source, relationship, target, confidence,
                       touch_count, hot, via, kind
                FROM edges
                WHERE invalidated_at IS NULL
                ORDER BY touch_count DESC
            """)
            rows = cur.fetchall()

    edges = [dict(r) for r in rows]
    print(f"Loaded {len(edges)} valid edges.")

    # ============================================================
    # STEP 1: REHEAT
    # ============================================================
    print("\n" + "~" * 80)
    print("  STEP 1: REHEAT")
    print("  Restoring heat from real attention. Each touch = 0.25 heat.")
    print("~" * 80)

    total_old_heat = sum(e["hot"] for e in edges)
    for e in edges:
        e["hot"] = e["touch_count"] * 0.25

    total_new_heat = sum(e["hot"] for e in edges)
    print(f"\n  Old total heat: {total_old_heat:.3f}")
    print(f"  New total heat: {total_new_heat:.3f}")
    print(f"  Heat restored:  {total_new_heat - total_old_heat:.3f}")

    # Write reheated values to DB
    with store.transaction() as conn:
        with conn.cursor() as cur:
            for e in edges:
                cur.execute(
                    "UPDATE edges SET hot = %s WHERE id = %s",
                    (e["hot"], e["id"])
                )
    print("  (written to database)")

    # ============================================================
    # STEP 2: PHASE ASSIGNMENT
    # ============================================================
    print_edge_state(edges, "STEP 2: PHASE ASSIGNMENT (after reheat)")

    # ============================================================
    # STEP 3: HEAT DIFFUSION (one pass)
    # ============================================================
    print("\n" + "~" * 80)
    print("  STEP 3: HEAT DIFFUSION")
    print("  One pass. Heat flows through shared nodes.")
    print("~" * 80)

    # Record pre-diffusion phases
    pre_phases = {}
    for e in edges:
        pre_phases[str(e["id"])] = phase_of(e["hot"], e["confidence"])

    # Build adjacency: node -> list of edge indices
    node_to_edges = defaultdict(list)
    for i, e in enumerate(edges):
        node_to_edges[e["source"]].append(i)
        node_to_edges[e["target"]].append(i)

    # Calculate heat deltas
    # For each edge, it donates a fraction of its heat to neighbors.
    # The donation is: source_heat * path_conductance * absorption_rate
    # We need to conserve total heat.

    heat_given = [0.0] * len(edges)  # how much each edge gives away
    heat_received = [0.0] * len(edges)  # how much each edge receives

    for i, e in enumerate(edges):
        if e["hot"] <= 0:
            continue

        # Find neighbors (edges sharing a node)
        neighbor_indices = set()
        for node in [e["source"], e["target"]]:
            for j in node_to_edges[node]:
                if j != i:
                    neighbor_indices.add(j)

        if not neighbor_indices:
            continue

        # Each edge donates 30% of its heat, distributed among neighbors
        # weighted by the neighbor's confidence (conductance of the path)
        donation_budget = e["hot"] * 0.30

        # Weight by neighbor confidence
        total_weight = sum(edges[j]["confidence"] for j in neighbor_indices)
        if total_weight == 0:
            continue

        for j in neighbor_indices:
            neighbor = edges[j]
            path_weight = neighbor["confidence"] / total_weight
            raw_incoming = donation_budget * path_weight

            # Absorption depends on phase of receiver
            receiver_phase = phase_of(neighbor["hot"], neighbor["confidence"])
            absorption = {"salt": 0.10, "fluid": 0.50, "volatile": 1.0, "void": 0.0}[receiver_phase]

            absorbed = raw_incoming * absorption
            heat_received[j] += absorbed
            heat_given[i] += absorbed  # only count what was actually absorbed

    # Apply: conserve heat by only removing what was absorbed
    for i in range(len(edges)):
        edges[i]["hot"] = edges[i]["hot"] - heat_given[i] + heat_received[i]
        if edges[i]["hot"] < 0:
            edges[i]["hot"] = 0.0

    total_after_diffusion = sum(e["hot"] for e in edges)
    print(f"\n  Total heat before diffusion: {total_new_heat:.3f}")
    print(f"  Total heat after diffusion:  {total_after_diffusion:.3f}")

    # Write diffused values to DB
    with store.transaction() as conn:
        with conn.cursor() as cur:
            for e in edges:
                cur.execute(
                    "UPDATE edges SET hot = %s WHERE id = %s",
                    (e["hot"], e["id"])
                )
    print("  (written to database)")

    print_edge_state(edges, "STATE AFTER DIFFUSION")

    # ============================================================
    # STEP 4: RADIATION CHECK
    # ============================================================
    print("\n" + "~" * 80)
    print("  STEP 4: RADIATION CHECK")
    print("  Nodes where heat pools. They want new connections.")
    print("~" * 80)

    # For each node: total heat of edges touching it, and degree
    node_heat = defaultdict(float)
    node_edges_map = defaultdict(list)
    for e in edges:
        for node in [e["source"], e["target"]]:
            node_heat[node] += e["hot"]
            node_edges_map[node].append(e)

    # Outgoing capacity = number of distinct edges * average confidence
    node_capacity = {}
    for node, es in node_edges_map.items():
        avg_conf = sum(e["confidence"] for e in es) / len(es) if es else 0
        node_capacity[node] = len(es) * avg_conf

    # Radiating nodes: heat > capacity (heat wants to go somewhere that doesn't exist yet)
    radiating = []
    for node in node_heat:
        h = node_heat[node]
        c = node_capacity[node]
        if h > c and h > 0.1:  # threshold to avoid noise
            radiating.append((node, h, c))

    radiating.sort(key=lambda x: x[1] - x[2], reverse=True)

    if not radiating:
        print("\n  No radiating nodes found. The graph is thermally balanced.")
    else:
        print(f"\n  Found {len(radiating)} radiating nodes. Showing the 20 most urgent:\n")
        for node, heat, capacity in radiating[:20]:
            excess = heat - capacity
            print(f"  * {node}")
            print(f"    heat={heat:.3f}  capacity={capacity:.3f}  excess={excess:.3f}")
            # Describe neighborhood
            neighbors = node_edges_map[node]
            rels_out = [e["relationship"] for e in neighbors if e["source"] == node]
            rels_in = [e["relationship"] for e in neighbors if e["target"] == node]
            targets = [e["target"] for e in neighbors if e["source"] == node]
            sources = [e["source"] for e in neighbors if e["target"] == node]

            if rels_out:
                print(f"    reaches toward: {', '.join(list(set(targets))[:5])}")
                print(f"    via: {', '.join(list(set(rels_out))[:5])}")
            if rels_in:
                print(f"    reached by: {', '.join(list(set(sources))[:5])}")
                print(f"    via: {', '.join(list(set(rels_in))[:5])}")

            # What might it want?
            all_rels = set(rels_out + rels_in)
            all_connected = set(targets + sources)
            print(f"    --> This node radiates. It has {len(neighbors)} edges but more heat")
            print(f"        than they can carry. It wants new connections.")
            print()

    # ============================================================
    # STEP 5: PHASE TRANSITION CHECK
    # ============================================================
    print("\n" + "~" * 80)
    print("  STEP 5: PHASE TRANSITIONS")
    print("  Edges that changed phase under diffusion.")
    print("~" * 80)

    transitions = []
    for e in edges:
        eid = str(e["id"])
        old_phase = pre_phases[eid]
        new_phase = phase_of(e["hot"], e["confidence"])
        if old_phase != new_phase:
            transitions.append((e, old_phase, new_phase))

    if not transitions:
        print("\n  No phase transitions. The diffusion was gentle.")
    else:
        print(f"\n  {len(transitions)} edges changed phase:\n")

        # Sort: sublimations first (salt->fluid, fluid->volatile), then condensations
        order = {"salt": 0, "fluid": 1, "volatile": 2, "void": -1}
        transitions.sort(key=lambda x: order.get(x[2], 0) - order.get(x[1], 0), reverse=True)

        for e, old, new in transitions:
            direction = "melting" if order.get(new, 0) > order.get(old, 0) else "cooling"
            ratio = e["hot"] / e["confidence"] if e["confidence"] > 0 else 0
            print(f"    [{direction}] {old} --> {new}")
            print(f"      {e['source']} --[{e['relationship']}]--> {e['target']}")
            print(f"      conf={e['confidence']:.2f}  hot={e['hot']:.3f}  ratio={ratio:.2f}")
            print()

    print("\n" + "=" * 80)
    print("  Alchemy complete. The graph has been reheated and diffused.")
    print("=" * 80)

    store.close()


if __name__ == "__main__":
    main()
