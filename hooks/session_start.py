#!/usr/bin/env python3
"""
session_start.py — Claude Code SessionStart hook

Surfaces bro-engine graph state at session open:
  - stats (total, tiers)
  - founding edges (constitutional truths)
  - recent edges (last 7 days)
  - stale edges needing revalidation
  - hot edges (most recently touched)

Outputs JSON with additionalContext injected into Claude's context.

Environment:
    BRO_ENGINE_DB  — postgres connection string (default: postgresql:///bro_engine)
"""

import json
import os
import sys

import psycopg
from psycopg.rows import dict_row


DB = os.environ.get("BRO_ENGINE_DB", "postgresql:///bro_engine")


def fmt_edge(row: dict) -> str:
    conf = f"{row['confidence']:.2f}"
    return f"  [{conf}] {row['source']} —{row['relationship']}→ {row['target']}"


def run():
    try:
        with psycopg.connect(DB, row_factory=dict_row) as conn:
            lines = []

            # Stats
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as n FROM edges WHERE invalidated_at IS NULL")
                total = cur.fetchone()["n"]
                cur.execute("""
                    SELECT
                        SUM(CASE WHEN confidence >= 0.95 THEN 1 ELSE 0 END) as founding,
                        SUM(CASE WHEN confidence >= 0.7 AND confidence < 0.95 THEN 1 ELSE 0 END) as tested,
                        SUM(CASE WHEN confidence >= 0.4 AND confidence < 0.7 THEN 1 ELSE 0 END) as observed,
                        SUM(CASE WHEN confidence < 0.4 THEN 1 ELSE 0 END) as hypothesis,
                        SUM(CASE WHEN vector IS NOT NULL THEN 1 ELSE 0 END) as vectorized
                    FROM edges WHERE invalidated_at IS NULL
                """)
                s = cur.fetchone()

            lines.append(f"=== bro-engine graph ({total} edges) ===")
            lines.append(
                f"  founding:{s['founding']}  tested:{s['tested']}  "
                f"observed:{s['observed']}  hypothesis:{s['hypothesis']}  "
                f"vectorized:{s['vectorized']}"
            )

            # Founding edges
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source, relationship, target, confidence
                    FROM edges
                    WHERE invalidated_at IS NULL
                      AND (kind = 'founding_edge' OR confidence >= 0.95)
                    ORDER BY confidence DESC, ts DESC
                    LIMIT 8
                """)
                rows = cur.fetchall()
            if rows:
                lines.append("\nFounding edges:")
                lines.extend(fmt_edge(r) for r in rows)

            # Recent edges (last 7 days)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source, relationship, target, confidence, ts
                    FROM edges
                    WHERE invalidated_at IS NULL
                      AND ts > NOW() - INTERVAL '7 days'
                    ORDER BY ts DESC
                    LIMIT 10
                """)
                rows = cur.fetchall()
            if rows:
                lines.append("\nRecent (7d):")
                lines.extend(fmt_edge(r) for r in rows)

            # Hot edges (most active)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source, relationship, target, confidence, hot
                    FROM edges
                    WHERE invalidated_at IS NULL AND hot > 0.1
                    ORDER BY hot DESC
                    LIMIT 5
                """)
                rows = cur.fetchall()
            if rows:
                lines.append("\nHot (most active):")
                lines.extend(fmt_edge(r) for r in rows)

            # Stale edges
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source, relationship, target, confidence
                    FROM edges
                    WHERE invalidated_at IS NULL
                      AND (last_touched_at IS NULL OR last_touched_at < NOW() - INTERVAL '90 days')
                      AND confidence < 0.95
                    ORDER BY confidence ASC, ts ASC
                    LIMIT 5
                """)
                rows = cur.fetchall()
            if rows:
                lines.append("\nStale (needs revalidation):")
                lines.extend(fmt_edge(r) for r in rows)

            context = "\n".join(lines)
            print(json.dumps({"context": context}))

    except Exception as e:
        # Don't block the session on DB errors
        sys.stderr.write(f"[session_start hook] {e}\n")
        sys.exit(0)


if __name__ == "__main__":
    run()
