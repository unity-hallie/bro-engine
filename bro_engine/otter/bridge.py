"""
Bridge: load a Graph into the otter loop, write derived edges back.

This is the connection point between persistent storage and inference.
The loop doesn't know about your database — it just sees OtterEdges.
"""

from collections import deque
from .protocol import Graph, OtterEdge


class OtterState:
    """
    State of the otter loop.

    set_of_support: edges not yet focused on (the frontier)
    usable:         edges that have been focused on (exhausted)
    """

    def __init__(self):
        self.set_of_support: deque = deque()
        self.usable: list = []
        self.step: int = 0
        self.halted: bool = False
        self.halt_reason: str = ""


def load_state(graph: Graph, **kwargs) -> OtterState:
    """
    Load a graph's edges into an OtterState.

    All edges go into set_of_support — the frontier the otter loop
    will work through. Pass kwargs to filter what loads (confidence
    threshold, provenance, limit, etc.).
    """
    state = OtterState()
    for edge in graph.to_otter_edges(**kwargs):
        state.set_of_support.append(edge)
    return state


def save_derived(state: OtterState, graph: Graph, via: str) -> None:
    """
    Write derived edges from a completed otter run back to the graph.

    Reads from state.usable — edges that have been focused on and
    produced new items. Only writes OtterEdge instances.
    """
    derived = [e for e in state.usable if isinstance(e, OtterEdge)]
    if derived:
        graph.from_otter_edges(derived, via)


def otter_step(
    state: OtterState,
    combine_fn,
    subsumes_fn=None,
    choose_focus_fn=None,
    prune_fn=None,
    max_new_items: int = 50,
) -> OtterState:
    """One step of the otter loop."""
    if not state.set_of_support:
        state.halted = True
        state.halt_reason = "set_of_support empty"
        return state

    focus = choose_focus_fn(state.set_of_support) if choose_focus_fn else state.set_of_support.popleft()
    if choose_focus_fn:
        state.set_of_support.remove(focus)

    state.step += 1
    new_items = []

    for y in state.usable:
        for result in combine_fn(focus, y):
            all_known = set(state.set_of_support) | set(state.usable) | set(new_items)
            if result in all_known:
                continue
            if subsumes_fn and any(subsumes_fn(known, result) for known in all_known):
                continue
            if prune_fn and prune_fn(result, state):
                continue
            result.step = state.step
            new_items.append(result)
            if len(new_items) >= max_new_items:
                break
        if len(new_items) >= max_new_items:
            break

    if subsumes_fn:
        for new_item in new_items:
            to_remove = [
                existing for existing in list(state.set_of_support) + state.usable
                if subsumes_fn(new_item, existing)
            ]
            for item in to_remove:
                if item in state.set_of_support:
                    state.set_of_support.remove(item)
                if item in state.usable:
                    state.usable.remove(item)

    state.usable.append(focus)
    state.set_of_support.extend(new_items)
    return state


def run_otter(
    state: OtterState,
    combine_fn,
    max_steps: int = 100,
    stop_fn=None,
    **kwargs,
) -> OtterState:
    """Run the otter loop until halted, stop condition met, or max_steps reached."""
    for _ in range(max_steps):
        if state.halted:
            break
        if stop_fn and stop_fn(state):
            state.halted = True
            state.halt_reason = "stop condition met"
            break
        state = otter_step(state, combine_fn, **kwargs)
    return state
