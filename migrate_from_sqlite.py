"""
Migrate contemplative edges from old bro_graph.sqlite into bro-engine.

Filters out code introspection edges (calls, has_parameter, etc.)
and migrates the remaining ~8k contemplative edges.

Usage:
    python migrate_from_sqlite.py --dry-run
    python migrate_from_sqlite.py --apply
    python migrate_from_sqlite.py --apply --source /path/to/bro_graph.sqlite
"""

import argparse
import json
import sqlite3
import os
import sys
from pathlib import Path

# Add bro-engine to path
sys.path.insert(0, str(Path(__file__).parent))

from bro_engine.graph_store.edge import Edge
from bro_engine.graph_store.graph_store import GraphStore

# These are implementation-level edges about bro's own code structure.
# Not contemplative knowledge — just AST introspection.
CODE_RELATIONSHIPS = {
    'calls', 'has_parameter', 'contains_code', 'has_method', 'returns',
    'has_function', 'has_class', 'same_relationship_as', 'appears_at_rope_position',
    'inherits_from', 'imports_from', 'imports', 'has_heading',
}

# Sources that are clearly artifacts/data-entry noise, not knowledge
BLOCKED_SOURCES = {
    'reconcile_locations',
}

SQLITE_PATH = Path(__file__).parent.parent / 'bro' / 'bro_graph.sqlite'
BRO_ENGINE_DB = os.environ.get('BRO_ENGINE_DB', 'postgresql:///bro_engine')
MIGRATION_VIA = 'migrated_from_bro_sqlite'


def load_contemplative_edges(sqlite_path: Path) -> list[dict]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    rel_placeholders = ','.join('?' * len(CODE_RELATIONSHIPS))
    src_placeholders = ','.join('?' * len(BLOCKED_SOURCES))
    rows = conn.execute(f"""
        SELECT source, relationship, target, confidence, via, context, qualifiers
        FROM edges
        WHERE relationship NOT IN ({rel_placeholders})
          AND source NOT IN ({src_placeholders})
        ORDER BY confidence DESC
    """, list(CODE_RELATIONSHIPS) + list(BLOCKED_SOURCES)).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def migrate(sqlite_path: Path, dry_run: bool = True):
    print(f"Source: {sqlite_path}")
    print(f"Target: {BRO_ENGINE_DB}")
    print()

    edges = load_contemplative_edges(sqlite_path)
    print(f"Contemplative edges found: {len(edges)}")

    if dry_run:
        print()
        print("--- DRY RUN: top 20 edges ---")
        for e in edges[:20]:
            via = e['via'] or '(untagged)'
            print(f"  {e['confidence']:.2f}  {e['source']} --[{e['relationship']}]--> {e['target']}  via={via}")
        print(f"  ... and {len(edges) - 20} more")
        print()
        print("Run with --apply to migrate.")
        return

    store = GraphStore(BRO_ENGINE_DB)

    skipped = 0
    migrated = 0
    errors = 0

    print("Migrating...")
    for row in edges:
        confidence = float(row['confidence'] or 0.5)

        if confidence >= 0.95:
            kind = 'founding_edge'
        else:
            kind = None

        original_via = row['via'] or ''
        qualifiers = []
        if original_via:
            qualifiers.append(f"original_via:{original_via}")

        try:
            edge = Edge(
                source=row['source'],
                relationship=row['relationship'],
                target=row['target'],
                confidence=min(confidence, 1.0),
                via=MIGRATION_VIA,
                kind=kind,
                qualifiers=qualifiers,
            )

            with store.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO edges (
                            source, relationship, target, confidence, via,
                            kind, properties, qualifiers, touch_count, last_touched_at
                        ) VALUES (
                            %(source)s, %(relationship)s, %(target)s, %(confidence)s, %(via)s,
                            %(kind)s, %(properties)s::jsonb, %(qualifiers)s::jsonb,
                            1, NOW()
                        )
                    """, {
                        "source": edge.source,
                        "relationship": edge.relationship,
                        "target": edge.target,
                        "confidence": edge.confidence,
                        "via": edge.via,
                        "kind": edge.kind,
                        "properties": '{}',
                        "qualifiers": json.dumps(edge.qualifiers),
                    })
                migrated += 1

        except Exception as ex:
            errors += 1
            if errors <= 5:
                print(f"  ERROR: {row['source']} --[{row['relationship']}]--> {row['target']}: {ex}")

    store.close()

    print(f"Done.")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate contemplative edges from bro sqlite to bro-engine')
    parser.add_argument('--apply', action='store_true', help='Actually migrate (default is dry run)')
    parser.add_argument('--source', default=str(SQLITE_PATH), help='Path to bro_graph.sqlite')
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"Error: sqlite file not found: {source}")
        sys.exit(1)

    migrate(source, dry_run=not args.apply)
