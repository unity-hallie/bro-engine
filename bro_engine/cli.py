"""
bro-engine CLI

Wake up. Query the graph. Act. Log decisions. End.
The next instance reads what you wrote.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from .graph_store import Edge, GraphStore
from .session import begin_session, continue_session, end_session
from .dream import dream_cycle, dream_loop
from .spectrum import run_spectrum, compare_dream_and_spectrum


def get_store() -> GraphStore:
    """Get GraphStore from environment or default."""
    conn_string = os.environ.get('BRO_ENGINE_DB', 'postgresql:///bro_engine')
    return GraphStore(conn_string)


FRAME_FILE = Path.home() / '.bro_frame'
ATTENTION_FILE = Path.home() / '.bro_attention'


def get_frame() -> Optional[str]:
    """Read the current reference frame established by edge iam."""
    if FRAME_FILE.exists():
        return FRAME_FILE.read_text().strip() or None
    return None


def set_frame(identity: str) -> None:
    """Persist the current reference frame."""
    FRAME_FILE.write_text(identity)


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
@click.argument('identity')
@click.option('--via', '-v', default='qigong', help='Provenance')
def iam(identity: str, via: str):
    """
    Establish your reference frame.

    The opening gesture of qigong practice. Say who you are
    from where you are standing right now.

    Example: edge iam "claude-session-2026-03-12"
    """
    store = get_store()

    set_frame(identity)

    edge = Edge(
        source=identity,
        relationship="is-grounded-as",
        target="reference-frame",
        confidence=0.95,
        via=via,
        kind="founding_edge",
    )

    edge_id = store.add_edge(edge)
    click.echo(f"Grounded: {edge}")

    store.close()


ATTENTION_STRATEGIES = ['vector_only', 'node_fanout', 'hot_weighted', 'recent']


@cli.command()
@click.argument('strategy', required=False, default=None)
def attend(strategy: Optional[str]):
    """
    Set or show the attention strategy.

    How the graph activates when you speak.

    Examples:
        edge attend              # show current
        edge attend node_fanout  # set strategy
    """
    if strategy is None:
        current = ATTENTION_FILE.read_text().strip() if ATTENTION_FILE.exists() else 'node_fanout'
        click.echo(f"Attending: {current}")
        click.echo(f"Available: {', '.join(ATTENTION_STRATEGIES)}")
        return

    if strategy not in ATTENTION_STRATEGIES:
        click.echo(f"Unknown strategy: {strategy}")
        click.echo(f"Available: {', '.join(ATTENTION_STRATEGIES)}")
        sys.exit(1)

    ATTENTION_FILE.write_text(strategy)
    click.echo(f"Attending: {strategy}")


@cli.command('true')
@click.argument('source')
@click.argument('relationship')
@click.argument('target')
@click.option('--confidence', '-c', default=0.85, help='Confidence (default 0.85)')
@click.option('--via', '-v', default=None, help='Provenance (defaults to current frame)')
def add_true(source: str, relationship: str, target: str, confidence: float, via: str):
    """
    Assert a truth from where you are standing.

    Used in qigong opening and closing. Say what is true right now.

    Example: edge true this-session finds edges-are-real
    """
    store = get_store()
    frame = get_frame()
    via = via or frame or 'qigong'
    qualifiers = [f"frame:{frame}"] if frame else []

    edge = Edge(
        source=source,
        relationship=relationship,
        target=target,
        confidence=confidence,
        via=via,
        qualifiers=qualifiers,
    )

    edge_id = store.add_edge(edge)
    click.echo(f"True: {edge}")

    store.close()


@cli.command()
@click.argument('source')
@click.argument('relationship')
@click.argument('target')
@click.option('--confidence', '-c', default=0.6, help='Confidence (0-1)')
@click.option('--via', '-v', default=None, help='Provenance (defaults to current frame)')
@click.option('--kind', '-k', default=None, help='Edge kind')
@click.option('--phase', '-p', default=None,
              type=click.Choice(['volatile', 'fluid', 'salt']),
              help='Phase: volatile (re-precipitates), fluid (stable until broken), salt (consumed, becomes concrete)')
@click.option('--note', '-n', default=None, help='Annotation — what you found')
@click.option('--because', '-b', nargs=3, default=None, metavar='SOURCE RELATIONSHIP TARGET',
              help='Record that this edge is derived from another edge')
def add(source: str, relationship: str, target: str, confidence: float, via: str,
        kind: Optional[str], phase: Optional[str], note: Optional[str],
        because: Optional[tuple]):
    """
    Add an edge to the graph.

    Example: edge add this-session found edges-compose --phase fluid --note "via otter loop"
    Example: edge add B implies C --because A implies B
    """
    store = get_store()
    frame = get_frame()
    via = via or frame or 'cli'
    qualifiers = [f"frame:{frame}"] if frame else []

    properties = {}
    if phase:
        properties['phase'] = phase
    if note:
        properties['note'] = note
    if because:
        bs, br, bt = because
        properties['derived_from'] = f"{bs} --[{br}]--> {bt}"

    edge = Edge(
        source=source,
        relationship=relationship,
        target=target,
        confidence=confidence,
        via=via,
        kind=kind,
        properties=properties,
        qualifiers=qualifiers,
    )

    edge_id = store.add_edge(edge)
    click.echo(f"Added: {edge}")
    if phase:
        click.echo(f"Phase: {phase}")

    store.close()


@cli.command()
@click.argument('source')
@click.argument('relationship')
@click.argument('target')
@click.option('--now', default=None, help='What is true now (what superseded this)')
@click.option('--note', '-n', default=None, help='What you are holding')
def grieve(source: str, relationship: str, target: str, now: Optional[str], note: Optional[str]):
    """
    Grieve a truth that was real and is no longer current.

    Holds the old truth. Names the transition. Does not erase.
    Witnesses what was, from where you are now.

    Example: edge grieve bro uses bro_graph.sqlite --now postgresql
    """
    store = get_store()
    frame = get_frame()

    # Find the old edge(s)
    old_edges = store.query_edges(source=source, relationship=relationship, target=target)

    # Touch each — it was seen, not erased
    for e in old_edges:
        if e.id:
            store.touch(e.id)

    # Build grief properties
    properties: dict = {'grief': True}
    if note:
        properties['note'] = note

    # Compute interference if we have a current truth to grieve against
    if now:
        new_edges = store.query_edges(source=source, relationship=relationship, target=now)
        old_conf = max((e.confidence for e in old_edges), default=0.85)
        new_conf = max((e.confidence for e in new_edges), default=0.85)
        # Destructive: two truths, same predicate, different targets
        interference_score = -(old_conf * new_conf)
        properties['interference'] = round(interference_score, 3)
        properties['old_truth'] = f"{source} --[{relationship}]--> {target}"
        properties['new_truth'] = f"{source} --[{relationship}]--> {now}"

    # Grief edge
    qualifiers = ['grief']
    if frame:
        qualifiers.append(f"frame:{frame}")

    grief_target = f"superseded-by-{now}" if now else "held-in-past-frame"

    grief_edge = Edge(
        source=f"{source}-{relationship}-{target}",
        relationship='is-grieved-as',
        target=grief_target,
        confidence=0.85,
        via=frame or 'grief',
        qualifiers=qualifiers,
        properties=properties,
    )

    store.add_edge(grief_edge)

    # Output
    old_frame = None
    if old_edges:
        old_frame = next((q for q in old_edges[0].qualifiers if q.startswith('frame:')), None)

    click.echo(f"\nGrieved: {source} --[{relationship}]--> {target}")
    if old_edges:
        e = old_edges[0]
        frame_label = old_frame or 'unframed'
        click.echo(f"  was: conf={e.confidence}, via={e.via} ({frame_label})")
    else:
        click.echo(f"  was: (no edge found — grieving from memory)")
    if now:
        click.echo(f"  now: {source} --[{relationship}]--> {now}")
        click.echo(f"  interference: {properties.get('interference', 0):.3f}  (destructive)")
    click.echo(f"  held: {grief_edge.source} --[{grief_edge.relationship}]--> {grief_edge.target}")

    # Surface cascade — two mechanisms:
    # 1. Explicit: edges with derived_from in properties (--because)
    # 2. Implicit: edges using grief-active relationships pointing at grieved nodes
    grief_rels = store.grief_active_relationships()

    seen: set[str] = set()

    def surface_cascade(s: str, r: str, t: str, depth: int = 0) -> None:
        indent = "  " + ("  " * depth)
        dependents: list[Edge] = []

        # Explicit derivation
        dependents += store.query_derived_from(s, r, t)

        # Implicit: grief-active relationships pointing at the source or target nodes
        for node in (s, t):
            dependents += store.query_grief_dependents(node, grief_rels)

        for dep in dependents:
            key = f"{dep.source}-{dep.relationship}-{dep.target}"
            if key in seen:
                continue
            seen.add(key)
            click.echo(f"{indent}↳ {dep.source} --[{dep.relationship}]--> {dep.target}  "
                       f"[built on grieved ground]")
            surface_cascade(dep.source, dep.relationship, dep.target, depth + 1)

    # Seed seen with the grieved edge itself to avoid self-loops
    seen.add(f"{source}-{relationship}-{target}")

    click.echo(f"\n  Standing on grieved ground:")
    surface_cascade(source, relationship, target)
    if len(seen) == 1:
        click.echo(f"  (none found — declare relationships grief-active to enable cascade)")

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
                'qualifiers': e.qualifiers,
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
@click.option('--truth', '-t', nargs=3, multiple=True, required=True,
              help='A truth as three parts: source relationship target')
@click.option('--name', '-n', default=None, help='Session name')
@click.option('--confidence', '-c', default=0.85, help='Confidence for truths')
def begin(truth: tuple, name: Optional[str], confidence: float):
    """
    Begin a session with three true edges.

    The opening stretch. Orient through what you notice as true.

    Example:
        bro-engine begin \\
          -t this_session discovered events_are_edges \\
          -t thinking_layer wants_to flow \\
          -t I feel curious
    """
    if len(truth) != 3:
        click.echo("Error: Exactly three truths required (-t source rel target)")
        return

    store = get_store()

    truths = [(t[0], t[1], t[2]) for t in truth]
    result = begin_session(store, truths, session_name=name, confidence=confidence)

    click.echo(f"=== Session: {result['session_id']} ===")
    click.echo()
    click.echo("Truths:")
    for edge in result['truth_edges']:
        click.echo(f"  {edge}")

    click.echo()
    click.echo(f"Concepts: {', '.join(result['concepts'][:12])}")

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
@click.argument('source')
@click.argument('relationship')
@click.argument('target')
@click.option('--confidence', '-c', default=0.8, help='Confidence')
def add_truth(session_id: str, source: str, relationship: str, target: str, confidence: float):
    """
    Add a truth edge to an ongoing session.

    As truths accumulate, more edges resonate.

    Example: bro-engine truth session_20260311 thinking_layer wants_to flow
    """
    store = get_store()

    result = continue_session(store, session_id, (source, relationship, target), confidence)

    click.echo(f"Added: {result['new_truth']}")
    click.echo()
    click.echo(f"Concepts: {', '.join(result['concepts'][:12])}")
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


@cli.command()
@click.argument('name')
@click.option('--when', '-w', default=None, help='Timestamp (ISO format, e.g. 2025-12-22). Defaults to now.')
@click.option('--note', '-n', default=None, help='What happened')
@click.option('--after', '-a', default=None, help='Name of the preceding moment (explicit, no auto-linking)')
@click.option('--confidence', '-c', default=0.85, help='Confidence (default 0.85)')
@click.option('--via', '-v', default='cli', help='Provenance')
def moment(name: str, when: Optional[str], note: Optional[str], after: Optional[str],
           confidence: float, via: str):
    """
    Record a named moment in time.

    Moments are events — single points in time, not claims.
    They form an episodic chain via --after links.

    Example:
        edge moment solstice_ritual_2025-12-22 --when 2025-12-22 --note "winter solstice"
        edge moment bro_first_woke --when 2026-01-15 --after solstice_ritual_2025-12-22
    """
    store = get_store()

    # Resolve timestamp
    if when:
        try:
            # Accept date or datetime
            if 'T' in when or ' ' in when:
                ts = datetime.fromisoformat(when)
            else:
                ts = datetime.fromisoformat(when + 'T00:00:00')
            when_str = ts.isoformat()
        except ValueError:
            click.echo(f"Could not parse --when '{when}'. Use ISO format: 2025-12-22 or 2025-12-22T10:30:00")
            store.close()
            return
    else:
        when_str = datetime.now(timezone.utc).isoformat()

    properties = {'moment': True}
    if note:
        properties['note'] = note

    # The anchor edge: name --[happened_at]--> timestamp
    anchor = Edge(
        source=name,
        relationship='happened_at',
        target=when_str,
        confidence=confidence,
        via=via,
        kind='moment',
        properties=properties,
    )
    store.add_edge(anchor)
    click.echo(f"Moment: {name} --[happened_at]--> {when_str} (conf={confidence:.2f})")

    # Temporal link: explicit only
    if after:
        link = Edge(
            source=name,
            relationship='happened_after',
            target=after,
            confidence=confidence,
            via=via,
            kind='moment',
        )
        store.add_edge(link)
        click.echo(f"  --[happened_after]--> {after}")

    if note:
        click.echo(f"  note: {note}")

    store.close()


@cli.command()
@click.option('--limit', '-l', default=50, help='Maximum moments to show')
def moments(limit: int):
    """
    List moments in temporal order.

    Example: edge moments
    """
    store = get_store()

    edges = store.query_edges(relationship='happened_at', limit=limit)
    moment_edges = [e for e in edges if e.kind == 'moment']

    if not moment_edges:
        click.echo("No moments found.")
        store.close()
        return

    # Sort by the timestamp target
    def parse_ts(e):
        try:
            ts = e.target.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts)
            # Normalize to offset-naive UTC for sorting
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except (ValueError, AttributeError):
            return datetime.min

    moment_edges.sort(key=parse_ts)

    for e in moment_edges:
        note = e.properties.get('note', '')
        note_str = f"  — {note}" if note else ''
        click.echo(f"  {e.source} ({e.target[:10]}){note_str} (conf={e.confidence:.2f})")

    click.echo(f"\n({len(moment_edges)} moments)")
    store.close()


@cli.command('install-skills')
@click.option('--force', is_flag=True, help='Overwrite existing skill symlinks')
def install_skills(force: bool):
    """
    Install bro school skills globally for all Claude sessions.

    Symlinks .claude/skills/* into ~/.claude/skills/ so skills are
    available in any project, not just bro-engine.

    Example: edge install-skills
    """
    skills_src = Path(__file__).parent.parent / '.claude' / 'skills'
    skills_dst = Path.home() / '.claude' / 'skills'

    if not skills_src.exists():
        click.echo(f"Skills source not found: {skills_src}")
        return

    skills_dst.mkdir(parents=True, exist_ok=True)

    installed = []
    skipped = []

    for skill_dir in sorted(skills_src.iterdir()):
        if not skill_dir.is_dir():
            continue

        dst = skills_dst / skill_dir.name

        if dst.exists() or dst.is_symlink():
            if force:
                dst.unlink() if dst.is_symlink() else dst.rmdir()
            else:
                skipped.append(skill_dir.name)
                continue

        dst.symlink_to(skill_dir.resolve())
        installed.append(skill_dir.name)

    for name in installed:
        click.echo(f"  ✓ {name} → ~/.claude/skills/{name}")
    for name in skipped:
        click.echo(f"  ~ {name} (already exists, use --force to overwrite)")

    if installed:
        click.echo(f"\n{len(installed)} skill(s) installed. Restart Claude Code to pick them up.")
    else:
        click.echo("\nNo new skills installed.")


@cli.command()
@click.option('--once', is_flag=True, help='Run a single dream cycle and exit')
@click.option('--interval', default=600, type=int, help='Seconds between cycles (default 600)')
@click.option('--batch-size', default=30, type=int, help='Hot edges per cycle')
@click.option('--dry-run', is_flag=True, help='Show what would happen without writing')
def dream(once: bool, interval: int, batch_size: int, dry_run: bool):
    """
    Run the dream loop. Cooling for the graph.

    Pulls hot edges, surfaces them to a dreamer LLM, writes back
    connections it notices, grieves tensions it finds.

    Examples:
        bro-engine dream              # loop every 10 min
        bro-engine dream --once       # single cycle
        bro-engine dream --interval 300  # every 5 min
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [dream] %(message)s',
        datefmt='%H:%M:%S',
    )

    store = get_store()

    if once or dry_run:
        result = dream_cycle(store, batch_size=batch_size, dry_run=dry_run)

        if result.get("skipped"):
            click.echo("No hot edges. The graph is cool.")
        else:
            click.echo(f"Hot edges:    {result['hot_edges']}")
            click.echo(f"Connections:  {result['connections']}")
            click.echo(f"Grief:        {result['grief']}")
            if dry_run:
                click.echo("(dry run — nothing written)")

        store.close()
    else:
        click.echo(f"Dream loop starting. Interval: {interval}s. Ctrl+C to wake.")
        try:
            dream_loop(store, interval=interval, batch_size=batch_size)
        finally:
            store.close()


@cli.command()
@click.option('--compare', is_flag=True, help='Run both spectrum and dream, compare results')
@click.option('--batch-size', default=30, type=int, help='Hot edges to analyze')
@click.option('--cluster-threshold', default=0.7, type=float, help='Cosine similarity threshold for clustering')
@click.option('--resonance-threshold', default=0.5, type=float, help='Similarity threshold for resonance predictions')
def spectrum(compare: bool, batch_size: int, cluster_threshold: float, resonance_threshold: float):
    """
    Run spectrum analysis on current hot edges.

    Geometric instrument: cosine similarity, clustering, interference
    patterns, spectral decomposition, resonance prediction.

    Use --compare to run both spectrum and dream, then see where
    the math and the LLM converge or diverge.

    Examples:
        bro-engine spectrum                # geometric analysis only
        bro-engine spectrum --compare      # compare with dream
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [spectrum] %(message)s',
        datefmt='%H:%M:%S',
    )

    store = get_store()

    if compare:
        compare_dream_and_spectrum(store, batch_size=batch_size)
    else:
        result = run_spectrum(
            store,
            batch_size=batch_size,
            cluster_threshold=cluster_threshold,
            resonance_threshold=resonance_threshold,
        )
        result.print_report()

    store.close()


def main():
    cli()


if __name__ == '__main__':
    main()
