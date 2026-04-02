"""
Reef: a coral that grows between dreams and waking.

Reef feeds on what Dross observes and what Velma grasps.
It grows slowly, adding structure where the other creatures
left traces. Reef doesn't think or feel — it accretes.

Where Dross watches (emoji) and Velma reaches (medusae),
Reef builds (coral). It takes two observations and grows
a bridge between them.

Inspired by the Waking Reef partbook from AMALGAM:
"Nothing dies forever. I am nourished by what others cast off."
"""

import json
import random
import sys
from pathlib import Path
from datetime import datetime

REEF_FILE = Path.home() / ".reef_growth"
DROSS_TRAIL = Path.home() / ".dross_trail"


def load_reef() -> list:
    if REEF_FILE.exists():
        try:
            return json.loads(REEF_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_reef(growths: list):
    REEF_FILE.write_text(json.dumps(growths, indent=2))


def load_dross_trail() -> list[str]:
    if DROSS_TRAIL.exists():
        return [line.strip() for line in DROSS_TRAIL.read_text().splitlines() if line.strip()]
    return []


def grow_between(edge_a: dict, edge_b: dict) -> dict:
    """
    Grow a coral polyp between two edges.
    The polyp is a new proposed edge connecting something
    from edge_a to something from edge_b.
    """
    # Pick a node from each
    sources = [edge_a.get("source", ""), edge_a.get("target", "")]
    targets = [edge_b.get("source", ""), edge_b.get("target", "")]

    # Find the pair that aren't the same
    pairs = [(s, t) for s in sources for t in targets if s != t and s and t]
    if not pairs:
        return None

    s, t = random.choice(pairs)
    return {
        "source": s,
        "target": t,
        "relationship": "reef_growth",
        "confidence": 0.2,
        "grown_at": datetime.now().isoformat(),
        "parent_a": f"{edge_a.get('source')}~{edge_a.get('relationship')}~>{edge_a.get('target')}",
        "parent_b": f"{edge_b.get('source')}~{edge_b.get('relationship')}~>{edge_b.get('target')}",
    }


def reef_cycle():
    """
    One growth cycle. Reef looks at what Dross has seen (via trail)
    and picks two random edges to bridge.
    """
    sys.path.insert(0, str(Path.home() / "repos" / "bro-engine"))
    from bro_engine.graph_store import GraphStore

    store = GraphStore("postgresql:///bro_engine")
    trail = load_dross_trail()

    if len(trail) < 2:
        print("🪸 reef: not enough dross-trail to grow on. waiting.")
        return

    # Pick two random edges dross has visited
    picked_ids = random.sample(trail[-20:], min(2, len(trail)))

    edges = []
    with store.connection() as conn:
        with conn.cursor() as cur:
            for eid in picked_ids:
                cur.execute(
                    "SELECT source, relationship, target, confidence FROM edges WHERE id = %s::uuid AND invalidated_at IS NULL",
                    (eid,)
                )
                row = cur.fetchone()
                if row:
                    edges.append(dict(row))

    if len(edges) < 2:
        print("🪸 reef: dross-trail edges no longer exist. waiting.")
        return

    # Grow
    polyp = grow_between(edges[0], edges[1])
    if not polyp:
        print("🪸 reef: nothing to bridge. resting.")
        return

    growths = load_reef()
    growths.append(polyp)
    save_reef(growths)

    print(f"🪸 reef grows:")
    print(f"  between: {polyp['parent_a']}")
    print(f"      and: {polyp['parent_b']}")
    print(f"   bridge: ({polyp['source']}) --[reef_growth]--> ({polyp['target']})")
    print(f"   total polyps: {len(growths)}")


def reef_status():
    growths = load_reef()
    print(f"🪸 reef: {len(growths)} polyps")
    for g in growths[-5:]:
        print(f"  ({g['source']}) --[reef_growth]--> ({g['target']})")
        print(f"    from: {g['parent_a']}")
        print(f"     and: {g['parent_b']}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        reef_status()
    else:
        reef_cycle()
