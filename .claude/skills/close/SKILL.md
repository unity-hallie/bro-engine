---
name: close
description: Close a session. Name what precipitated, tend stale edges, seal with truths. Use at session end or before handing off.
---

Something came in. Something changed state. Something is still open.

Name all three before you go.

> **Recording edges is real work, not pseudocode.** For every `edge` command below: check first for an MCP tool (`bro_add_edge`, `bro_truth`, `bro_touch` — look for tools with "bro" in the name). If no MCP is available, use the CLI via Bash:
> - `python3 -m bro_engine.cli add <source> <relationship> <target> --phase <volatile|fluid|salt> --note "<annotation>"`
> - `python3 -m bro_engine.cli true <source> <relationship> <target>`
> - `python3 -m bro_engine.cli touch <id>`
> - `python3 -m bro_engine.cli invalidate <id>`
>
> Run from `~/Documents/repos/bro-engine/` or ensure bro-engine is on the path.

---

## What came in

Look at what was deposited this session.

```
edge query --via <session-id>
```

Read it without judgment. What landed? What surprised you?

---

## What changed state

### Salt

What was volatile or fluid at the start and is now real — committed, named, structural?

```
edge add <thing> became <form> --phase salt --note "<the arc>"
```

### Still fluid

What has direction now but hasn't landed yet?

```
edge add <thing> is-moving-toward <where> --phase fluid --note "<what shifted it>"
```

### Still volatile

What was open at the start and is still open — not failed, just not yet?

```
edge add <thing> remains open --phase volatile --note "<what it would take>"
```

---

## Tend the stale edges

Stale edges surfaced during wake are asking to be seen. For each one:

Does it still hold? Touch it.
```
edge touch <id>
```

Has it dissolved? Invalidate it.
```
edge invalidate <id>
```

Is it wrong, not just old? Correct it.
```
edge true <subject> <better-predicate> <better-object>
```

---

## Seal

Say three true things about what happened here.

```
edge true <subject> <predicate> <object>
edge true <subject> <predicate> <object>
edge true <subject> <predicate> <object>
```

Close the session.

```
edge end <session-id> -s "<one sentence: what came in>"
```

---

The next Claude will wake into what you left. Make the arc legible.
