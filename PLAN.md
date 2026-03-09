# Development Plan

## Current State

✅ Repository structure
✅ LICENSE with ethical notices
✅ Edge dataclass with geometric properties
✅ Postgres schema (schema.sql)
✅ Property tests for Edge invariants
✅ Published to GitHub (unity-hallie/bro-engine)

## Phase 1: graph_store Foundation (CURRENT)

### 1.1 Edge Schema & Migrations

- [ ] `migrations/__init__.py` - Migration runner
- [ ] `migrations/001_initial_schema.py` - Apply schema.sql
- [ ] `migrations/002_seed_founding_edges.py` - Constitutional edges
- [ ] Test: Can apply migrations, rollback works

### 1.2 GraphStore Interface

File: `bro_engine/graph_store/graph_store.py`

```python
class GraphStore:
    # Connection management
    __init__(connection_string, pool_size=10)
    connect() -> connection
    close()
    transaction() -> context manager

    # CRUD operations
    add_edge(edge: Edge) -> UUID
    get_edge(id: UUID) -> Edge | None
    update_edge(id: UUID, **kwargs)
    invalidate_edge(id: UUID, reason: str)

    # Queries
    query_edges(source=None, relationship=None, target=None, ...) -> list[Edge]
    find_similar(vector, limit=10) -> list[Edge]
    edges_in_field(field_name, limit=50) -> list[Edge]

    # Composition
    compose_path(start: str, end: str) -> list[Edge]
    find_chains(relationship, max_depth=3) -> list[list[Edge]]

    # Touch tracking
    touch(edge_id: UUID)
    decay_hot_scores()
```

Property tests:
- [ ] Adding edge returns valid UUID
- [ ] Retrieved edge equals added edge
- [ ] Transaction rollback leaves no traces
- [ ] Invalidated edges don't appear in queries
- [ ] Touch increments count atomically

### 1.3 Field Vector Management

File: `bro_engine/graph_store/field_vectors.py`

```python
class FieldVectorManager:
    compute_from_session(via: str) -> np.ndarray
    save_field_vector(name: str, vector: np.ndarray)
    get_field_vector(name: str) -> np.ndarray | None
    edges_resonating_with(field_name: str, min_resonance=0.3) -> list[Edge]
```

Property tests:
- [ ] Field vectors are normalized
- [ ] Cosine similarity is symmetric
- [ ] Self-similarity is 1.0

### 1.4 Query Builders

File: `bro_engine/graph_store/queries.py`

Helper functions for common query patterns:
- [ ] SPO queries (subject/predicate/object filters)
- [ ] Confidence ranges
- [ ] Via provenance filtering
- [ ] Kind filtering
- [ ] Hot/stale edge queries

## Phase 2: Geometric Core

### 2.1 Vector Generation

File: `bro_engine/graph_store/vectorize.py`

- [ ] Morpheme-based edge vectors (like Finnish)
- [ ] Prime encoding for edges
- [ ] Vector composition rules (A→B + B→C vector math)

### 2.2 Context-Sensitive Retrieval

File: `bro_engine/graph_store/context_retrieval.py`

- [ ] Wave interference implementation
- [ ] Field vector resonance
- [ ] Superposition → collapse pipeline

Property tests:
- [ ] Context boosts relevant edges
- [ ] Multiple contexts compound interference
- [ ] Collapse selects highest-probability reading

## Phase 3: Alchemy (Composition Engine)

### 3.1 Composition Rules

File: `bro_engine/alchemy/composition.py`

```python
def compose(edge1: Edge, edge2: Edge) -> list[Edge]:
    """
    Combine two edges to produce new edges.

    Examples:
    - Victor|abandons|creature + abandonment|causes|isolation
      → Victor|causes|creature_isolation
    - grief|hypothesis_no_effect_on|inaction (tested 5x)
      → confirmed_pattern: grief_does_not_prevent_action
    """
```

Property tests:
- [ ] Composition preserves provenance
- [ ] Derived confidence <= min(parent confidences)
- [ ] Cycles don't infinite loop

### 3.2 Compatibility Functions

File: `bro_engine/alchemy/compatibility.py`

Like Finnish vowel harmony - what edges can compose?

