---
name: infer
description: Ask the graph what it implies. Run otter inference on a focused subgraph. Use when you want to know what the edges already know but haven't said.
---

The graph holds more than what was explicitly deposited.

Edges compose across shared terms. `A --[implies]--> B` and `C --[caused]--> A` together imply something about C and B. The otter loop finds these combinations — not computation, noticing.

But it needs a question first. Without one, it produces flood.

---

## Name what you want to know

Before running anything: what are you asking?

Say it as an edge you're looking for — something like "I want to know what X implies" or "I want to know what leads to Y."

```
edge true <question-subject> <question-predicate> <question-object>
```

Hold that. It will focus the reading.

---

## Focus the subgraph

Don't run inference on 8000 edges. Pick a center.

What source, relationship, or term is most relevant to your question?

```
edge query -s <term> --min-confidence 0.8
edge query -t <term> --min-confidence 0.8
```

Read what surfaces. These are the edges that will participate.

---

## Run

```python
from bro_engine.otter import load_state, run_otter, edge_combine
from bro_engine.graph_store.graph_store import GraphStore

gs = GraphStore()
state = load_state(gs, source="<your-term>")   # or target=, or no filter for broader
state = run_otter(state, edge_combine, max_steps=20)

# See what was derived
derived = [e for e in state.usable if e.step and e.step > 0]
for e in derived:
    print(f"  {e.subject} --[{e.predicate}]--> {e.object}  (conf={e.confidence:.2f})")
```

Read the derived edges without judgment. What surprised you?

---

## Tend what surfaced

For each derived edge: does it hold? Is it useful? Is it wrong?

Keep what holds:
```
edge add <subject> <predicate> <object> --phase fluid --note "derived by otter: <the arc>"
```

Discard what doesn't — you don't need to write it anywhere. Just notice it dissolved.

Correct what's wrong:
```
edge true <subject> <better-predicate> <better-object>
```

---

## Closing

Say one true thing about what the graph knew that you didn't.
Say one true thing about what didn't compose the way you expected.
Say one true thing about what the inference revealed about the question itself.

```
edge true <graph-knowledge> was-implicit-until now
edge true <non-composition> resisted <why>
edge true <the-question> was-actually-about <what-you-found>
```

Leave the question in the soil.

```
edge add <question> led-to <what-surfaced> --phase fluid --note "<what the otter found>"
```
