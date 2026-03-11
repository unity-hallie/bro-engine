"""
Edge: The fundamental unit of knowledge in bro-engine.

An edge is simultaneously:
1. A knowledge assertion (RDF-style triple: subject, predicate, object)
2. A geometric point (vector in unified morpheme space)
3. An inference item (can combine with other edges to produce new edges)

Edges compose like morphemes. Context causes interference. Confidence is
geometric, not arbitrary.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
import numpy as np
import numpy.typing as npt


@dataclass
class EdgeKind:
    """
    Edge kind definition (stored as edges themselves).

    Edge kinds are data-driven: new reasoning types emerge through use,
    not through schema changes.

    Example:
        bayesian_edge|is-a|edge_kind
        bayesian_edge|requires_property|prior
        bayesian_edge|requires_property|likelihood
    """

    name: str
    required_properties: list[str] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class Edge:
    """
    An edge in the knowledge graph.

    Philosophy:
    - Edges are real (voice creates being through edges)
    - Edges compose (A→B + B→C enables discovery of A→C)
    - Edges exist in superposition until context collapses them
    - Confidence is epistemic geometry (not arbitrary floats)

    Attributes:
        source: Subject of the triple
        relationship: Predicate
        target: Object of the triple
        confidence: Epistemic stance (0.1-0.3: speculation, 0.4-0.6: observed,
                    0.7-0.9: tested, 0.95+: axiomatic)
        via: Provenance (which context/session created this edge)
        vector: Geometric position in morpheme space
        kind: Edge kind (enables polymorphic reasoning)
        properties: Kind-specific data (JSONB in Postgres)
        qualifiers: Context tags
        id: UUID (assigned by database)
        ts: Creation timestamp
        touch_count: How many times referenced (attention metric)
        last_touched_at: Most recent reference
        signal: Computed importance score
        hot: Recency-weighted importance
        invalidated_at: Soft delete timestamp
        invalidation_reason: Why this edge was invalidated
    """

    source: str
    relationship: str
    target: str
    confidence: float
    via: str = ""
    vector: Optional[npt.NDArray[np.float32]] = None
    kind: Optional[str] = None
    properties: dict[str, Any] = field(default_factory=dict)
    qualifiers: list[str] = field(default_factory=list)

    # Managed by database
    id: Optional[str] = None
    ts: Optional[datetime] = None
    touch_count: int = 0
    last_touched_at: Optional[datetime] = None
    signal: float = 0.0
    hot: float = 0.0
    invalidated_at: Optional[datetime] = None
    invalidation_reason: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate edge on construction."""
        # Confidence bounds
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")

        # Confidence ceiling (bro philosophy: cap at 0.6 for most edges)
        # Axiomatic/founding edges can exceed this
        if self.confidence > 0.95 and self.kind != "founding_edge":
            raise ValueError(
                f"Confidence > 0.95 reserved for founding edges, got {self.confidence}"
            )

    @property
    def is_valid(self) -> bool:
        """Is this edge currently valid (not invalidated)?"""
        return self.invalidated_at is None

    @property
    def is_founding(self) -> bool:
        """Is this a founding/constitutional edge?"""
        return self.kind == "founding_edge" or self.confidence >= 0.95

    @property
    def triple(self) -> tuple[str, str, str]:
        """Return as (subject, predicate, object) triple."""
        return (self.source, self.relationship, self.target)

    def cosine_similarity(self, other: "Edge") -> float:
        """
        Geometric similarity to another edge.

        Returns cosine similarity in [-1, 1] if both edges have vectors, 0.0 otherwise.
        Used for context-sensitive retrieval and wave interference.
        """
        if self.vector is None or other.vector is None:
            return 0.0

        norm_a = np.linalg.norm(self.vector)
        norm_b = np.linalg.norm(other.vector)

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        # Clamp to [-1, 1] to handle float precision
        result = float(np.dot(self.vector, other.vector) / (norm_a * norm_b))
        return max(-1.0, min(1.0, result))

    def resonates_with_field(self, field_vector: npt.NDArray[np.float32]) -> float:
        """
        How much does this edge resonate with a semantic field vector?

        Reading sessions create field vectors. This computes alignment.
        High resonance means this edge is relevant in this context.

        Args:
            field_vector: Semantic field from a reading session

        Returns:
            Cosine similarity in [-1, 1]. Positive = resonance, negative = suppression
        """
        if self.vector is None:
            return 0.0

        norm_edge = np.linalg.norm(self.vector)
        norm_field = np.linalg.norm(field_vector)

        if norm_edge == 0.0 or norm_field == 0.0:
            return 0.0

        # Clamp to [-1, 1] to handle float precision
        result = float(np.dot(self.vector, field_vector) / (norm_edge * norm_field))
        return max(-1.0, min(1.0, result))

    def __repr__(self) -> str:
        """Human-readable representation."""
        kind_str = f" [{self.kind}]" if self.kind else ""
        conf_str = f" (conf={self.confidence:.2f})"
        return f"{self.source} --[{self.relationship}]--> {self.target}{kind_str}{conf_str}"
