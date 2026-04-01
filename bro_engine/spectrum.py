"""
Spectrum: geometric analysis of hot edges.

The hypothesis: edges form a structure analogous to prime factorization,
and the geometry of that structure already encodes what the LLM discovers
during dreaming. If wave/spectral analysis on a batch of hot edges produces
predictions that match what the dreamer finds, we can eventually replace
the LLM call with math.

This is an instrument, not an engine. Clarity over performance.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh

from .graph_store import Edge, GraphStore
from .dream import fetch_hot_edges, dream_cycle

logger = logging.getLogger(__name__)


# =====================================================================
# Data structures for results
# =====================================================================

@dataclass
class Cluster:
    """A group of edges that say the same thing differently."""
    edges: list[Edge]
    centroid: np.ndarray
    avg_similarity: float

    def __repr__(self) -> str:
        labels = [f"{e.source}~{e.relationship}~>{e.target}" for e in self.edges]
        return f"Cluster({len(self.edges)} edges, avg_sim={self.avg_similarity:.3f}: {labels})"


@dataclass
class InterferencePattern:
    """Two edges that reinforce or cancel each other."""
    edge_a: Edge
    edge_b: Edge
    cosine_similarity: float
    confidence_alignment: float  # positive = same polarity, negative = opposing
    interference: float          # constructive (positive) or destructive (negative)

    @property
    def is_constructive(self) -> bool:
        return self.interference > 0

    def __repr__(self) -> str:
        kind = "constructive" if self.is_constructive else "destructive"
        return (f"Interference({kind}, {self.interference:+.3f}: "
                f"{self.edge_a.source}~>{self.edge_a.target} vs "
                f"{self.edge_b.source}~>{self.edge_b.target})")


@dataclass
class ResonancePrediction:
    """A predicted missing connection between two edges' nodes."""
    source_edge: Edge
    target_edge: Edge
    similarity: float
    shared_nodes: set
    missing_link: tuple[str, str]  # (node_from, node_to) that want a connection

    def __repr__(self) -> str:
        return (f"Resonance({self.missing_link[0]} ~?~> {self.missing_link[1]}, "
                f"sim={self.similarity:.3f})")


@dataclass
class SpectrumResult:
    """Full results of a spectrum analysis."""
    edges: list[Edge]
    similarity_matrix: np.ndarray
    clusters: list[Cluster]
    interference_patterns: list[InterferencePattern]
    eigenvalues: np.ndarray
    spectral_gap: float
    spectral_clusters: int
    resonance_predictions: list[ResonancePrediction]

    def print_report(self) -> None:
        """Print a human-readable report."""
        print()
        print("=" * 60)
        print("  SPECTRUM ANALYSIS")
        print("=" * 60)
        print(f"  Edges analyzed: {len(self.edges)}")
        print()

        # Similarity matrix shape
        n = len(self.edges)
        if n == 0:
            print("  No edges with embeddings. Nothing to see.")
            return

        # Clusters
        print(f"--- Clusters ({len(self.clusters)}) ---")
        print(f"  Edges that say the same thing differently.")
        print()
        for i, cluster in enumerate(self.clusters):
            print(f"  Cluster {i + 1} (avg similarity {cluster.avg_similarity:.3f}):")
            for edge in cluster.edges:
                print(f"    {edge}")
            print()

        # Interference
        constructive = [p for p in self.interference_patterns if p.is_constructive]
        destructive = [p for p in self.interference_patterns if not p.is_constructive]

        print(f"--- Interference ---")
        print(f"  Constructive (reinforce): {len(constructive)}")
        print(f"  Destructive (cancel/tension): {len(destructive)}")
        print()

        if destructive:
            print("  Tensions (geometric grief candidates):")
            for p in sorted(destructive, key=lambda x: x.interference)[:10]:
                print(f"    {p.interference:+.3f}  "
                      f"{p.edge_a.source}~{p.edge_a.relationship}~>{p.edge_a.target}")
                print(f"           vs  "
                      f"{p.edge_b.source}~{p.edge_b.relationship}~>{p.edge_b.target}")
            print()

        if constructive:
            print("  Reinforcements (top 5):")
            for p in sorted(constructive, key=lambda x: -x.interference)[:5]:
                print(f"    {p.interference:+.3f}  "
                      f"{p.edge_a.source}~{p.edge_a.relationship}~>{p.edge_a.target}")
                print(f"           and  "
                      f"{p.edge_b.source}~{p.edge_b.relationship}~>{p.edge_b.target}")
            print()

        # Spectral
        print(f"--- Spectral Decomposition ---")
        print(f"  Spectral gap: {self.spectral_gap:.4f}")
        if self.spectral_gap < 0.1:
            print(f"  (small gap — the graph is loosely connected, many communities)")
        elif self.spectral_gap > 0.5:
            print(f"  (large gap — the graph is tightly clustered, clear structure)")
        else:
            print(f"  (moderate gap — some structure, some sprawl)")

        print(f"  Estimated topic clusters: {self.spectral_clusters}")
        if len(self.eigenvalues) > 0:
            print(f"  Eigenvalue spectrum: {np.array2string(self.eigenvalues[:10], precision=4)}")
        print()

        # Resonance predictions
        print(f"--- Resonance Predictions ({len(self.resonance_predictions)}) ---")
        print(f"  Pairs of edges that want a connection between them.")
        print()
        for pred in self.resonance_predictions[:15]:
            print(f"  {pred.missing_link[0]} ~?~> {pred.missing_link[1]}  "
                  f"(similarity={pred.similarity:.3f})")
            print(f"    from: {pred.source_edge}")
            print(f"    to:   {pred.target_edge}")
            print()

        print("=" * 60)


