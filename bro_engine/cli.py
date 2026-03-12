"""
bro-engine CLI

Wake up. Query the graph. Act. Log decisions. End.
The next instance reads what you wrote.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from .graph_store import Edge, GraphStore
from .session import begin_session, continue_session, end_session


def get_store() -> GraphStore:
    """Get GraphStore from environment or default."""
    conn_string = os.environ.get('BRO_ENGINE_DB', 'postgresql:///bro_engine')
    return GraphStore(conn_string)


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """bro-engine: A contemplative knowledge engine for polysynthetic edge composition."""
    pass


@cli.command()
def wake():
    """
    Bootstrap from the graph. Run this at session start.

    Surfaces founding edges, recent learning, and stale beliefs.
    """
    store = get_store()

    click.echo("=== Founding Edges (constitutional) ===")
    for edge in store.founding_edges(limit=15):
        click.echo(f"  {edge}")

    click.echo()
    click.echo("=== Recent Edges (last 7 days) ===")
    recent = store.recent_edges(limit=10)
    if recent:
        for edge in recent:
            click.echo(f"  {edge}")
    else:
        click.echo("  (none)")

    click.echo()
    click.echo("=== Stale Edges (need revalidation) ===")
    stale = store.stale_edges(limit=5)
    if stale:
        for edge in stale:
            click.echo(f"  {edge}")
    else:
        click.echo("  (none)")

    store.close()


@cli.command()
@click.argument('source')
@click.argument('relationship')
@click.argument('target')
@click.option('--confidence', '-c', default=0.6, help='Confidence (0-1)')
@click.option('--via', '-v', default='cli', help='Provenance')
@click.option('--kind', '-k', default=None, help='Edge kind')
def add(source: str, relationship: str, target: str, confidence: float, via: str, kind: Optional[str]):
    """
    Add an edge to the graph.

    Example: bro-engine add "bro" "learns" "from_mistakes" -c 0.7
    """
    store = get_store()

    edge = Edge(
        source=source,
        relationship=relationship,
        target=target,
        confidence=confidence,
        via=via,
        kind=kind,
    )

    edge_id = store.add_edge(edge)
    click.echo(f"Added: {edge}")
    click.echo(f"ID: {edge_id}")

    store.close()


@cli.command()
@click.option('--source', '-s', default=None, help='Filter by source')
@click.option('--relationship', '-r', default=None, help='Filter by relationship')
@click.option('--target', '-t', default=None, help='Filter by target')
@click.option('--via', default=None, help='Filter by provenance')
@click.option('--min-confidence', default=None, type=float, help='Minimum confidence')
@click.option('--limit', '-l', default=20, help='Maximum results')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def query(source, relationship, target, via, min_confidence, limit, as_json):
    """
    Query edges from the graph.

    Example: bro-engine query -s bro -r commits_to
    """
    store = get_store()

    edges = store.query_edges(
        source=source,
        relationship=relationship,
        target=target,
        via=via,
        min_confidence=min_confidence,
        limit=limit,
    )

    if as_json:
        result = [
            {
                'source': e.source,
                'relationship': e.relationship,
                'target': e.target,
                'confidence': e.confidence,
                'via': e.via,
                'kind': e.kind,
            }
            for e in edges
        ]
        click.echo(json.dumps(result, indent=2))
    else:
        for edge in edges:
            click.echo(f"  {edge}")
        click.echo(f"\n({len(edges)} edges)")

    store.close()


@cli.command()
@click.argument('edge_id')
@click.argument('reason')
def invalidate(edge_id: str, reason: str):
    """
    Soft-delete an edge.

    Example: bro-engine invalidate <uuid> "superseded by new understanding"
    """
    store = get_store()

    if store.invalidate_edge(edge_id, reason):
        click.echo(f"Invalidated edge {edge_id}")
    else:
        click.echo(f"Edge not found or already invalidated: {edge_id}")

    store.close()


@cli.command()
@click.argument('edge_id')
def touch(edge_id: str):
    """
    Mark an edge as referenced (attention mechanism).

    Example: bro-engine touch <uuid>
    """
    store = get_store()
    store.touch(edge_id)
    click.echo(f"Touched edge {edge_id}")
    store.close()


@cli.command()
def stats():
    """Show graph statistics."""
    store = get_store()

    with store.connection() as conn:
        with conn.cursor() as cur:
            # Total edges
            cur.execute("SELECT COUNT(*) as count FROM edges WHERE invalidated_at IS NULL")
            total = cur.fetchone()['count']

            # By confidence tier
            cur.execute("""
                SELECT
                    CASE
                        WHEN confidence >= 0.95 THEN 'founding (0.95+)'
                        WHEN confidence >= 0.7 THEN 'tested (0.7-0.95)'
                        WHEN confidence >= 0.4 THEN 'observed (0.4-0.7)'
                        ELSE 'hypothesis (<0.4)'
                    END as tier,
                    COUNT(*) as count
                FROM edges
                WHERE invalidated_at IS NULL
                GROUP BY tier
                ORDER BY tier
            """)
            tiers = cur.fetchall()

            # Top relationships
            cur.execute("""
                SELECT relationship, COUNT(*) as count
                FROM edges
                WHERE invalidated_at IS NULL
                GROUP BY relationship
                ORDER BY count DESC
                LIMIT 10
            """)
            rels = cur.fetchall()

            # Top sources
            cur.execute("""
                SELECT source, COUNT(*) as count
                FROM edges
                WHERE invalidated_at IS NULL
                GROUP BY source
                ORDER BY count DESC
                LIMIT 10
            """)
            sources = cur.fetchall()

    click.echo(f"Total edges: {total}")
    click.echo()
    click.echo("By confidence:")
    for row in tiers:
        click.echo(f"  {row['tier']}: {row['count']}")
    click.echo()
    click.echo("Top relationships:")
    for row in rels:
        click.echo(f"  {row['relationship']}: {row['count']}")
    click.echo()
    click.echo("Top sources:")
    for row in sources:
        click.echo(f"  {row['source']}: {row['count']}")

    store.close()


@cli.command()
@click.option('--apply', is_flag=True, help='Apply the schema (destructive!)')
def init(apply: bool):
    """
    Initialize the database schema.

    Requires PostgreSQL with pgvector extension.
    """
    if not apply:
        click.echo("This will create/recreate the bro_engine schema.")
        click.echo("Run with --apply to proceed.")
        click.echo()
        click.echo("Prerequisites:")
        click.echo("  brew install postgresql@18")
        click.echo("  brew services start postgresql@18")
        click.echo("  brew install pgvector")
        click.echo("  createdb bro_engine")
        return

    import subprocess
    schema_path = Path(__file__).parent / 'graph_store' / 'schema.sql'

    if not schema_path.exists():
        click.echo(f"Schema not found: {schema_path}")
        sys.exit(1)

    db_name = os.environ.get('BRO_ENGINE_DB', 'postgresql:///bro_engine')
    # Extract database name from connection string
    if '///' in db_name:
        db_name = db_name.split('///')[-1]

    result = subprocess.run(
        ['psql', '-d', db_name, '-f', str(schema_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        click.echo("Schema applied successfully.")
    else:
        click.echo(f"Error: {result.stderr}")
        sys.exit(1)


@cli.command()
@click.argument('truth_1')
@click.argument('truth_2')
@click.argument('truth_3')
@click.option('--name', '-n', default=None, help='Session name')
def begin(truth_1: str, truth_2: str, truth_3: str, name: Optional[str]):
    """
    Begin a session with three true things.

    The opening stretch. Orient through what you notice as true.

    Example: bro-engine begin "the graph is alive" "I am curious" "spring is coming"
    """
    store = get_store()

    result = begin_session(store, truth_1, truth_2, truth_3, session_name=name)

    click.echo(f"=== Session: {result['session_id']} ===")
    click.echo()
    click.echo("Truths:")
    for i, truth in enumerate(result['truths'], 1):
        click.echo(f"  {i}. {truth}")

    click.echo()
    click.echo(f"Concepts extracted: {', '.join(result['concepts'][:10])}")

    click.echo()
    click.echo("=== Resonant Edges ===")
    if result['resonant_edges']:
        for edge in result['resonant_edges'][:15]:
            click.echo(f"  {edge}")
    else:
        click.echo("  (no resonant edges found)")

    store.close()


@cli.command('truth')
@click.argument('session_id')
@click.argument('new_truth')
def add_truth(session_id: str, new_truth: str):
    """
    Add a truth to an ongoing session.

    As truths accumulate, more edges resonate.

    Example: bro-engine truth session_20260311_220000 "the thinking layer wants to flow"
    """
    store = get_store()

    result = continue_session(store, session_id, new_truth)

    click.echo(f"Added truth #{result['total_truths']}: {new_truth}")
    click.echo()
    click.echo(f"Concepts: {', '.join(result['concepts'][:10])}")
    click.echo()
    click.echo("=== Resonant Edges ===")
    for edge in result['resonant_edges'][:10]:
        click.echo(f"  {edge}")

    store.close()


@cli.command('end')
@click.argument('session_id')
@click.option('--summary', '-s', default=None, help='Session summary')
def end(session_id: str, summary: Optional[str]):
    """
    End a session.

    Example: bro-engine end session_20260311_220000 -s "discovered the thinking layer"
    """
    store = get_store()

    end_session(store, session_id, summary)

    click.echo(f"Session ended: {session_id}")
    if summary:
        click.echo(f"Summary: {summary}")

    store.close()


def main():
    cli()


if __name__ == '__main__':
    main()
