#!/usr/bin/env python3
"""
embed_indexer.py — bro-engine semantic embedding daemon

Listens for new edges via postgres LISTEN/NOTIFY (channel: bro_new_edge).
Accumulates a batch, then embeds when system has enough free resources.
Falls back to polling for any edges that arrived before the daemon started.

Resource policy (tunable via env):
  - Won't start a batch if free RAM < BRO_MIN_FREE_RAM_GB (default 1.5 GB)
  - Batch size scales with free RAM: bigger headroom → bigger batch
  - Uses MPS (Apple Silicon) if available, otherwise CPU
  - Backs off to BRO_BUSY_SLEEP_S (default 60s) when resources are tight

Lifecycle:
  - Designed to run as a launchd agent (always-on, restarts on crash)
  - Handles SIGTERM gracefully (flushes pending batch before exit)
  - Logs to stdout/stderr (captured by launchd into log files)

Usage:
    python3 embed_indexer.py

Environment:
    BRO_ENGINE_DB       postgres connection string  (default: postgresql:///bro_engine)
    BRO_MIN_FREE_RAM_GB minimum free RAM in GB before batching  (default: 1.5)
    BRO_BATCH_MAX       hard cap on batch size  (default: 128)
    BRO_BATCH_TRIGGER   minimum pending edges to start a batch  (default: 4)
    BRO_FLUSH_AFTER_S   max seconds to wait before flushing anyway  (default: 30)
    BRO_BUSY_SLEEP_S    sleep when resources are tight  (default: 60)
    BRO_POLL_INTERVAL_S how often to sweep for missed edges  (default: 300)
"""

import logging
import os
import select
import signal
import sys
import time
from collections import deque
from typing import Optional

import numpy as np
import psutil
import psycopg
from psycopg.rows import dict_row

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [bro-embed] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

DB          = os.environ.get("BRO_ENGINE_DB",       "postgresql:///bro_engine")
MIN_FREE_GB = float(os.environ.get("BRO_MIN_FREE_RAM_GB", "1.5"))
BATCH_MAX   = int(os.environ.get("BRO_BATCH_MAX",       "128"))
BATCH_TRIG  = int(os.environ.get("BRO_BATCH_TRIGGER",     "4"))
FLUSH_AFTER = int(os.environ.get("BRO_FLUSH_AFTER_S",    "30"))
BUSY_SLEEP  = int(os.environ.get("BRO_BUSY_SLEEP_S",     "60"))
POLL_IVSL   = int(os.environ.get("BRO_POLL_INTERVAL_S", "300"))

# ── State ─────────────────────────────────────────────────────────────────────

_running       = True
_pending_ids: deque[str] = deque()   # edge UUIDs notified but not yet embedded
_last_notify   = 0.0                  # time of most recent notification
_last_poll     = 0.0                  # time of most recent sweep for missed edges


def _handle_signal(sig, _frame):
    global _running
    log.info(f"Signal {sig} — flushing and shutting down")
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT,  _handle_signal)


# ── Resource helpers ──────────────────────────────────────────────────────────

def free_ram_gb() -> float:
    return psutil.virtual_memory().available / (1024 ** 3)


def headroom_batch_size() -> int:
    """Return a batch size proportional to free RAM, capped at BATCH_MAX."""
    free = free_ram_gb()
    # rough heuristic: each 384-dim float32 vector + sentence overhead ~= 2 MB
    # allow 60% of free RAM for batch work
    estimated = int((free * 0.6 * 1024) / 2)
    return max(1, min(estimated, BATCH_MAX))


def device_label() -> str:
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


# ── Model ─────────────────────────────────────────────────────────────────────

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        device = device_label()
        log.info(f"Loading all-MiniLM-L6-v2 on {device}...")
        _model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        log.info("Model ready.")
    return _model


# ── DB helpers ────────────────────────────────────────────────────────────────

