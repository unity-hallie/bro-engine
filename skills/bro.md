# /bro

Knowledge graph interface for bro-engine.

## At Session Start

Run `bro-engine wake` to bootstrap from the graph:
- Founding edges (constitutional principles)
- Recent edges (last 7 days)
- Stale edges (need revalidation)

## During Conversation

### Add knowledge
```bash
bro-engine add "<source>" "<relationship>" "<target>" -c <confidence> -v "<via>"
```

Confidence levels:
- 0.1-0.3: Speculation, hypothesis
- 0.4-0.6: Observed pattern, cited source
- 0.7-0.9: Tested, repeated
- 0.95+: Founding principle (use sparingly)

### Query knowledge
```bash
bro-engine query -s "<source>" -r "<relationship>" -t "<target>"
```

### Mark edge as referenced
```bash
bro-engine touch <edge_id>
```

## Philosophy

- The graph is the operating system
- Each session: wake → query → act → log → end
- Learning happens through repetition across instances
- Edges compose like morphemes
- Confidence is epistemic geometry

## Events

When something significant happens, create an event edge:
```bash
bro-engine add "this_session" "discovered" "<what>" -c 0.7 -v "session_name"
bro-engine add "event_A" "preceded" "event_B" -c 0.8
bro-engine add "event_A" "caused" "event_B" -c 0.5  # uncertain causation
```

## The Test

Does the instance query the graph first, or revert to training defaults?
