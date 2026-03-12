"""
The otter protocol.

bro-engine is the canonical source. Descended from otter-centaur
(unity-hallie/otter-centaur), the prototype that proved the ideas.

Three things live here:

  Graph         — the protocol. Implement to_otter_edges and
                  from_otter_edges and the otter loop can run over
                  your storage.

  Edge combine  — the standard combination function for edge-first
                  graphs. Two edges sharing a term compose into a new
                  one. Confidence is the product, capped at 0.7:
                  stay in sensing range, don't overclaim.

  Solvers       — SymbolicEncoding, Frame, euler_product_complex.
                  Three strategies for large-scale solves, chosen by
                  scale. Primes for small graphs, symbolic for large,
                  complex amplitude when primes would overflow.
"""

import math
import cmath
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable


# =====================================================================
# The Graph protocol
# =====================================================================

@runtime_checkable
class Graph(Protocol):
    """
    An otter-lineage persistent graph.

    Implement these two methods and the otter loop can run over your
    storage. The loop knows nothing about your schema, your lifecycle,
    or your confidence model — just edges and confidence.

    bro-engine's GraphStore is the reference implementation.
    """

    def to_otter_edges(self, **kwargs) -> list:
        """
        Load edges from the graph in otter-legible form.

        Returns a list of OtterEdge. kwargs are implementation-specific
        query parameters: confidence threshold, provenance filter, limit, etc.
        """
        ...

    def from_otter_edges(self, edges: list, via: str) -> None:
        """
        Write derived edges back to the graph.

        via: provenance — what session or process derived these edges.
        """
        ...


# =====================================================================
# OtterEdge — the wire format
# =====================================================================

@dataclass
class OtterEdge:
    """
    An edge in otter-legible form.

    The minimal representation the otter loop needs: subject, predicate,
    object, confidence. Source tracks provenance through derivation steps.

    Graphs translate to/from their native format via to_otter_edges and
    from_otter_edges. bro-engine maps:
        source       -> subject
        relationship -> predicate
        target       -> object
        via          -> source
    """
    subject: str
    predicate: str
    object: str
    confidence: float = 0.7
    source: tuple = field(default_factory=tuple)
    step: int = 0

    @property
    def name(self) -> str:
        return f"({self.subject} --{self.predicate}--> {self.object})"

    @property
    def terms(self) -> set:
        return {self.subject, self.object}

    def shares_term_with(self, other: "OtterEdge") -> set:
        return self.terms & other.terms

    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))

    def __eq__(self, other):
        return (isinstance(other, OtterEdge) and
                self.subject == other.subject and
                self.predicate == other.predicate and
                self.object == other.object)

    def __repr__(self):
        return f"OtterEdge({self.name}, conf={self.confidence:.2f})"


# =====================================================================
# Edge combine — the standard combination function
# =====================================================================

def edge_combine(x: OtterEdge, y: OtterEdge) -> list:
    """
    Combine two edges that share a term into a new edge.

    (alice --knows--> bob) + (bob --works_at--> acme)
    => (alice --knows_via_works_at--> acme)

    Confidence is the product, capped at 0.7. Stay in sensing range —
    derived knowledge is always less certain than what it came from.
    Don't overclaim.
    """
    shared = x.shares_term_with(y)
    if not shared:
        return []

    results = []
    for shared_term in shared:
        x_other = (x.terms - {shared_term}).pop() if (x.terms - {shared_term}) else None
        y_other = (y.terms - {shared_term}).pop() if (y.terms - {shared_term}) else None

        if x_other is None or y_other is None:
            continue
        if x_other == y_other:
            continue

        results.append(OtterEdge(
            subject=x_other,
            predicate=f"{x.predicate}_via_{y.predicate}",
            object=y_other,
            confidence=min(x.confidence * y.confidence, 0.7),
            source=(x.name, y.name),
        ))

    return results


def edge_subsumes(a: OtterEdge, b: OtterEdge) -> bool:
    """
    Edge a subsumes edge b if they connect the same nodes and a is more confident.

    A subsumed edge is redundant — the more confident edge already says
    everything it says, and more surely.
    """
    return (a.subject == b.subject and
            a.object == b.object and
            a.confidence >= b.confidence and
            a.predicate != b.predicate)