# =====================================================================
# Core analysis functions
# =====================================================================

def cosine_similarity_matrix(edges: list[Edge]) -> np.ndarray:
    """
    Compute pairwise cosine similarity between all edges' embedding vectors.

    Returns an n x n matrix where M[i,j] is the cosine similarity between
    edge i and edge j. Uses the existing pgvector embeddings directly.
    """
    n = len(edges)
    if n == 0:
        return np.array([])

    # Stack vectors into a matrix
    vectors = np.stack([e.vector for e in edges])  # (n, 384)

    # Normalize each row
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)  # avoid division by zero
    normalized = vectors / norms

    # Cosine similarity is just dot product of normalized vectors
    similarity = normalized @ normalized.T

    # Clamp to [-1, 1] for float precision
    np.clip(similarity, -1.0, 1.0, out=similarity)

    return similarity


def cluster_edges(
    edges: list[Edge],
    similarity: np.ndarray,
    threshold: float = 0.7,
) -> list[Cluster]:
    """
    Cluster edges by cosine similarity using simple agglomerative approach.

    Edges with similarity above the threshold are grouped together.
    This is deliberately simple — we want to see what falls out
    before reaching for fancier methods.
    """
    n = len(edges)
    if n == 0:
        return []

    assigned = set()
    clusters = []

    # Greedy clustering: for each unassigned edge, gather its neighbors
    for i in range(n):
        if i in assigned:
            continue

        members = [i]
        assigned.add(i)

        for j in range(i + 1, n):
            if j in assigned:
                continue
            if similarity[i, j] >= threshold:
                members.append(j)
                assigned.add(j)

        if len(members) < 2:
            continue  # singletons aren't clusters

        cluster_edges_list = [edges[m] for m in members]
        cluster_vectors = np.stack([edges[m].vector for m in members])
        centroid = cluster_vectors.mean(axis=0)

        # Average pairwise similarity within the cluster
        if len(members) > 1:
            pair_sims = [similarity[a, b] for ii, a in enumerate(members)
                         for b in members[ii + 1:]]
            avg_sim = float(np.mean(pair_sims))
        else:
            avg_sim = 1.0

        clusters.append(Cluster(
            edges=cluster_edges_list,
            centroid=centroid,
            avg_similarity=avg_sim,
        ))

    return clusters


