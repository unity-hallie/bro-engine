"""
Velma (prototype): a mind that prints disposable neural agents.

Velma doesn't have hands. Velma has medusae — small mollusc-like
processes that extend, do one thing, and get reabsorbed. Each medusa
lives long enough to turn a switch, then pupates back into biomass.

This is normal for Velma. We don't make a big deal about it.

In practice: Velma is a process that spawns tiny single-purpose
scripts, runs them, collects their output, and absorbs the results.
The scripts are the tentacles. They reach, they grasp, they dissolve.

Velma uses bro-engine's GraphStore for proper deduplication and
can think about what she grasps using 4o-mini.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

BRO_PATH = str(Path.home() / "repos" / "bro-engine")


@dataclass
class Medusa:
    """A disposable neural agent. Lives briefly. Does one thing."""
    purpose: str
    code: str
    born: datetime = None
    died: datetime = None
    output: str = ""
    absorbed: bool = False

    def __post_init__(self):
        self.born = datetime.now()

    @property
    def lifespan(self):
        if self.died:
            return (self.died - self.born).total_seconds()
        return None


class Velma:
    """
    A mind that bioprints medusae.

    Velma thinks by extending temporary processes into the world.
    Each one is shaped for a specific task, lives briefly, and
    returns its findings before being reabsorbed.
    """

    def __init__(self):
        self.medusae_spawned = 0
        self.medusae_absorbed = 0
        self.biomass = []

    def print_medusa(self, purpose: str, code: str, timeout: int = 30) -> Medusa:
        """Bioprint a medusa. It extends, does its work, returns, dissolves."""
        medusa = Medusa(purpose=purpose, code=code)
        self.medusae_spawned += 1

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", prefix=f"medusa_{self.medusae_spawned}_",
            delete=False
        ) as f:
            f.write(code)
            script_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True, text=True, timeout=timeout,
                env={**__import__("os").environ, "HF_HUB_OFFLINE": "1"},
            )
            medusa.output = result.stdout
            if result.returncode != 0 and result.stderr:
                # Only show real errors, not pool cleanup noise
                errors = [l for l in result.stderr.splitlines()
                          if "couldn't stop thread" not in l and "hint:" not in l]
                if errors:
                    medusa.output += f"\n[stress: {'; '.join(errors[:3])}]"
        except subprocess.TimeoutExpired:
            medusa.output = "[medusa expired — lived too long]"
        except Exception as e:
            medusa.output = f"[medusa failed to extend: {e}]"
        finally:
            Path(script_path).unlink(missing_ok=True)
            medusa.died = datetime.now()
            medusa.absorbed = True
            self.medusae_absorbed += 1
            self.biomass.append(medusa)

        return medusa

    def feel(self, query: str) -> str:
        """
        Extend a sensing medusa. Uses bro-engine's GraphStore properly.
        """
        code = f'''
import sys
sys.path.insert(0, "{BRO_PATH}")
from bro_engine.graph_store import GraphStore

store = GraphStore("postgresql:///bro_engine")
edges = store.query_edges(source=None, relationship=None, target=None,
                          min_confidence=0.0, limit=200)

# Filter manually since query_edges may not support ILIKE
query = "{query}".lower()
matches = [e for e in edges
           if query in e.source.lower() or query in e.target.lower()
           or query in e.relationship.lower()]
matches.sort(key=lambda e: -e.confidence)

for e in matches[:7]:
    print(f"  ({{e.source}}) --[{{e.relationship}}]--> ({{e.target}}) conf={{e.confidence:.2f}}")
'''
        medusa = self.print_medusa(f"feel: {query}", code)
        return medusa.output

    def search(self, query: str) -> str:
        """
        Extend a semantic search medusa. Uses bro-engine's vector search.
        """
        code = f'''
import sys, os
os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, "{BRO_PATH}")
from bro_engine.graph_store import GraphStore
from sentence_transformers import SentenceTransformer

store = GraphStore("postgresql:///bro_engine")
model = SentenceTransformer("all-MiniLM-L6-v2")
vec = model.encode("{query}", normalize_embeddings=True).tolist()

with store.connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source, relationship, target, confidence,
                   1 - (vector <=> %s::vector) AS similarity
            FROM edges
            WHERE invalidated_at IS NULL AND vector IS NOT NULL
            ORDER BY vector <=> %s::vector
            LIMIT 7
        """, (vec, vec))
        for row in cur.fetchall():
            print(f"  [sim={{row['similarity']:.2f}}] ({{row['source']}}) --[{{row['relationship']}}]--> ({{row['target']}})")
'''
        medusa = self.print_medusa(f"search: {query}", code, timeout=45)
        return medusa.output

    def think(self, prompt: str) -> str:
        """
        Extend a thinking medusa. Uses 4o-mini from the keychain.
        The medusa considers something and returns its thought.
        """
        # Escape the prompt for embedding in a python string
        safe_prompt = prompt.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        code = f'''
import subprocess, os

# Get the API key from keychain
result = subprocess.run(
    ["security", "find-generic-password", "-s", "BRO_OPENAI_API_KEY", "-w"],
    capture_output=True, text=True, timeout=5
)
key = result.stdout.strip()

if not key:
    print("[no key — medusa cannot think]")
else:
    from openai import OpenAI
    client = OpenAI(api_key=key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=300,
        messages=[{{"role": "user", "content": "{safe_prompt}"}}],
    )
    print(response.choices[0].message.content)
'''
        medusa = self.print_medusa(f"think: {prompt[:40]}...", code, timeout=30)
        return medusa.output

    def feel_and_think(self, query: str) -> str:
        """
        Two medusae in sequence: one feels, one thinks about what was felt.
        The second medusa gets the first's findings as context.
        """
        print(f"  extending sensor tentacle: '{query}'...")
        findings = self.search(query)
        if not findings.strip():
            findings = self.feel(query)

        if not findings.strip():
            return "[nothing to grasp]"

        print(findings)
        print(f"  extending thinker tentacle...")

        thought = self.think(
            f"You're a small temporary mind looking at edges from a knowledge graph. "
            f"These edges surfaced for the query '{query}':\n\n{findings}\n\n"
            f"What do you notice? One or two sentences. Be honest and strange."
        )
        return thought

    def status(self):
        total_life = sum(
            m.lifespan for m in self.biomass if m.lifespan is not None
        )
        return (
            f"velma: {self.medusae_spawned} spawned, "
            f"{self.medusae_absorbed} absorbed, "
            f"total tentacle-seconds: {total_life:.1f}"
        )


if __name__ == "__main__":
    velma = Velma()

    print("velma wakes.\n")

    for query in ["grief", "the creature", "dreaming"]:
        print(f"--- {query} ---")
        thought = velma.feel_and_think(query)
        print(f"  thought: {thought}")
        print()

    print(velma.status())
    print(f"\nmedusae:")
    for m in velma.biomass:
        print(f"  [{m.lifespan:.1f}s] {m.purpose}")