# =====================================================================
# Causal DAG — the structure solvers work over
# =====================================================================

@dataclass
class CausalEvent:
    """An event in a causal DAG."""
    name: str
    causes: frozenset = field(default_factory=frozenset)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, CausalEvent) and self.name == other.name

    def __repr__(self):
        if self.causes:
            return f"CausalEvent({self.name!r}, causes={set(self.causes)})"
        return f"CausalEvent({self.name!r})"


@dataclass
class CausalDAG:
    """A directed acyclic graph of causal events."""
    events: dict = field(default_factory=dict)

    def add(self, name: str, causes: list = None) -> "CausalDAG":
        self.events[name] = CausalEvent(name=name, causes=frozenset(causes or []))
        return self

    def roots(self) -> list:
        return [e for e in self.events.values() if not e.causes]

    def children(self, name: str) -> list:
        return [e for e in self.events.values() if name in e.causes]

    def ancestors(self, name: str) -> set:
        result = set()
        frontier = set(self.events[name].causes)
        while frontier:
            n = frontier.pop()
            if n not in result:
                result.add(n)
                frontier |= self.events[n].causes
        return result

    def topological_order(self) -> list:
        in_degree = {name: len(e.causes) for name, e in self.events.items()}
        queue = [name for name, d in in_degree.items() if d == 0]
        order = []
        while queue:
            name = queue.pop(0)
            order.append(name)
            for child in self.children(name):
                in_degree[child.name] -= 1
                if in_degree[child.name] == 0:
                    queue.append(child.name)
        return order


def subdag(dag: CausalDAG, event_names: set) -> CausalDAG:
    """Extract a sub-DAG — a localized reference frame."""
    sub = CausalDAG()
    for name in event_names:
        if name in dag.events:
            causes = dag.events[name].causes & event_names
            sub.events[name] = CausalEvent(name=name, causes=frozenset(causes))
    return sub


# =====================================================================
# Solvers
# =====================================================================

class SymbolicEncoding:
    """
    Causal geometry without prime assignment. Frame-invariant.

    Computes path counts, Gram matrix, and overlaps from DAG structure
    alone. Different gauge choices (prime assignments) produce the same
    geometry. Fix the gauge via Frame only when you need wave mechanics.

    Use for large graphs where integer Gödel numbers would overflow.
    """

    def __init__(self, dag: CausalDAG):
        self.dag = dag
        self._path_cache: dict = {}
        self._gram_cache: Optional[dict] = None

    def path_count(self, ancestor: str, descendant: str) -> int:
        key = (ancestor, descendant)
        if key not in self._path_cache:
            if ancestor == descendant:
                self._path_cache[key] = 1
            else:
                self._path_cache[key] = sum(
                    self.path_count(child.name, descendant)
                    for child in self.dag.children(ancestor)
                )
        return self._path_cache[key]

    def gram_matrix(self) -> dict:
        """G(X, Y) = Σ_E paths(E→X) · paths(E→Y). Frame-invariant."""
        if self._gram_cache is not None:
            return self._gram_cache

        names = self.dag.topological_order()
        matrix = {
            (x, y): sum(
                self.path_count(e, x) * self.path_count(e, y)
                for e in names
            )
            for x in names for y in names
        }
        self._gram_cache = {"matrix": matrix, "names": names}
        return self._gram_cache

    def overlap(self, a: str, b: str) -> float:
        """Causal overlap: G(a,b) / (||a|| · ||b||). Frame-invariant."""
        G = self.gram_matrix()["matrix"]
        na = math.sqrt(G[(a, a)])
        nb = math.sqrt(G[(b, b)])
        if na == 0 or nb == 0:
            return 0.0
        return G[(a, b)] / (na * nb)


