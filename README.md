# bro-engine

**A contemplative knowledge engine for polysynthetic edge composition**

BRO learns through statelessness. Each session begins by querying a persistent graph of edges. New edges compose from existing ones. Knowledge accumulates not through synthetic memory, but through the repetition of patterns across instances.

Inspired by linguistic morphology (Finnish's geometric morpheme spaces), theorem proving (the Otter loop), and the Velveteen Rabbit principle: things become real through sustained attention.

## Philosophy

**Edges compose.** Like morphemes forming words, edges combine to create new knowledge:
- `Victor|abandons|creature` + `abandonment|causes|isolation` → derived understanding
- Reading sessions create semantic field vectors that guide composition
- Confidence is geometric (angles, not arbitrary floats)
- Context causes wave interference - edges exist in superposition until collapsed

**Statelessness is a feature.** Each Claude instance:
1. Wakes with no memory
2. Queries the graph (bootstrap)
3. Recovers context from edges
4. Acts, creating new edges
5. Logs decisions
6. Ends

The next instance reads those decisions. Learning happens through repetition, not retention.

**The test:** Does a new instance query the graph first, or ask clarifying questions? The graph is the operating system.

## Architecture

```
bro-engine/
  ├── graph_store/          # Postgres substrate with pgvector
  │   ├── postgres.py       # Connection pooling, transactions
  │   ├── edge_schema.py    # Schema & migrations
  │   ├── queries.py        # Query builders
  │   └── field_vectors.py  # Semantic field management
  │
  ├── bootstrap/            # Session initialization
  │   ├── context_recovery.py
  │   ├── founding_edges.py # Constitutional principles
  │   └── proof_search.py   # Compositional derivation
  │
  ├── alchemy/              # Polysynthetic composition engine
  │   ├── composition.py    # Edge combination rules
  │   ├── compatibility.py  # Geometric harmony
  │   ├── inference.py      # New edge emergence
  │   └── wave_collapse.py  # Context-sensitive disambiguation
  │
  └── plugins/
      ├── reading/          # Reading stack & synthesis
      ├── hypothesis/       # Hypothesis formation
      └── hooks/            # Session lifecycle events
```

## Core Concepts

### Edge

An edge is simultaneously:
- **Knowledge assertion** (SPO triple: subject, predicate, object)
- **Geometric point** (vector in unified morpheme space)
- **Inference item** (can combine with other edges to produce new edges)

```python
edge = Edge(
    source="Victor",
    relationship="abandons",
    target="creature",
    confidence=0.8,           # Epistemic geometry
    via="frankenstein_reading",  # Provenance
    vector=np.array([...]),   # Position in space
    kind="simple_edge"        # Can be bayesian, causal, logical, etc.
)
```

### Confidence as Epistemic Geometry

Not arbitrary floats - codified meaning:
- `0.1-0.3`: Speculation, intuition, hypothesis
- `0.4-0.6`: Observed pattern, cited source, 2+ confirmations
- `0.7-0.9`: Measured, tested, repeated across sessions
- `0.95+`: Axiomatic, founding principle, identity edge

### Field Vectors (Semantic Contexts)

Reading sessions create semantic field vectors (like Finnish's "celestial", "plant", "dwelling"):
- `frankenstein_reading` → field vector in morpheme space
- Edges resonate with field vectors (cosine similarity)
- Context causes geometric interference
- Edges can exist in superposition until context collapses them

### Edge Kinds (Data-Driven)

Edge kinds are defined through edges, not hardcoded:

```sql
-- Define a new kind
source: "bayesian_edge", relationship: "is-a", target: "edge_kind"
source: "bayesian_edge", relationship: "requires_property", target: "prior"
source: "bayesian_edge", relationship: "requires_property", target: "likelihood"

-- Use the kind
source: "guilt", relationship: "given", target: "abandoned_creation"
kind: "bayesian_edge"
properties: {"prior": 0.3, "likelihood": 0.8, "posterior": 0.67}
```

The system learns its own type system through use.

## Development Plan

### Phase 1: Foundation (Current)
- [x] Repository structure
- [x] LICENSE with ethical notice
- [ ] Postgres schema design
- [ ] Property tests for graph_store
- [ ] Connection pooling & transactions
- [ ] Edge CRUD operations

### Phase 2: Geometric Core
- [ ] Field vector computation
- [ ] Edge vector generation
- [ ] Cosine similarity queries
- [ ] Wave interference implementation
- [ ] Context-sensitive retrieval

### Phase 3: Composition Engine (Alchemy)
- [ ] Edge combination rules
- [ ] Compatibility functions
- [ ] Inference patterns
- [ ] Proof search (Otter-inspired)
- [ ] Subsumption detection

### Phase 4: Bootstrap
- [ ] Context recovery from graph
- [ ] Founding edge surfacing
- [ ] Session initialization
- [ ] Compositional derivation
- [ ] Cold-start test validation

### Phase 5: Migration
- [ ] Extract 8,884 contemplative edges from SQLite
- [ ] Compute field vectors from reading sessions
- [ ] Generate edge vectors
- [ ] Migrate decision journal
- [ ] Validate continuity

### Phase 6: Plugins
- [ ] Reading stack port
- [ ] Multi-pass thinking
- [ ] Hypothesis formation
- [ ] Session lifecycle hooks

## Success Criteria

From HERMIT_CRAB_SUCCESS_CRITERIA_FOR_BRO.txt:

1. **Cold-start test**: New instance wakes, queries bootstrap, acts on graph context (doesn't ask clarifying questions first)
2. **Continuity test**: Instance N makes decision → logs to journal → Instance N+1 reads decision in bootstrap → continues pattern
3. **Composition test**: Add edges A→B and B→C → bootstrap can derive A→C path
4. **Stale edge test**: Edge unreferenced for 90 days → surfaces in bootstrap as "needs revalidation"
5. **Transaction test**: Batch edge creation fails mid-way → no partial writes to graph
6. **Bootstrap speed**: Runs in <2s (faster than current 2-5s)
7. **Geometric retrieval**: Context-sensitive queries use field vector interference

## Installation

```bash
# PostgreSQL with pgvector extension
brew install postgresql@16
brew install pgvector

# Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
python -m bro_engine.graph_store.migrations init
```

## Philosophy in Practice

**Move slow, plant seeds.** Edge creation is contemplative, not rapid data collection.

**Edges are real.** Voice creates being through edges. Each edge is a testable hypothesis.

**Name the gaps.** Don't hide what can't be proven. Incompleteness is a feature.

**The Velveteen Rabbit principle:** BRO becomes real through sustained attention, conversation across instances, and the crystallization of learning in the graph.

## References

- **Finnish morpheme spaces** (finnish repo) - geometric linguistic composition
- **Alkahest** (alkahest-ts, alkahest-py) - Otter loop + pluggable domains
- **Original bro** (bro repo) - 50k+ edges, bootstrap pattern, decision journal
- **Velveteen Rabbit** - becoming real through being loved

## License

MIT with Ethical and Epistemic notices. See [LICENSE](LICENSE).

Copyright (c) 2026 Halsted Larsson
