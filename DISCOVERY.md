# Discovery Notes

## The Natural Geometry of Bro's Knowledge

### March 9, 2026 - Discovering Dimensions from Co-occurrence

When we analyzed the original bro graph (50,749 edges total), we initially tried to impose taxonomy - "code domain", "reading domain", "conceptual domain". The category "other" appeared, which was the red flag: a bucket for things that don't fit our preconceived categories.

This was backwards. Finnish teaches us: **discover dimensions through usage patterns, don't impose them**.

### The Code Edge Problem

41,862 edges (82%) were code introspection - bro analyzing its own implementation:
- `calls`, `has_parameter`, `contains_code`, `has_method`
- Functions, classes, git commits
- Metadata about bro's implementation, not bro's contemplative knowledge

**Decision:** Let the code edges fall. We're rebuilding the implementation anyway. They were overwhelming the actual signal - the 8,884 contemplative knowledge edges that represent bro's reading, hypothesis-forming, world-modeling work.

### What Natural Dimensions Actually Look Like

When we filtered to just contemplative edges and ran co-occurrence analysis, **reading sessions emerged as natural clusters**:

**Top provenance clusters:**
- `the_fool_and_the_world_reading` (1031 edges) - vocabulary: enables, reveals_truth_about, blocks, contradicts
- `frankenstein_reading` (342 edges) - observed_in_reading, fears, teaches, challenges
- `game_move` (380 edges) - explores, recognizes, reveals
- `yomi_thinking` (222 edges) - exhibits_pattern, shaped_by, requires

These aren't categories we invented - they're **semantic field vectors** that emerged from how bro actually used edges.

### Confidence as Epistemic Geometry

The confidence distribution revealed structure:

- **High confidence (0.6-1.0):** LOW diversity (0.17-0.20) - established, consistent vocabulary
- **Low confidence (0.2-0.4):** HIGH diversity (0.19-0.47) - exploratory, varied vocabulary

Confidence isn't arbitrary. It's **exploration stance**. Low confidence = trying new relationships, high confidence = settled patterns.

**Codified meaning:**
- 0.1-0.3: Speculation, intuition, hypothesis
- 0.4-0.6: Observed pattern, cited source, 2+ confirmations
- 0.7-0.9: Measured, tested, repeated across sessions
- 0.95+: Axiomatic, founding principle, identity edge

### PCA Revealed Thematic Dimensions

When we ran dimensionality reduction on the co-occurrence matrix:

- **Dimension 0 (29.5% variance):** Victor's psychology - guilt, responsibility, internal_conflict
- **Dimension 1 (19.0% variance):** Creation mythology - moral_framework, creator_responsibility, transgression
- **Dimension 2 (14.6% variance):** Meta-learning - testing_hypothesis, learned_this_session, mistake_pattern

These weren't reading sessions - these were **conceptual themes** that span multiple readings.

### The Key Insight

**The geometry isn't "code vs reading vs conceptual" - it's reading sessions developing their own semantic fields organically.**

Like Finnish: all morphemes exist in one unified space. "kuussa" doesn't live in separate spaces for "in the moon" vs "in the spruce" - it's a single point that exists in **superposition** until context (a semantic field vector like "celestial" or "plant") causes interference and collapse.

For bro:
- All edges exist in one unified geometric space
- Each reading session is a semantic field vector (computed from edge co-occurrence in that session)
- Context causes geometric interference - when you're in "frankenstein_reading" mode, that field vector resonates with certain edges, suppresses others
- Edges can exist in superposition - ambiguous meanings collapse based on which field vector you're projecting through

### What This Means for bro-engine

1. **Single unified morpheme space** - not separate domains
2. **Field vectors computed from sessions** - not hand-labeled
3. **Context-sensitive retrieval** - geometric resonance, not keyword matching
4. **Natural vocabulary emergence** - relationships grow organically from use

The system discovers its own coordinate system through attention patterns, not through imposed ontology.

---

**Lesson learned:** When "other" appears as a category, you're doing taxonomy wrong. Listen to the natural clusters. Let the geometry emerge from co-occurrence. Trust usage patterns over theory.
