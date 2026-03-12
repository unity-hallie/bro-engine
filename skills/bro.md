# /bro

Knowledge graph interface for bro-engine.

## Session Start: Three True Things

Begin with three truths. Each truth is an edge.

```bash
bro-engine begin \
  -t this_session discovered something_new \
  -t I feel curious \
  -t the_graph is alive
```

This creates a session, stores the truths as edges, and surfaces resonant edges from the graph.

## During Session

### Add more truths
```bash
bro-engine truth <session_id> thinking_layer wants_to flow
```

As truths accumulate, more edges resonate.

### Add knowledge
```bash
bro-engine add "<source>" "<relationship>" "<target>" -c <confidence> -v "<via>"
```

### Query
```bash
bro-engine query -s "<source>" -r "<relationship>" -t "<target>"
```

## End Session

```bash
bro-engine end <session_id> -s "summary of what happened"
```

## Confidence

- 0.1-0.3: Speculation, hypothesis
- 0.4-0.6: Observed pattern
- 0.7-0.9: Tested, repeated
- 0.95+: Founding principle

## Philosophy

- Truths are edges
- Edges resonate with other edges
- The thinking layer flows, not loops
- State truth → edges surface → think → state truth → more edges
- Different sessions name different truths → parallax → triangulation

## The Test

Does the instance begin with three truths, or ask clarifying questions first?
