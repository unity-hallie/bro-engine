"""
Otter protocol — the combinatorial inference layer.

bro-engine is the canonical implementation and protocol source.
Descended from otter-centaur (unity-hallie/otter-centaur), the prototype
that proved the ideas. Not a dependency — a lineage.

Implement Graph to participate in the ecosystem.
"""

from .protocol import (
    Graph,
    OtterEdge,
    edge_combine,
    edge_subsumes,
    SymbolicEncoding,
    Frame,
    ConvergentProof,
    CausalDAG,
    CausalEvent,
    subdag,
    euler_product_complex,
    interference,
)
from .bridge import load_state, save_derived

__all__ = [
    "Graph",
    "OtterEdge",
    "edge_combine",
    "edge_subsumes",
    "SymbolicEncoding",
    "Frame",
    "ConvergentProof",
    "CausalDAG",
    "CausalEvent",
    "subdag",
    "euler_product_complex",
    "interference",
    "load_state",
    "save_derived",
]
