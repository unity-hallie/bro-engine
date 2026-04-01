"""
GraphStore: The interface through which all graph access flows.

Connection pooling, transactions, CRUD operations. No more scattered connections.
The graph is the operating system.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Any, Generator
from uuid import UUID
import json

import numpy as np
import numpy.typing as npt
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .edge import Edge


class GraphStore:
    """
    Persistent graph storage with geometric properties.

    All graph access flows through this interface:
    - Connection pooling (no more 201 scattered connections)
    - Transaction management (atomic operations)
    - CRUD for edges
    - Geometric queries (vector similarity, field resonance)
    - Touch tracking (attention mechanism)
    """

    def __init__(self, connection_string: str, pool_size: int = 10):
        """
        Initialize the graph store.

        Args:
            connection_string: PostgreSQL connection string
            pool_size: Maximum connections in pool
        """
        self.connection_string = connection_string
        self._pool = ConnectionPool(
            connection_string,
            min_size=1,
            max_size=pool_size,
            kwargs={"row_factory": dict_row}
        )

    def close(self) -> None:
        """Close all connections in the pool."""
        self._pool.close()

    @contextmanager
    def connection(self) -> Generator:
        """Get a connection from the pool."""
        with self._pool.connection() as conn:
            yield conn

    @contextmanager
    def transaction(self) -> Generator:
        """
        Transaction context manager.

        All operations within the context are atomic.
        Rollback on exception, commit on success.
        """
        with self._pool.connection() as conn:
            with conn.transaction():
                yield conn

    # ==================== CRUD Operations ====================

    def add_edge(self, edge: Edge) -> UUID:
        """
        Add an edge to the graph.

        Args:
            edge: The edge to add

        Returns:
            UUID of the created edge
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO edges (
                        source, relationship, target, confidence, via,
                        vector, kind, properties, qualifiers,
                        touch_count, last_touched_at
                    ) VALUES (
                        %(source)s, %(relationship)s, %(target)s, %(confidence)s, %(via)s,
                        %(vector)s, %(kind)s, %(properties)s, %(qualifiers)s,
                        1, NOW()
                    )
                    RETURNING id
                """, {
                    "source": edge.source,
                    "relationship": edge.relationship,
                    "target": edge.target,
                    "confidence": edge.confidence,
                    "via": edge.via,
                    "vector": _vector_to_pg(edge.vector),
                    "kind": edge.kind,
                    "properties": Jsonb(edge.properties),
                    "qualifiers": Jsonb(edge.qualifiers),
                })
                result = cur.fetchone()
                return result["id"]

    def get_edge(self, edge_id: UUID) -> Optional[Edge]:
        """
        Retrieve an edge by ID.

        Args:
            edge_id: UUID of the edge

        Returns:
            Edge if found, None otherwise
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM edges WHERE id = %s
                """, (edge_id,))
                row = cur.fetchone()
                if row is None:
                    return None
                return _row_to_edge(row)

    def update_edge(self, edge_id: UUID, **kwargs) -> bool:
        """
        Update edge fields.

        Args:
            edge_id: UUID of the edge
            **kwargs: Fields to update (confidence, via, kind, properties, etc.)

        Returns:
            True if edge was updated, False if not found
        """
        if not kwargs:
            return False

        # Build SET clause dynamically
        set_parts = []
        params = {"id": edge_id}

        for key, value in kwargs.items():
            if key in ("source", "relationship", "target", "confidence", "via", "kind"):
                set_parts.append(f"{key} = %({key})s")
                params[key] = value
            elif key == "vector":
                set_parts.append("vector = %(vector)s")
                params["vector"] = _vector_to_pg(value)
            elif key == "properties":
                set_parts.append("properties = %(properties)s")
                params["properties"] = Jsonb(value)
            elif key == "qualifiers":
                set_parts.append("qualifiers = %(qualifiers)s")
                params["qualifiers"] = Jsonb(value)

        if not set_parts:
            return False

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    UPDATE edges
                    SET {", ".join(set_parts)}
                    WHERE id = %(id)s AND invalidated_at IS NULL
                """, params)
                return cur.rowcount > 0

    def invalidate_edge(self, edge_id: UUID, reason: str) -> bool:
        """
        Soft-delete an edge.

        Args:
            edge_id: UUID of the edge
            reason: Why this edge is being invalidated

        Returns:
            True if edge was invalidated, False if not found
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE edges
                    SET invalidated_at = NOW(), invalidation_reason = %s
                    WHERE id = %s AND invalidated_at IS NULL
                """, (reason, edge_id))
                return cur.rowcount > 0

    # ==================== Query Operations ====================

    def query_edges(
        self,
        source: Optional[str] = None,
        relationship: Optional[str] = None,
        target: Optional[str] = None,
        kind: Optional[str] = None,
        via: Optional[str] = None,
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        include_invalid: bool = False,
        limit: int = 100,
    ) -> list[Edge]:
        """
        Query edges with flexible filters.

        Args:
            source: Filter by source
            relationship: Filter by relationship
            target: Filter by target
            kind: Filter by edge kind
            via: Filter by provenance
            min_confidence: Minimum confidence threshold
            max_confidence: Maximum confidence threshold
            include_invalid: Include invalidated edges
            limit: Maximum edges to return

        Returns:
            List of matching edges
        """
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if not include_invalid:
            conditions.append("invalidated_at IS NULL")

        if source is not None:
            conditions.append("source = %(source)s")
            params["source"] = source
        if relationship is not None:
            conditions.append("relationship = %(relationship)s")
            params["relationship"] = relationship
        if target is not None:
            conditions.append("target = %(target)s")
            params["target"] = target
        if kind is not None:
            conditions.append("kind = %(kind)s")
            params["kind"] = kind
        if via is not None:
            conditions.append("via = %(via)s")
            params["via"] = via
        if min_confidence is not None:
            conditions.append("confidence >= %(min_confidence)s")
            params["min_confidence"] = min_confidence
        if max_confidence is not None:
            conditions.append("confidence <= %(max_confidence)s")
            params["max_confidence"] = max_confidence

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT * FROM edges
                    WHERE {where_clause}
                    ORDER BY ts DESC
                    LIMIT %(limit)s
                """, params)
                return [_row_to_edge(row) for row in cur.fetchall()]

    def find_similar(
        self,
        vector: npt.NDArray[np.float32],
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> list[tuple[Edge, float]]:
        """
        Find edges similar to a query vector.

        Args:
            vector: Query vector (384 dimensions, all-MiniLM-L6-v2)
            limit: Maximum edges to return
            min_confidence: Minimum confidence threshold

        Returns:
            List of (edge, similarity) tuples, sorted by similarity descending
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT *, 1 - (vector <=> %(vector)s) AS similarity
                    FROM edges
                    WHERE invalidated_at IS NULL
                      AND vector IS NOT NULL
                      AND confidence >= %(min_confidence)s
                    ORDER BY vector <=> %(vector)s
                    LIMIT %(limit)s
                """, {
                    "vector": _vector_to_pg(vector),
                    "min_confidence": min_confidence,
                    "limit": limit,
                })
                return [
                    (_row_to_edge(row), row["similarity"])
                    for row in cur.fetchall()
                ]

    def edges_in_field(
        self,
        field_name: str,
        limit: int = 50,
        min_resonance: float = 0.3,
    ) -> list[tuple[Edge, float]]:
        """
        Find edges that resonate with a semantic field.

        Args:
            field_name: Name of the field vector
            limit: Maximum edges to return
            min_resonance: Minimum resonance threshold

        Returns:
            List of (edge, resonance) tuples
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                # Use the database function
                cur.execute("""
                    SELECT * FROM edges_in_field(%(field_name)s, %(limit)s, %(min_resonance)s)
                """, {
                    "field_name": field_name,
                    "limit": limit,
                    "min_resonance": min_resonance,
                })
                results = []
                for row in cur.fetchall():
                    edge = self.get_edge(row["id"])
                    if edge:
                        results.append((edge, row["resonance"]))
                return results

    # ==================== Touch Tracking ====================

    def touch(self, edge_id: UUID) -> bool:
        """
        Record that an edge was referenced (attention mechanism).

        Args:
            edge_id: UUID of the edge

        Returns:
            True if edge was touched, False if not found
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT touch_edge(%s)", (edge_id,))
                return True

    def query_derived_from(self, source: str, relationship: str, target: str) -> list[Edge]:
        """
        Find edges whose properties record derivation from a specific edge triple.

        Looks for properties->>'derived_from' matching the canonical triple string.
        """
        triple = f"{source} --[{relationship}]--> {target}"
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM edges
                    WHERE properties->>'derived_from' = %(triple)s
                    AND invalidated_at IS NULL
                    ORDER BY ts DESC
                """, {"triple": triple})
                return [_row_to_edge(row) for row in cur.fetchall()]

    def grief_active_relationships(self) -> list[str]:
        """
        Return all relationship names declared as grief-active.

        A relationship is grief-active when an edge exists:
            <relationship-name> --[is]--> grief-active

        These relationship types participate in grief cascade: when a node
        is grieved, edges using these relationships whose target matches
        the grieved node surface their sources as standing on grieved ground.
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source FROM edges
                    WHERE relationship = 'is'
                    AND target = 'grief-active'
                    AND invalidated_at IS NULL
                """)
                return [row['source'] for row in cur.fetchall()]

    def query_grief_dependents(self, node: str, grief_active_rels: list[str]) -> list[Edge]:
        """
        Find edges standing on grieved ground via grief-active relationships.

        For each grief-active relationship R: finds edges X --[R]--> node,
        meaning X depends on node being true. If node is grieved, X is downstream.
        """
        if not grief_active_rels:
            return []
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM edges
                    WHERE relationship = ANY(%(rels)s)
                    AND target = %(node)s
                    AND invalidated_at IS NULL
                    ORDER BY ts DESC
                """, {"rels": grief_active_rels, "node": node})
                return [_row_to_edge(row) for row in cur.fetchall()]

    def decay_hot_scores(self) -> int:
        """
        Decay hot scores across all edges.

        Should be run periodically (e.g., daily).

        Returns:
            Number of edges affected
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT decay_hot_scores()")
                cur.execute("""
                    SELECT COUNT(*) as count FROM edges
                    WHERE hot > 0.01 AND invalidated_at IS NULL
                """)
                result = cur.fetchone()
                return result["count"] if result else 0

    # ==================== View Accessors ====================

    def founding_edges(self, limit: int = 50) -> list[Edge]:
        """Get founding/constitutional edges."""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM edges_founding
                    ORDER BY ts ASC
                    LIMIT %s
                """, (limit,))
                return [_row_to_edge(row) for row in cur.fetchall()]

    def recent_edges(self, limit: int = 50) -> list[Edge]:
        """Get edges from the last 7 days."""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM edges_recent
                    ORDER BY ts DESC
                    LIMIT %s
                """, (limit,))
                return [_row_to_edge(row) for row in cur.fetchall()]

    def open_sessions(self, orphan_threshold_hours: int = 1) -> list[dict]:
        """
        Find sessions that were opened but never closed.

        A session is open if it has a began_at edge but no ended_at edge.
        Sessions older than orphan_threshold_hours are flagged as orphaned.

        Returns:
            List of dicts with session_id, opened_at, edge_count, orphaned
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        b.source as session_id,
                        b.target as opened_at,
                        b.ts as opened_ts,
                        COUNT(e.id) as edge_count
                    FROM edges b
                    LEFT JOIN edges e
                        ON e.via = b.source
                        AND e.invalidated_at IS NULL
                    WHERE b.relationship = 'began_at'
                      AND b.invalidated_at IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM edges x
                          WHERE x.source = b.source
                            AND x.relationship = 'ended_at'
                            AND x.invalidated_at IS NULL
                      )
                    GROUP BY b.source, b.target, b.ts
                    ORDER BY b.ts DESC
                """)
                rows = cur.fetchall()

        from datetime import timezone
        now = datetime.now(timezone.utc)
        result = []
        for row in rows:
            opened_ts = row["opened_ts"]
            if opened_ts and opened_ts.tzinfo is None:
                opened_ts = opened_ts.replace(tzinfo=timezone.utc)
            age_hours = (now - opened_ts).total_seconds() / 3600 if opened_ts else 0
            result.append({
                "session_id": row["session_id"],
                "opened_at": row["opened_at"],
                "edge_count": row["edge_count"],
                "orphaned": age_hours > orphan_threshold_hours,
                "age_hours": round(age_hours, 1),
            })
        return result

    def validate_session(self, session_id: str) -> bool:
        """
        Check if a session is currently open (began but not ended).

        Returns:
            True if session is valid and open, False otherwise
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM edges
                        WHERE source = %(sid)s
                          AND relationship = 'began_at'
                          AND invalidated_at IS NULL
                    ) as has_start,
                    EXISTS(
                        SELECT 1 FROM edges
                        WHERE source = %(sid)s
                          AND relationship = 'ended_at'
                          AND invalidated_at IS NULL
                    ) as has_end
                """, {"sid": session_id})
                row = cur.fetchone()
                return bool(row["has_start"] and not row["has_end"])

    def stale_edges(self, limit: int = 50) -> list[Edge]:
        """Get edges that haven't been touched in 90 days."""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM edges_stale
                    ORDER BY last_touched_at ASC NULLS FIRST
                    LIMIT %s
                """, (limit,))
                return [_row_to_edge(row) for row in cur.fetchall()]

    # ==================== Otter Protocol ====================

    def to_otter_edges(self, **kwargs) -> list:
        """
        Load edges in otter-legible form.

        Implements the Graph protocol. Maps bro-engine's field names
        to the otter wire format:
            source       -> subject
            relationship -> predicate
            target       -> object
            via          -> source (provenance)

        kwargs are passed through to query_edges for filtering.
        """
        from bro_engine.otter.protocol import OtterEdge
        edges = self.query_edges(**kwargs)
        return [
            OtterEdge(
                subject=e.source,
                predicate=e.relationship,
                object=e.target,
                confidence=e.confidence,
                source=(e.via,) if e.via else (),
            )
            for e in edges
        ]

    def from_otter_edges(self, edges: list, via: str) -> None:
        """
        Write derived edges back to the graph.

        Implements the Graph protocol. Maps otter wire format back to
        bro-engine's Edge. Derived edges get confidence capped at 0.6
        (observed pattern range) — they haven't been tested yet.
        """
        from bro_engine.otter.protocol import OtterEdge
        from .edge import Edge
        for oe in edges:
            if not isinstance(oe, OtterEdge):
                continue
            self.add_edge(Edge(
                source=oe.subject,
                relationship=oe.predicate,
                target=oe.object,
                confidence=min(oe.confidence, 0.6),
                via=via,
                kind="derived_edge",
            ))


# ==================== Helpers ====================

def _vector_to_pg(vector: Optional[npt.NDArray[np.float32]]) -> Optional[str]:
    """Convert numpy array to PostgreSQL vector string."""
    if vector is None:
        return None
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


def _row_to_edge(row: dict) -> Edge:
    """Convert database row to Edge object."""
    vector = None
    if row.get("vector"):
        # pgvector returns as string "[1,2,3,...]"
        vec_str = str(row["vector"])
        if vec_str.startswith("[") and vec_str.endswith("]"):
            vector = np.array(
                [float(x) for x in vec_str[1:-1].split(",")],
                dtype=np.float32
            )

    return Edge(
        source=row["source"],
        relationship=row["relationship"],
        target=row["target"],
        confidence=row["confidence"],
        via=row.get("via", ""),
        vector=vector,
        kind=row.get("kind"),
        properties=row.get("properties", {}),
        qualifiers=row.get("qualifiers", []),
        id=str(row["id"]),
        ts=row.get("ts"),
        touch_count=row.get("touch_count", 0),
        last_touched_at=row.get("last_touched_at"),
        signal=row.get("signal", 0.0),
        hot=row.get("hot", 0.0),
        invalidated_at=row.get("invalidated_at"),
        invalidation_reason=row.get("invalidation_reason"),
    )