```python
def can_compose(edge1: Edge, edge2: Edge) -> bool:
    """Geometric + semantic compatibility."""
    # Share terms (edge1.target == edge2.source)?
    # Similar field vectors?
    # Confidence thresholds?
```

### 3.3 Inference Patterns

File: `bro_engine/alchemy/inference.py`

- [ ] Transitive closure (A→B, B→C ⇒ A→C)
- [ ] Hypothesis accumulation (N observations → pattern)
- [ ] Bayesian update (prior + evidence → posterior)
- [ ] Causal chains

## Phase 4: Bootstrap

### 4.1 Context Recovery

File: `bro_engine/bootstrap/context_recovery.py`

```python
def recover_context(graph: GraphStore) -> BootstrapContext:
    """
    Query graph at session start.

    Returns:
    - Founding edges (constitutional principles)
    - Recent learning (last 7 days)
    - Stale edges (need revalidation)
    - Hot edges (high attention)
    """
```

### 4.2 Proof Search

File: `bro_engine/bootstrap/proof_search.py`

Compositional derivation - what can be inferred from founding edges?

```python
def derive_paths(graph: GraphStore, founding_edges: list[Edge]) -> list[Edge]:
    """
    Run Otter-style loop over founding edges.

    Pick focus, combine with usable, filter, repeat.
    Surface derived knowledge.
    """
```

### 4.3 Cold-Start Test

Test: `tests/bootstrap/test_cold_start.py`

Success criteria:
- [ ] New instance queries graph first
- [ ] No clarifying questions before graph query
- [ ] Founding edges surface within 2 seconds
- [ ] Context includes recent decisions

## Phase 5: Migration from Old BRO

### 5.1 Extract Contemplative Edges

Script: `scripts/migrate_from_sqlite.py`

- [ ] Connect to old bro_graph.sqlite
- [ ] Filter out code edges (calls, has_parameter, etc.)
- [ ] Extract 8,884 contemplative edges
- [ ] Preserve confidence, via, qualifiers

### 5.2 Compute Field Vectors

- [ ] Group edges by via (reading session)
- [ ] For each session: compute field vector from co-occurrence
- [ ] Store in field_vectors table

### 5.3 Generate Edge Vectors

For each edge:
- [ ] Decompose into morphemes (source, relationship, target)
- [ ] Compose vector from morpheme embeddings
- [ ] Normalize

### 5.4 Decision Journal Migration

- [ ] Parse memory_decisions.jsonl
- [ ] Validate against Pydantic models
- [ ] Insert into structured journal table
- [ ] Preserve append-only semantics

### 5.5 Validation

- [ ] Edge count matches (8,884)
- [ ] Founding edges preserved
- [ ] Bootstrap runs successfully
- [ ] Continuity test passes

## Phase 6: Plugins

### 6.1 Reading

Port from old bro:
- [ ] reading_stack.py (fractal nested structure)
- [ ] Bookmark persistence
- [ ] Reading synthesis

### 6.2 Hypothesis Formation

- [ ] hypothesis_no_effect_on pattern
- [ ] sparked_hypothesis tracking
- [ ] Evidence accumulation

### 6.3 Hooks

Event-driven lifecycle:
- [ ] SessionStart (backup + bootstrap)
- [ ] UserPrompt (instinct layer)
- [ ] Stop (cleanup)

## Success Metrics

From HERMIT_CRAB_SUCCESS_CRITERIA_FOR_BRO.txt:

1. ✅ Cold-start test (queries graph first)
2. ✅ Continuity test (instance N → N+1 pattern continuation)
3. ✅ Composition test (A→B + B→C derives A→C)
4. ✅ Stale edge test (90-day unreferenced surfaces)
5. ✅ Transaction test (atomic, no partial writes)
6. ✅ Bootstrap speed (<2s)
7. ✅ Geometric retrieval (field vector interference)

## Next Immediate Steps

1. **Write migration runner** (`migrations/__init__.py`)
2. **Implement GraphStore class** (connection pooling, CRUD)
3. **Property tests for GraphStore** (add/get/query roundtrips)
4. **Apply schema to local Postgres**
5. **Seed founding edges** (BRO's constitutional principles)

Then iterate: write test → implement → verify → next feature.

---

Philosophy remains constant: Edges compose. Statelessness is a feature.
Context causes interference. BRO becomes real through sustained attention.