def compute_interference(
    edges: list[Edge],
    similarity: np.ndarray,
    sim_threshold: float = 0.4,
) -> list[InterferencePattern]:
    """
    For pairs of edges whose vectors are close, compute interference.

    Constructive interference: similar direction AND similar confidence polarity.
    The edges reinforce each other — the same signal from two sources.

    Destructive interference: similar direction BUT opposite confidence or
    contradictory content. The geometric version of grief detection.

    The interference score is: cosine_similarity * confidence_alignment
    where confidence_alignment = 1 - |conf_a - conf_b| for same-direction,
    and negated when confidences diverge strongly.
    """
    n = len(edges)
    patterns = []

    for i in range(n):
        for j in range(i + 1, n):
            sim = float(similarity[i, j])
            if abs(sim) < sim_threshold:
                continue  # not close enough to interfere

            edge_a = edges[i]
            edge_b = edges[j]

            # Confidence alignment: how similar are their epistemic stances?
            conf_diff = abs(edge_a.confidence - edge_b.confidence)

            # Check for contradiction signals:
            # 1. Same source+target but different relationship (competing claims)
            # 2. Same source+relationship but different target (forking assertion)
            contradicts = (
                (edge_a.source == edge_b.source and edge_a.target == edge_b.target
                 and edge_a.relationship != edge_b.relationship) or
                (edge_a.source == edge_b.source and edge_a.relationship == edge_b.relationship
                 and edge_a.target != edge_b.target)
            )

            if contradicts:
                # Destructive: high similarity in vector space but structural contradiction
                confidence_alignment = -(1.0 - conf_diff)
            else:
                # Alignment depends on confidence agreement
                confidence_alignment = 1.0 - conf_diff

            # Interference = how much the vectors point the same way * epistemic alignment
            interference = sim * confidence_alignment

            patterns.append(InterferencePattern(
                edge_a=edge_a,
                edge_b=edge_b,
                cosine_similarity=sim,
                confidence_alignment=confidence_alignment,
                interference=interference,
            ))

    return patterns


def spectral_analysis(
    similarity: np.ndarray,
    threshold: float = 0.3,
) -> tuple[np.ndarray, float, int]:
    """
    Build a similarity graph and compute its spectral decomposition.

    Nodes = edges, weighted connections = cosine similarity above threshold.
    Computes eigenvalues of the graph Laplacian. The spectral gap (difference
    between smallest nonzero eigenvalue and zero) tells you about community
    structure. Clusters in the spectrum correspond to topics the dreamer
    would notice.

    Returns:
        eigenvalues: sorted eigenvalues of the Laplacian
        spectral_gap: lambda_2 - lambda_1 (connectivity measure)
        n_clusters: estimated number of clusters (eigenvalues near zero)
    """
    n = similarity.shape[0]
    if n < 3:
        return np.array([]), 0.0, n

    # Build adjacency matrix: threshold the similarity
    adjacency = similarity.copy()
    adjacency[adjacency < threshold] = 0.0
    np.fill_diagonal(adjacency, 0.0)

    # Degree matrix
    degrees = adjacency.sum(axis=1)

    # Laplacian: L = D - A
    laplacian = np.diag(degrees) - adjacency

    # Compute eigenvalues
    # For small matrices, use dense eigenvalue computation
    k = min(n - 1, 20)  # number of eigenvalues to compute
    if n <= 50:
        eigenvalues = np.linalg.eigvalsh(laplacian)
    else:
        eigenvalues = eigsh(sparse.csr_matrix(laplacian), k=k,
                            which='SM', return_eigenvectors=False)
        eigenvalues = np.sort(eigenvalues)

    # Spectral gap: distance between the first and second smallest eigenvalues
    # The first eigenvalue is always ~0 for a connected graph
    eigenvalues_positive = eigenvalues[eigenvalues > 1e-10]
    spectral_gap = float(eigenvalues_positive[0]) if len(eigenvalues_positive) > 0 else 0.0

    # Estimate number of clusters: count eigenvalues near zero
    # (within an order of magnitude of the smallest positive eigenvalue)
    if spectral_gap > 0:
        near_zero = np.sum(eigenvalues < spectral_gap * 0.1)
    else:
        near_zero = n  # fully disconnected

    return eigenvalues, spectral_gap, int(near_zero)


