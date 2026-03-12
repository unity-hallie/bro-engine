"""
Session initialization with three true things.

The opening stretch. Orient the self through what it notices as true.
Different sessions name different truths → parallax → triangulation.
"""

import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from .graph_store import Edge, GraphStore


def begin_session(
    store: GraphStore,
    truths: list[tuple[str, str, str]],
    session_name: Optional[str] = None,
    confidence: float = 0.85,
) -> dict:
    """
    Begin a session with three true edges.

    Args:
        store: GraphStore connection
        truths: List of (source, relationship, target) tuples - the three truths
        session_name: Optional name (defaults to timestamp)
        confidence: Confidence for the truth edges (default 0.85)

    Returns:
        Dict with session_id, truth_edges, and resonant edges
    """
    if len(truths) != 3:
        raise ValueError("Exactly three truths required for session start")

    # Create session token
    session_id = session_name or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Store session start as an event
    store.add_edge(Edge(
        source=session_id,
        relationship="began_at",
        target=datetime.now().isoformat(),
        confidence=0.95,
        via=session_id,
        kind="founding_edge",
    ))

    # Store the three truths as proper edges
    truth_edges = []
    concepts = []

    for source, relationship, target in truths:
        edge = Edge(
            source=source,
            relationship=relationship,
            target=target,
            confidence=confidence,
            via=session_id,
        )
        edge_id = store.add_edge(edge)
        truth_edges.append(edge)

        # Collect concepts from all parts
        concepts.extend([source, relationship, target])

    # Dedupe concepts
    concepts = list(dict.fromkeys(concepts))

    # Find resonant edges
    resonant = find_resonant_edges(store, concepts, session_id)

    return {
        "session_id": session_id,
        "truth_edges": truth_edges,
        "concepts": concepts,
        "resonant_edges": resonant,
    }


def extract_concepts(truths: list[str]) -> list[str]:
    """
    Extract key concepts from the three truths.

    Simple approach: split into words, filter stopwords,
    keep meaningful terms.
    """
    stopwords = {
        'i', 'me', 'my', 'the', 'a', 'an', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must',
        'and', 'or', 'but', 'if', 'then', 'than', 'that', 'this',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'it', 'its', "it's", 'they', 'them', 'their', 'we', 'us', 'our',
        'you', 'your', 'he', 'she', 'his', 'her', 'him',
        'what', 'which', 'who', 'whom', 'when', 'where', 'why', 'how',
        'all', 'each', 'every', 'both', 'few', 'more', 'most', 'some',
        'any', 'no', 'not', 'only', 'just', 'also', 'very', 'too',
        'can', 'now', 'way', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'under', 'again',
        'there', 'here', 'because', 'as', 'until', 'while', 'so',
        'feel', 'feels', 'feeling', 'felt', 'think', 'know', 'see',
        'get', 'got', 'like', 'want', 'need', 'take', 'make', 'go',
    }

    concepts = []
    for truth in truths:
        # Normalize and split
        words = re.findall(r'\b\w+\b', truth.lower())
        # Filter stopwords and short words
        meaningful = [w for w in words if w not in stopwords and len(w) > 2]
        concepts.extend(meaningful)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in concepts:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique


def find_resonant_edges(
    store: GraphStore,
    concepts: list[str],
    exclude_session: str,
    limit: int = 20,
) -> list[Edge]:
    """
    Find edges that resonate with the given concepts.

    Searches source, relationship, and target fields for concept matches.
    """
    if not concepts:
        return []

    resonant = []
    seen_ids = set()

    for concept in concepts:
        # Search in source
        for edge in store.query_edges(source=concept, limit=10):
            if edge.via != exclude_session and edge.id not in seen_ids:
                resonant.append(edge)
                seen_ids.add(edge.id)

        # Search in target
        for edge in store.query_edges(target=concept, limit=10):
            if edge.via != exclude_session and edge.id not in seen_ids:
                resonant.append(edge)
                seen_ids.add(edge.id)

    # Sort by confidence descending
    resonant.sort(key=lambda e: e.confidence, reverse=True)

    return resonant[:limit]


def continue_session(
    store: GraphStore,
    session_id: str,
    truth: tuple[str, str, str],
    confidence: float = 0.8,
) -> dict:
    """
    Add a new truth edge to an ongoing session.

    As truths accumulate, more edges resonate.
    """
    source, relationship, target = truth

    # Add new truth as proper edge
    edge = Edge(
        source=source,
        relationship=relationship,
        target=target,
        confidence=confidence,
        via=session_id,
    )
    store.add_edge(edge)

    # Get all edges from this session for resonance
    session_edges = store.query_edges(via=session_id, limit=50)

    # Collect concepts from all session edges
    concepts = []
    for e in session_edges:
        concepts.extend([e.source, e.relationship, e.target])
    concepts = list(dict.fromkeys(concepts))

    resonant = find_resonant_edges(store, concepts, session_id)

    return {
        "session_id": session_id,
        "new_truth": edge,
        "total_truths": len([e for e in session_edges if e.relationship not in ("began_at", "ended_at", "summary")]),
        "concepts": concepts,
        "resonant_edges": resonant,
    }


def end_session(
    store: GraphStore,
    session_id: str,
    summary: Optional[str] = None,
) -> str:
    """
    Mark a session as ended.

    Optionally add a summary edge.
    """
    store.add_edge(Edge(
        source=session_id,
        relationship="ended_at",
        target=datetime.now().isoformat(),
        confidence=0.95,
        via=session_id,
        kind="founding_edge",
    ))

    if summary:
        store.add_edge(Edge(
            source=session_id,
            relationship="summary",
            target=summary,
            confidence=0.85,
            via=session_id,
        ))

    return session_id
