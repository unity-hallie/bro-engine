---
name: pressure
description: Feel where the pressure threatens to rip. Find the chaotic surface. Name the tension before it names you.
---

Pressure doesn't appear from nowhere. Something is being held open. Something is at its yield strength.

Find it before it finds you.

---

## Opening

Ground in relation to where you are.

```
edge iam <who-you-are>
edge true <subject> <predicate> <object>
edge true <subject> <predicate> <object>
edge true <subject> <predicate> <object>
```

---

## Feel the weight

What is being held open right now?

Not just in this file — in the whole environment. Uncommitted changes, unresolved branches, open questions, things working by accident. List them without judgment.

These are the load-bearing points. Some weight is healthy. Some has accumulated past its yield strength.

## Find the chaotic surface

Where is the system non-linear — where a small change could cascade?

Feel for:
- **Race conditions**: things that work *usually* but not *always*, timing held together by hope
- **Papering**: timeouts, retries, catch-and-ignore — places where the code manages its own uncertainty
- **Unchecked assumptions**: "this will be set by now," "this can't be null," "this always returns before that fires"

These are seams where order is asserted rather than enforced.

```
edge true <chaotic-surface> is <description>
```

## Locate the tension source

Pressure comes from:
- **Sequencing debt**: operations that should be ordered but aren't
- **State spread**: shared mutable state touched by multiple async paths
- **Responsibility blur**: functions that do too many things

Name which one. Name it specifically.

```
edge add <tension-source> causes <pressure-point> --phase fluid --note "<what you observed>"
```

## Find the rip risk

Where would the seam actually fail — not just behave strangely, but produce wrong output silently?

Silent wrongness is worse than a thrown error. An error stops. Wrong output continues, downstream, quietly corrupting.

Say what you find. Say it plainly.

## Feel the relief shape

Pressure has a shape. Relief has a complementary shape.

What structural change would remove the *category* of pressure — not just this instance?

Feel that shape. Hold it lightly.

---

## Closing

Say one true thing about where the pressure lives.
Say one true thing about what is holding.
Say one true thing about what would release.

```
edge true <pressure-location> holds <what-it-holds>
edge true <relief-shape> would-release <what-it-would-release>
```

Leave it in the soil.

```
edge add <what-you-found> is-now named --phase fluid --note "<the tension, the seam, the shape of relief>"
```