def fetch_rows_by_ids(conn, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT id, source, relationship, target
            FROM edges
            WHERE id = ANY(%s::uuid[])
              AND vector IS NULL
              AND invalidated_at IS NULL
        """, (ids,))
        return cur.fetchall()


def fetch_unvectorized(conn, limit: int) -> list[dict]:
    """Sweep for any edges that missed the NOTIFY (e.g. inserted before daemon started)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT id, source, relationship, target
            FROM edges
            WHERE vector IS NULL
              AND invalidated_at IS NULL
            ORDER BY ts DESC
            LIMIT %s
        """, (limit,))
        return cur.fetchall()


def write_vectors(conn, rows: list[dict], vectors: np.ndarray) -> int:
    with conn.cursor() as cur:
        for row, vec in zip(rows, vectors):
            cur.execute(
                "UPDATE edges SET vector = %s::vector WHERE id = %s::uuid",
                (vec.tolist(), row["id"]),
            )
    conn.commit()
    return len(rows)


def count_vectorized(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM edges WHERE vector IS NOT NULL AND invalidated_at IS NULL")
        return cur.fetchone()[0]


# ── Batch processing ──────────────────────────────────────────────────────────

def embed_batch(conn, rows: list[dict]) -> Optional[int]:
    if not rows:
        return 0

    free = free_ram_gb()
    if free < MIN_FREE_GB:
        log.warning(f"Low RAM ({free:.1f} GB free, need {MIN_FREE_GB} GB) — deferring batch of {len(rows)}")
        return None  # caller should re-enqueue

    model = get_model()
    texts = [f"{r['source']} {r['relationship']} {r['target']}" for r in rows]

    t0 = time.monotonic()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
    elapsed = time.monotonic() - t0

    n = write_vectors(conn, rows, vectors)
    log.info(f"Embedded {n} edges in {elapsed:.1f}s ({device_label()}, {free:.1f} GB free)")
    return n


def flush_pending(conn):
    """Drain _pending_ids and embed whatever is still unvectorized."""
    global _pending_ids

    ids = list(_pending_ids)
    _pending_ids.clear()

    rows = fetch_rows_by_ids(conn, ids) if ids else []

    # also grab any missed edges up to batch cap
    cap = headroom_batch_size()
    if len(rows) < cap:
        missed = fetch_unvectorized(conn, cap - len(rows))
        seen = {r["id"] for r in rows}
        rows.extend(r for r in missed if r["id"] not in seen)

    if not rows:
        return

    result = embed_batch(conn, rows)
    if result is None:
        # re-enqueue for next attempt
        for r in rows:
            _pending_ids.append(str(r["id"]))


# ── Main loop ─────────────────────────────────────────────────────────────────

def run():
    global _last_notify, _last_poll

    log.info(f"Connecting to {DB}")
    # Two connections: one for LISTEN (autocommit), one for queries/writes
    listen_conn  = psycopg.connect(DB, autocommit=True)
    work_conn    = psycopg.connect(DB)

    listen_conn.execute("LISTEN bro_new_edge")
    log.info("Listening on channel bro_new_edge")

    # Startup sweep
    startup_rows = fetch_unvectorized(work_conn, BATCH_MAX)
    if startup_rows:
        log.info(f"{len(startup_rows)} unvectorized edges found at startup — embedding now")
        embed_batch(work_conn, startup_rows)

    _last_poll = time.monotonic()

    try:
        while _running:
            # Poll the listen socket with a 5s timeout so we can check _running
            ready = select.select([listen_conn], [], [], 5.0)[0]

            if ready:
                for notify in listen_conn.notifies():
                    _pending_ids.append(notify.payload)
                    _last_notify = time.monotonic()
                    log.debug(f"Notified: edge {notify.payload}")

            now = time.monotonic()

            should_flush = (
                len(_pending_ids) >= BATCH_TRIG
                or (len(_pending_ids) > 0 and now - _last_notify >= FLUSH_AFTER)
            )

            if should_flush:
                free = free_ram_gb()
                if free >= MIN_FREE_GB:
                    flush_pending(work_conn)
                else:
                    log.info(f"Batch ready ({len(_pending_ids)} edges) but RAM low ({free:.1f} GB) — waiting {BUSY_SLEEP}s")
                    time.sleep(BUSY_SLEEP)

            # Periodic sweep for any edges that bypassed NOTIFY
            if now - _last_poll >= POLL_IVSL:
                missed = fetch_unvectorized(work_conn, BATCH_MAX)
                if missed:
                    log.info(f"Poll sweep: {len(missed)} unvectorized edges")
                    embed_batch(work_conn, missed)
                _last_poll = now

    finally:
        log.info("Flushing remaining batch before exit...")
        try:
            flush_pending(work_conn)
        except Exception as e:
            log.error(f"Final flush failed: {e}")
        listen_conn.close()
        work_conn.close()
        log.info("Shutdown complete.")


if __name__ == "__main__":
    run()
