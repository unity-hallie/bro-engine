# Planning in Edges

Captured: 2026-03-11
Via: feel_skill_development_session

## The /feel Skill

```edges
feel | is-a | skill | conf:0.9 | via:this_session
feel | lives_at | ../feel | conf:1.0

flow_1_texture | is-a | practice | conf:0.9
flow_1_texture | part_of | feel | conf:1.0
flow_1_texture | about | proprioceptive_awareness | conf:0.8

flow_2_one_point | is-a | practice | conf:0.9
flow_2_one_point | part_of | feel | conf:1.0
flow_2_one_point | follows | flow_1_texture | conf:0.9

flow_3_again | is-a | practice | conf:0.9
flow_3_again | part_of | feel | conf:1.0
flow_3_again | follows | flow_2_one_point | conf:0.9
flow_3_again | leads_to | flow_1_texture | conf:0.9 | note:it_loops
```

## Events and Causation

```edges
event | is-a | edge_kind | conf:0.7 | note:hypothesis
event | can_represent | moment | conf:0.8
event | can_represent | decision | conf:0.8
event | can_represent | session | conf:0.8

preceded | is-a | relationship | conf:0.9
preceded | minimal_claim_about | sequence | conf:0.8
preceded | composes_transitively | conf:0.9 | note:A_preceded_B_+_B_preceded_C_implies_A_preceded_C

caused | is-a | relationship | conf:0.9
caused | implies | preceded | conf:0.95
caused | adds_to_preceded | mechanism | conf:0.8
caused | adds_to_preceded | theory | conf:0.8

confidence | distinguishes | preceded_vs_caused | conf:0.7
low_confidence_caused | equivalent_to | preceded_with_hypothesis | conf:0.7
```

## Timestamps

```edges
timestamp | provides_evidence_for | preceded | conf:0.85
timestamp | not_required_for | preceded | conf:0.8 | note:can_derive_from_other_sources
preceded | can_be_derived_from | relational_constraints | conf:0.8
sequence | emerges_from | causal_edges | conf:0.75
```

## Journal Migration

```edges
journal_entry | can_become | event | conf:0.8
memory_decisions.jsonl | contains | journal_entries | conf:1.0
journal_migration | needed_for | eating_dogfood | conf:0.85

migration_tooling | includes | journal_to_events | conf:0.8
migration_tooling | includes | timestamp_to_preceded | conf:0.8
migration_tooling | includes | precedence_queries | conf:0.8
```

## What the Graph Already Has

```edges
bro_engine_graph | supports | edges_with_confidence | conf:1.0
bro_engine_graph | supports | edge_composition | conf:1.0
bro_engine_graph | supports | edge_kinds_through_edges | conf:1.0
bro_engine_graph | supports | otter_loop_inference | conf:0.9
bro_engine_graph | supports | soft_invalidation | conf:1.0

events_and_causation | fits_in | existing_graph_structure | conf:0.85 | note:nothing_to_add_just_use_it
```

## Next Actions

```edges
implement_graphstore | precedes | journal_migration | conf:0.9
journal_migration | enables | event_edges | conf:0.85
event_edges | enables | causal_queries | conf:0.8
causal_queries | enables | bootstrap_knows_how_we_got_here | conf:0.75
```

---

These edges are hypotheses (mostly 0.7-0.85 confidence).
They'll gain confidence through use or fade if they don't hold.
