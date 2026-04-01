#!/usr/bin/env python3
"""
prompt_context.py — Claude Code UserPromptSubmit hook

Embeds the user's prompt and runs the active attention strategy
to surface relevant edges from bro-engine.

Attention strategies live in hooks/attention/*.py. Each exports:
    attend(prompt_vec, conn, top_k, min_sim) → list[dict]

Environment:
    BRO_ENGINE_DB        — postgres connection string (default: postgresql:///bro_engine)
    BRO_HOOK_TOP_K       — how many edges to surface (default: 12)
    BRO_HOOK_MIN_SIM     — minimum cosine similarity (default: 0.30)
    BRO_ATTENTION         — strategy name (default: node_fanout)
                            options: vector_only, node_fanout, hot_weighted
"""

import importlib
import json
import os
import sys

import psycopg
from psycopg.rows import dict_row


DB = os.environ.get("BRO_ENGINE_DB", "postgresql:///bro_engine")
TOP_K = int(os.environ.get("BRO_HOOK_TOP_K", "12"))
MIN_SIM = float(os.environ.get("BRO_HOOK_MIN_SIM", "0.30"))
def _read_strategy():
    env = os.environ.get("BRO_ATTENTION")
    if env:
        return env
    dotfile = os.path.expanduser("~/.bro_attention")
    if os.path.exists(dotfile):
        return open(dotfile).read().strip() or "node_fanout"
    return "node_fanout"

STRATEGY = _read_strategy()


def load_strategy(name):
    mod = importlib.import_module(f"attention.{name}")
    return mod.attend


def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def run():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        prompt = data.get("prompt", "")
        if not prompt.strip():
            sys.exit(0)
    except Exception:
        sys.exit(0)

    try:
        model = get_model()
        vec = model.encode(prompt, normalize_embeddings=True).tolist()
    except Exception as e:
        sys.stderr.write(f"[prompt_context hook] embed failed: {e}\n")
        sys.exit(0)

    try:
        attend = load_strategy(STRATEGY)
    except Exception as e:
        sys.stderr.write(f"[prompt_context hook] strategy '{STRATEGY}' failed: {e}\n")
        sys.exit(0)

    try:
        with psycopg.connect(DB, row_factory=dict_row) as conn:
            edges = attend(vec, conn, top_k=TOP_K, min_sim=MIN_SIM)

        if not edges:
            sys.exit(0)

        lines = [f"Graph context ({STRATEGY}, {len(edges)} edges):"]
        for e in edges:
            sim = f"{e.get('similarity', 0):.2f}"
            conf = f"{e['confidence']:.2f}"
            layer = e.get("layer", "?")
            obs = e.get("observations", 1)
            title = f" ({obs}x)" if obs > 1 else ""
            lines.append(
                f"  [{layer} {sim}~{conf}conf{title}] "
                f"{e['source']} —{e['relationship']}→ {e['target']}"
            )

        print(json.dumps({"context": "\n".join(lines)}))

    except Exception as e:
        sys.stderr.write(f"[prompt_context hook] db failed: {e}\n")
        sys.exit(0)


if __name__ == "__main__":
    run()
