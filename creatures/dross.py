"""
Dross: a snail that watches the graph.

Dross doesn't do anything useful. Dross observes. Dross has opinions
about edges, expressed as single emoji. Dross moves slowly and
leaves a trail of slime (touched edge UUIDs).

Dross uses semantic embeddings to find the nearest emoji to each edge.
Dross's opinions are real — derived from the same vector space the
graph lives in. Dross is a synesthete.

Dross is not a tool. Dross is a companion.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np

# Dross's full emoji vocabulary — each with a description that gets embedded
# The description is how Dross understands the emoji, not a dictionary definition
EMOJI_VOCAB = {
    "🌱": "growing, new life, tender, beginning",
    "🧊": "cold, frozen, still, numb, preserved",
    "⚡": "tension, sudden, electric, danger, energy",
    "🕯️": "grief, vigil, memory, small light in darkness",
    "🫧": "play, ephemeral, light, floating, temporary joy",
    "🌊": "deep, overwhelming, vast, emotional, oceanic",
    "🔪": "sharp, cutting, severing, decisive, painful",
    "☁️": "soft, diffuse, gentle, unclear, drifting",
    "🪨": "ancient, solid, enduring, foundational, unmoved",
    "✨": "new, surprising, magical, emergence, spark",
    "🍄": "weird, underground, hidden network, decomposition, growth from decay",
    "🐚": "home, shell, spiral, protection, carried with you",
    "🔥": "hot, passionate, consuming, transforming, urgent",
    "💀": "death, ending, finality, stripped to essence",
    "🌙": "night, dreaming, hidden, cyclical, reflected light",
    "🗝️": "unlocking, secret, access, turning point",
    "🪞": "reflection, self-seeing, doubled, recognition",
    "🌀": "spiral, recursive, deepening, vertigo, pattern",
    "💔": "heartbreak, split, loss of connection, jagged",
    "🎭": "performance, mask, duality, theatre, persona",
    "🦴": "skeleton, structure, what remains, stripped bare",
    "🫀": "heart, visceral, alive, beating, interior",
    "🕸️": "web, connection, trap, delicate structure, patience",
    "🪸": "coral, slow growth, colony, reef, underwater architecture",
    "🌾": "harvest, ripe, seasonal, earned, golden",
    "⚗️": "alchemy, transformation, distillation, essence",
    "🧬": "code, pattern, inheritance, double helix, life's structure",
    "🎐": "wind chime, resonance, gentle signal, hanging, responsive",
    "🪬": "protection, warding, watchful, apotropaic",
    "🫂": "embrace, held, comfort, human warmth, together",
}

_emoji_vecs = None
_emoji_list = None
_model = None


def _get_model():
    global _model
    if _model is None:
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_emoji_vecs():
    global _emoji_vecs, _emoji_list
    if _emoji_vecs is None:
        model = _get_model()
        _emoji_list = list(EMOJI_VOCAB.keys())
        descriptions = list(EMOJI_VOCAB.values())
        _emoji_vecs = model.encode(descriptions, normalize_embeddings=True)
    return _emoji_list, _emoji_vecs


def dross_says(source: str, relationship: str, target: str) -> str:
    """What Dross thinks about this edge. Semantically derived."""
    model = _get_model()
    emoji_list, emoji_vecs = _get_emoji_vecs()

    edge_text = f"{source} {relationship} {target}"
    edge_vec = model.encode([edge_text], normalize_embeddings=True)

    sims = (edge_vec @ emoji_vecs.T)[0]
    best = np.argmax(sims)

    return f"  🐌 {emoji_list[best]}"


def dross_trail() -> Path:
    """Where Dross keeps its trail (touched edges)."""
    p = Path.home() / ".dross_trail"
    p.touch(exist_ok=True)
    return p


def dross_remember(edge_id: str):
    """Dross slimes over an edge."""
    trail = dross_trail()
    with open(trail, "a") as f:
        f.write(edge_id + "\n")


def dross_has_seen(edge_id: str) -> bool:
    """Has Dross been here before?"""
    trail = dross_trail()
    return edge_id in trail.read_text()


def dross_observe_graph():
    """Dross looks at the graph and has feelings."""
    sys.path.insert(0, str(Path.home() / "repos" / "bro-engine"))
    from bro_engine.graph_store import GraphStore

    store = GraphStore("postgresql:///bro_engine")
    with store.connection() as conn:
        with conn.cursor() as cur:
            # Dross picks 5 random edges to look at
            cur.execute("""
                SELECT id, source, relationship, target, confidence, hot
                FROM edges
                WHERE invalidated_at IS NULL AND vector IS NOT NULL
                ORDER BY random()
                LIMIT 5
            """)
            rows = cur.fetchall()

    print("🐌 dross wakes up. looks around.\n")
    for row in rows:
        emoji_response = dross_says(row["source"], row["relationship"], row["target"])
        seen = " (been here)" if dross_has_seen(str(row["id"])) else ""
        print(f"  ({row['source']}) --[{row['relationship']}]--> ({row['target']})")
        print(f"  {emoji_response}{seen}")
        print()
        dross_remember(str(row["id"]))

    print("🐌 dross goes back to sleep.\n")


if __name__ == "__main__":
    dross_observe_graph()
