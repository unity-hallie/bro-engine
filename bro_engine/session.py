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
    truth_1: str,
    truth_2: str,
    truth_3: str,
    session_name: Optional[str] = None,
) -> dict:
    """
    Begin a session with three true things.

    Args:
        store: GraphStore connection
        truth_1, truth_2, truth_3: Three truths to orient the session
        session_name: Optional name (defaults to timestamp)

    Returns:
        Dict with session_id, truths, and resonant edges
    """
    # Create session token
    session_id = session_name or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Store session start as an event
    session_edge_id = store.add_edge(Edge(
        source=session_id,
        relationship="began_at",
        target=datetime.now().isoformat(),
        confidence=1.0,
        via=session_id,
        kind="founding_edge",
    ))

    # Store the three truths
    truths = [truth_1, truth_2, truth_3]
    truth_ids = []

    for i, truth in enumerate(truths, 1):
        edge_id = store.add_edge(Edge(
            source=session_id,
            relationship=f"truth_{i}",
            target=truth,
            confidence=0.95,
            via=session_id,
            kind="founding_edge",
        ))
        truth_ids.append(edge_id)

    # Extract concepts from truths for resonance matching
    concepts = extract_concepts(truths)

    # Find resonant edges
    resonant = find_resonant_edges(store, concepts, session_id)

    return {
        "session_id": session_id,
        "truths": truths,
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
    new_truth: str,
) -> dict:
    """
    Add a new truth to an ongoing session.

    As truths accumulate, more edges resonate.
    """
    # Get existing truths
    existing = store.query_edges(source=session_id, limit=10)
    truth_count = sum(1 for e in existing if e.relationship.startswith("truth_"))

    # Add new truth
    edge_id = store.add_edge(Edge(
        source=session_id,
        relationship=f"truth_{truth_count + 1}",
        target=new_truth,
        confidence=0.9,  # Slightly lower than opening truths
        via=session_id,
    ))

    # Extract concepts from all truths now
    all_truths = [e.target for e in existing if e.relationship.startswith("truth_")]
    all_truths.append(new_truth)

    concepts = extract_concepts(all_truths)
    resonant = find_resonant_edges(store, concepts, session_id)

    return {
        "session_id": session_id,
        "new_truth": new_truth,
        "total_truths": truth_count + 1,
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
        confidence=1.0,
        via=session_id,
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