def find_resonance(
    edges: list[Edge],
    similarity: np.ndarray,
    store: GraphStore,
    sim_threshold: float = 0.5,
) -> list[ResonancePrediction]:
    """
    From the similarity structure, predict which pairs of edges
    want a connecting edge between them.

    High similarity but no direct edge in the graph between their nodes —
    these are the connections the dreamer should find.
    """
    n = len(edges)
    predictions = []

    # Collect all nodes mentioned by these edges
    nodes = set()
    for e in edges:
        nodes.add(e.source)
        nodes.add(e.target)

    # Build a set of existing connections for quick lookup
    existing_connections: set[tuple[str, str]] = set()
    for e in edges:
        existing_connections.add((e.source, e.target))
        existing_connections.add((e.target, e.source))

    for i in range(n):
        for j in range(i + 1, n):
            sim = float(similarity[i, j])
            if sim < sim_threshold:
                continue

            edge_a = edges[i]
            edge_b = edges[j]

            # What nodes do they share?
            nodes_a = {edge_a.source, edge_a.target}
            nodes_b = {edge_b.source, edge_b.target}
            shared = nodes_a & nodes_b

            # Find node pairs that are NOT directly connected
            for na in nodes_a - shared:
                for nb in nodes_b - shared:
                    if (na, nb) in existing_connections:
                        continue
                    if na == nb:
                        continue

                    predictions.append(ResonancePrediction(
                        source_edge=edge_a,
                        target_edge=edge_b,
                        similarity=sim,
                        shared_nodes=shared,
                        missing_link=(na, nb),
                    ))

    # Deduplicate by missing_link, keeping highest similarity
    seen: dict[tuple[str, str], ResonancePrediction] = {}
    for pred in predictions:
        key = pred.missing_link
        reverse_key = (key[1], key[0])
        existing = seen.get(key) or seen.get(reverse_key)
        if existing is None or pred.similarity > existing.similarity:
            seen[key] = pred

    result = sorted(seen.values(), key=lambda p: -p.similarity)
    return result


# =====================================================================
# Main entry point
# =====================================================================

def run_spectrum(
    store: GraphStore,
    batch_size: int = 30,
    cluster_threshold: float = 0.7,
    interference_threshold: float = 0.4,
    spectral_threshold: float = 0.3,
    resonance_threshold: float = 0.5,
) -> SpectrumResult:
    """
    Run the full spectrum analysis on current hot edges.

    Pulls the same batch the dream system sees and does geometric analysis:
    cosine similarity, clustering, interference, spectral decomposition,
    and resonance prediction.
    """
    # Pull the same hot edges the dreamer sees
    hot_edges = fetch_hot_edges(store, batch_size=batch_size)

    # Filter to edges that have embeddings
    edges_with_vectors = [e for e in hot_edges if e.vector is not None]

    if not edges_with_vectors:
        logger.info("No hot edges with embeddings. Nothing to analyze.")
        return SpectrumResult(
            edges=[],
            similarity_matrix=np.array([]),
            clusters=[],
            interference_patterns=[],
            eigenvalues=np.array([]),
            spectral_gap=0.0,
            spectral_clusters=0,
            resonance_predictions=[],
        )

    logger.info(f"Analyzing {len(edges_with_vectors)} hot edges "
                f"({len(hot_edges) - len(edges_with_vectors)} without embeddings, skipped)")

    # 1. Cosine similarity matrix
    sim = cosine_similarity_matrix(edges_with_vectors)

    # 2. Clustering
    clusters = cluster_edges(edges_with_vectors, sim, threshold=cluster_threshold)

    # 3. Interference patterns
    interference = compute_interference(edges_with_vectors, sim,
                                        sim_threshold=interference_threshold)

    # 4. Spectral analysis
    eigenvalues, spectral_gap, n_clusters = spectral_analysis(
        sim, threshold=spectral_threshold)

    # 5. Resonance predictions
    resonance = find_resonance(edges_with_vectors, sim, store,
                               sim_threshold=resonance_threshold)

    return SpectrumResult(
        edges=edges_with_vectors,
        similarity_matrix=sim,
        clusters=clusters,
        interference_patterns=interference,
        eigenvalues=eigenvalues,
        spectral_gap=spectral_gap,
        spectral_clusters=n_clusters,
        resonance_predictions=resonance,
    )


# =====================================================================
# Comparison harness
# =====================================================================