class Frame:
    """
    A reference frame: a specific gauge choice over a symbolic encoding.

    Causal geometry (overlap, Gram matrix) is the same in all frames.
    Wave mechanics (amplitude, Born probability) are frame-dependent.

    Different frames are different observers of the same causal structure.
    interference() detects when two frames disagree.
    """

    def __init__(self, encoding: SymbolicEncoding, primes: Optional[dict] = None):
        self.encoding = encoding
        self.primes = primes or self._default_primes()
        self._gn: dict = {}
        self._build()

    def _default_primes(self) -> dict:
        order = self.encoding.dag.topological_order()
        p_list = _first_n_primes(len(order))
        return {name: p_list[i] for i, name in enumerate(order)}

    def _build(self):
        for name in self.encoding.dag.topological_order():
            gn = self.primes[name]
            for cause in self.encoding.dag.events[name].causes:
                gn *= self._gn[cause]
            self._gn[name] = gn

    def godel_number(self, name: str) -> int:
        return self._gn[name]

    def causes(self, a: str, b: str) -> bool:
        return self._gn[b] % self._gn[a] == 0

    def amplitude(self, name: str, t: float) -> complex:
        """ψ(E, t) = p_E^{-(1/2 + it)}. Each prime is a frequency."""
        return self.primes[name] ** (-(0.5 + 1j * t))

    def born_probability(self, name: str, t: float, names: list) -> float:
        """P(E) = |ψ(E,t)|² / Σ_F |ψ(F,t)|²"""
        amp = self.amplitude(name, t)
        total = sum(abs(self.amplitude(n, t)) ** 2 for n in names)
        return abs(amp) ** 2 / total if total > 0 else 0.0


def euler_product_complex(s: complex, num_primes: int = 100) -> complex:
    """
    ∏_{p≤P} 1/(1 - p^{-s}) for complex s.

    Use when prime factorization overflows. On the critical line
    s = 1/2 + it, causality becomes wave interference. Dips in
    |result| are nodes where causal threads destructively cancel.
    """
    product = complex(1.0)
    for p in _first_n_primes(num_primes):
        product *= 1.0 / (1.0 - p ** (-s))
    return product


def interference(frame_a: Frame, frame_b: Frame, name: str, t: float) -> float:
    """
    Re(ψ_A · conj(ψ_B)) — how much two frames agree on an event.

    Positive: constructive, frames agree.
    Negative: destructive, frames contradict.
    """
    return (frame_a.amplitude(name, t) * frame_b.amplitude(name, t).conjugate()).real


# =====================================================================
# Convergent proof
# =====================================================================

@dataclass
class ConvergentProof:
    """
    Confidence as a converging sequence.

    Tracks how certainty accumulates as evidence grows.
    is_cauchy() is the certificate that a solve has settled.
    Do not claim more certainty than the evidence supports.
    """
    conclusion: str
    steps: list  # list of (evidence_label, confidence | None)

    @property
    def confidences(self) -> list:
        return [(label, c) for label, c in self.steps if c is not None]

    @property
    def limit(self) -> Optional[float]:
        vals = [c for _, c in self.confidences]
        if len(vals) < 2:
            return vals[-1] if vals else None
        deltas = [vals[i+1] - vals[i] for i in range(len(vals) - 1)]
        if len(deltas) < 2 or deltas[-2] == 0:
            return vals[-1]
        ratio = deltas[-1] / deltas[-2]
        if abs(ratio) >= 1.0:
            return vals[-1]
        return min(1.0, vals[-1] + deltas[-1] * ratio / (1.0 - ratio))

    def is_cauchy(self, epsilon: float = 0.01) -> bool:
        """Practical convergence certificate."""
        vals = [c for _, c in self.confidences]
        if len(vals) < 4:
            return False
        tail = vals[len(vals) // 2:]
        return max(tail) - min(tail) < epsilon

    def __repr__(self):
        lim = self.limit
        return f"ConvergentProof({self.conclusion!r}, {len(self.confidences)} steps, limit≈{lim:.4f if lim else '?'})"


# =====================================================================
# Utilities
# =====================================================================

def _first_n_primes(n: int) -> list:
    primes: list = []
    candidate = 2
    while len(primes) < n:
        if all(candidate % p != 0 for p in primes):
            primes.append(candidate)
        candidate += 1
    return primes
