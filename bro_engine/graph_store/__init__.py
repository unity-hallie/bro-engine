"""
graph_store: Postgres substrate for edge storage with geometric properties.

The graph is the operating system. All knowledge lives as edges in a unified
geometric space. Reading sessions create semantic field vectors. Context
causes wave interference.

Core abstractions:
- Edge: knowledge triple + geometric point + inference item
- GraphStore: connection pooling, transactions, CRUD operations
- FieldVector: semantic context from reading sessions
- Query: compositional path finding, context-sensitive retrieval
"""

from .edge import Edge, EdgeKind

__all__ = ["Edge", "EdgeKind"]