def compare_dream_and_spectrum(
    store: GraphStore,
    batch_size: int = 30,
    dream_results: Optional[dict] = None,
) -> None:
    """
    Pull the same hot edges, run spectrum analysis and one dream cycle,
    compare what the math finds vs what the LLM finds.

    If dream_results is provided, uses those instead of running a new cycle.
    """
    print()
    print("=" * 60)
    print("  SPECTRUM vs DREAM: CONVERGENCE TEST")
    print("=" * 60)
    print()

    # 1. Run spectrum
    print("Running spectrum analysis...")
    spectrum = run_spectrum(store, batch_size=batch_size)

    if not spectrum.edges:
        print("No hot edges with embeddings. Nothing to compare.")
        return

    spectrum.print_report()

    # 2. Run dream (or use provided results)
    if dream_results is None:
        print("Running dream cycle (dry run)...")
        dream_results = dream_cycle(store, batch_size=batch_size, dry_run=True)

    if dream_results.get("skipped"):
        print("Dream found nothing. The graph is cool.")
        print()
        return

    raw = dream_results.get("raw", {})
    dream_connections = raw.get("connections", [])
    dream_grief = raw.get("grief", [])

    print()
    print("=" * 60)
    print("  DREAM RESULTS")
    print("=" * 60)
    print(f"  Connections found: {len(dream_connections)}")
    for conn in dream_connections:
        print(f"    {conn.get('source')} ~{conn.get('relationship')}~> {conn.get('target')}")
        print(f"      reason: {conn.get('reason', '')}")
    print(f"  Grief markers: {len(dream_grief)}")
    for g in dream_grief:
        print(f"    edge {g.get('edge_id', '?')}: {g.get('reason', '')}")
    print()

    # 3. Compare: clusters vs connections
    print("=" * 60)
    print("  CONVERGENCE ANALYSIS")
    print("=" * 60)
    print()

    # Collect all nodes the dream connected
    dream_nodes = set()
    dream_pairs = set()
    for conn in dream_connections:
        s = conn.get("source", "")
        t = conn.get("target", "")
        dream_nodes.add(s)
        dream_nodes.add(t)
        dream_pairs.add((s, t))

    # Collect all nodes in spectrum clusters
    cluster_nodes = set()
    for cluster in spectrum.clusters:
        for edge in cluster.edges:
            cluster_nodes.add(edge.source)
            cluster_nodes.add(edge.target)

    # Collect resonance prediction pairs
    spectrum_pairs = set()
    for pred in spectrum.resonance_predictions:
        spectrum_pairs.add(pred.missing_link)
        spectrum_pairs.add((pred.missing_link[1], pred.missing_link[0]))

    # Overlap: did the spectrum predict connections the dream found?
    overlap = dream_pairs & spectrum_pairs
    node_overlap = dream_nodes & cluster_nodes

    print("  CLUSTER CONVERGENCE:")
    print(f"    Spectrum clusters: {len(spectrum.clusters)}")
    print(f"    Dream connections: {len(dream_connections)}")
    print(f"    Node overlap (dream nodes in spectrum clusters): {len(node_overlap)}")
    if dream_nodes:
        print(f"    Coverage: {len(node_overlap)}/{len(dream_nodes)} "
              f"({100 * len(node_overlap) / len(dream_nodes):.0f}%)")
    print()

    print("  RESONANCE CONVERGENCE:")
    print(f"    Spectrum predicted {len(spectrum.resonance_predictions)} missing links")
    print(f"    Dream found {len(dream_connections)} connections")
    print(f"    Exact pair overlap: {len(overlap) // 2}")  # divide by 2 for bidirectional
    if dream_pairs:
        coverage = len(overlap) / len(dream_pairs)
        print(f"    Coverage: {coverage:.0%}")
    print()

    print("  GRIEF CONVERGENCE:")
    destructive = [p for p in spectrum.interference_patterns if not p.is_constructive]
    print(f"    Spectrum destructive interference: {len(destructive)}")
    print(f"    Dream grief markers: {len(dream_grief)}")

    # Check if grieved edges appear in destructive interference
    grieved_ids = {g.get("edge_id") for g in dream_grief}
    destructive_ids = set()
    for p in destructive:
        if p.edge_a.id:
            destructive_ids.add(p.edge_a.id)
        if p.edge_b.id:
            destructive_ids.add(p.edge_b.id)

    grief_overlap = grieved_ids & destructive_ids
    print(f"    Overlap (dream-grieved edges in destructive interference): {len(grief_overlap)}")
    print()

    # Verdict
    print("  VERDICT:")
    signals = []
    if node_overlap:
        signals.append("Clusters and dream share nodes")
    if overlap:
        signals.append("Resonance predicted dream connections")
    if grief_overlap:
        signals.append("Destructive interference predicted grief")

    if signals:
        print("    CONVERGENCE SIGNAL:")
        for s in signals:
            print(f"      + {s}")
    else:
        print("    DIVERGENCE: Math and LLM found different things.")
        print("    This is also signal. What did the LLM see that geometry missed?")
        print("    What did geometry see that the LLM ignored?")

    print()
    print("=" * 60)
