"""
Property-based tests for Edge.

Using hypothesis to generate random edges and verify invariants.
Philosophy: If these properties hold for arbitrary edges, the abstraction is sound.
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st
from bro_engine.graph_store.edge import Edge, EdgeKind

# Test dimensions: small for property tests, production size for spot checks
TEST_DIMS = 8
PROD_DIMS = 512


# Hypothesis strategies for generating test data
@st.composite
def valid_edge(draw):
    """Generate a valid edge."""
    source = draw(st.text(min_size=1, max_size=100))
    target = draw(st.text(min_size=1, max_size=100))
    relationship = draw(st.text(min_size=1, max_size=100))

    # Confidence in valid range, respecting founding edge ceiling
    is_founding = draw(st.booleans())
    if is_founding:
        confidence = draw(st.floats(min_value=0.95, max_value=1.0))
        kind = "founding_edge"
    else:
        confidence = draw(st.floats(min_value=0.0, max_value=0.95))
        kind = draw(st.one_of(st.none(), st.just("simple_edge")))

    via = draw(st.text(max_size=200))

    return Edge(
        source=source,
        relationship=relationship,
        target=target,
        confidence=confidence,
        via=via,
        kind=kind,
    )


@st.composite
def edge_with_vector(draw, dims=TEST_DIMS):
    """Generate an edge with a non-zero geometric vector."""
    edge = draw(valid_edge())
    vec = draw(st.lists(
        st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False),
        min_size=dims, max_size=dims
    ))
    vec = np.array(vec, dtype=np.float32)
    # If all zeros, set first element to 1
    if np.linalg.norm(vec) == 0:
        vec[0] = 1.0
    vec = vec / np.linalg.norm(vec)
    edge.vector = vec
    return edge


class TestEdgeInvariants:
    """Test invariants that must hold for all edges."""

    @given(valid_edge())
    def test_confidence_bounds(self, edge: Edge):
        """Confidence must always be in [0, 1]."""
        assert 0.0 <= edge.confidence <= 1.0

    @given(valid_edge())
    def test_triple_consistency(self, edge: Edge):
        """Triple property must match (source, relationship, target)."""
        assert edge.triple == (edge.source, edge.relationship, edge.target)

    @given(valid_edge())
    def test_valid_edge_is_valid(self, edge: Edge):
        """Edges without invalidation timestamp are valid."""
        assert edge.is_valid is True
        edge.invalidated_at = "2026-03-09T00:00:00"  # Soft delete
        assert edge.is_valid is False

    @given(valid_edge())
    def test_founding_edge_semantics(self, edge: Edge):
        """Founding edges have confidence >= 0.95."""
        if edge.is_founding:
            assert edge.confidence >= 0.95

    def test_confidence_ceiling_for_non_founding(self):
        """Non-founding edges cannot have confidence > 0.95."""
        with pytest.raises(ValueError, match="reserved for founding edges"):
            Edge(
                source="test",
                relationship="test",
                target="test",
                confidence=0.97,
                kind="simple_edge",  # Not founding
            )

    def test_confidence_out_of_bounds_raises(self):
        """Confidence outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be in"):
            Edge(source="a", relationship="b", target="c", confidence=1.5)

        with pytest.raises(ValueError, match="Confidence must be in"):
            Edge(source="a", relationship="b", target="c", confidence=-0.1)


class TestGeometricOperations:
    """Test geometric properties and operations."""

    @given(edge_with_vector(), edge_with_vector())
    def test_cosine_similarity_bounds(self, edge1: Edge, edge2: Edge):
        """Cosine similarity is always in [-1, 1]."""
        sim = edge1.cosine_similarity(edge2)
        assert -1.0 <= sim <= 1.0

    @given(edge_with_vector())
    def test_self_similarity_is_one(self, edge: Edge):
        """An edge is maximally similar to itself."""
        sim = edge.cosine_similarity(edge)
        assert np.isclose(sim, 1.0, atol=1e-6)

    @given(edge_with_vector(), edge_with_vector())
    def test_similarity_is_symmetric(self, edge1: Edge, edge2: Edge):
        """Cosine similarity is symmetric."""
        sim1 = edge1.cosine_similarity(edge2)
        sim2 = edge2.cosine_similarity(edge1)
        assert np.isclose(sim1, sim2, atol=1e-6)

    @given(valid_edge(), valid_edge())
    def test_edges_without_vectors_have_zero_similarity(self, edge1: Edge, edge2: Edge):
        """Edges without vectors return 0.0 similarity."""
        edge1.vector = None
        edge2.vector = None
        assert edge1.cosine_similarity(edge2) == 0.0

    @given(edge_with_vector())
    def test_field_resonance_bounds(self, edge: Edge):
        """Field resonance is in [-1, 1]."""
        field = np.random.randn(TEST_DIMS).astype(np.float32)
        field = field / np.linalg.norm(field)
        resonance = edge.resonates_with_field(field)
        assert -1.0 <= resonance <= 1.0

    @given(edge_with_vector())
    def test_resonance_with_self_vector_is_one(self, edge: Edge):
        """Edge resonates maximally with its own vector."""
        if edge.vector is not None:
            resonance = edge.resonates_with_field(edge.vector)
            assert np.isclose(resonance, 1.0, atol=1e-6)

    def test_production_scale_vectors(self):
        """Spot check: geometric ops work at production dimensions (512)."""
        vec1 = np.random.randn(PROD_DIMS).astype(np.float32)
        vec1 = vec1 / np.linalg.norm(vec1)
        vec2 = np.random.randn(PROD_DIMS).astype(np.float32)
        vec2 = vec2 / np.linalg.norm(vec2)

        edge1 = Edge("a", "r", "b", 0.5, vector=vec1)
        edge2 = Edge("c", "r", "d", 0.5, vector=vec2)

        # Properties hold at production scale
        assert -1.0 <= edge1.cosine_similarity(edge2) <= 1.0
        assert np.isclose(edge1.cosine_similarity(edge1), 1.0, atol=1e-6)
        assert np.isclose(
            edge1.cosine_similarity(edge2),
            edge2.cosine_similarity(edge1),
            atol=1e-6
        )


class TestEdgeRepresentation:
    """Test string representation and debugging."""

    @given(valid_edge())
    def test_repr_contains_triple(self, edge: Edge):
        """String representation includes the triple."""
        repr_str = repr(edge)
        assert edge.source in repr_str
        assert edge.relationship in repr_str
        assert edge.target in repr_str

    @given(valid_edge())
    def test_repr_contains_confidence(self, edge: Edge):
        """String representation includes confidence."""
        repr_str = repr(edge)
        assert "conf=" in repr_str

    @given(valid_edge())
    def test_repr_includes_kind_when_present(self, edge: Edge):
        """String representation includes kind if not None."""
        if edge.kind:
            assert edge.kind in repr(edge)


class TestEdgeKind:
    """Test edge kind definitions."""

    def test_edge_kind_creation(self):
        """Can create edge kind definitions."""
        kind = EdgeKind(
            name="bayesian_edge",
            required_properties=["prior", "likelihood"],
            description="Bayesian inference edge",
        )
        assert kind.name == "bayesian_edge"
        assert "prior" in kind.required_properties

    def test_edge_kind_defaults(self):
        """Edge kind has sensible defaults."""
        kind = EdgeKind(name="test_kind")
        assert kind.required_properties == []
        assert kind.description is None
