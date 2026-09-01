"""Graph utilities on the task DAG.

Nothing here knows about workflows, tasks, or resources -- it operates on
integer-indexed adjacency lists only. Pure, testable, no side effects.

Supersedes the recursive ``findAllTopologicalOrders`` and
``find_all_dependent_tasks`` in the original prototype, both of which had
bugs and needed sys.setrecursionlimit(100000) to survive diamond DAGs.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Set, Tuple


def build_adjacency(
    n_nodes: int, edges: Iterable[Tuple[int, int]]
) -> Tuple[List[List[int]], List[List[int]], List[int]]:
    """Return (forward_adj, reverse_adj, indegree) for ``n_nodes`` nodes.

    forward_adj[u] lists successors; reverse_adj[v] lists predecessors.
    """
    forward: List[List[int]] = [[] for _ in range(n_nodes)]
    reverse: List[List[int]] = [[] for _ in range(n_nodes)]
    indeg = [0] * n_nodes
    for u, v in edges:
        forward[u].append(v)
        reverse[v].append(u)
        indeg[v] += 1
    return forward, reverse, indeg


def kahn_topological_order(
    n_nodes: int,
    forward_adj: List[List[int]],
    indegree: List[int],
    tiebreak: List[int] = None,
) -> List[int]:
    """Deterministic topological order via Kahn's algorithm.

    ``tiebreak`` is an optional per-node integer used to break ties
    among ready nodes. Smaller tiebreak value first. If None, the
    node index is used (which is also deterministic).
    """
    if tiebreak is None:
        tiebreak = list(range(n_nodes))
    indeg = list(indegree)
    # Use a sorted list as a tiny priority queue; for small DAGs this is
    # fine, and ties are broken deterministically.
    ready = sorted([n for n in range(n_nodes) if indeg[n] == 0],
                   key=lambda n: (tiebreak[n], n))
    out: List[int] = []
    # Simple loop; no heap because re-sorting on small ready sets is cheap
    # and we want full determinism.
    while ready:
        u = ready.pop(0)
        out.append(u)
        for v in forward_adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                # insert keeping sorted-by-tiebreak
                lo, hi = 0, len(ready)
                key = (tiebreak[v], v)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if (tiebreak[ready[mid]], ready[mid]) < key:
                        lo = mid + 1
                    else:
                        hi = mid
                ready.insert(lo, v)
    if len(out) != n_nodes:
        raise ValueError("Graph has at least one cycle; topological sort impossible")
    return out


def descendants(
    forward_adj: List[List[int]], source: int, cache: Dict[int, Set[int]] = None
) -> Set[int]:
    """All nodes reachable from ``source`` (excluding ``source`` itself), memoized.

    Uses iterative DFS with post-order memoization. Safe on DAGs with
    diamonds and deep chains; no recursion limit concerns.
    """
    if cache is None:
        cache = {}
    if source in cache:
        return cache[source]

    # iterative post-order: process children first, then combine
    order: List[int] = []
    seen: Set[int] = set()
    stack: List[Tuple[int, int]] = [(source, 0)]
    while stack:
        node, child_idx = stack[-1]
        kids = forward_adj[node]
        if child_idx < len(kids):
            stack[-1] = (node, child_idx + 1)
            child = kids[child_idx]
            if child not in seen and child not in cache:
                seen.add(child)
                stack.append((child, 0))
        else:
            stack.pop()
            order.append(node)

    # Now assign cache entries in post-order (children before parents).
    for node in order:
        if node in cache:
            continue
        s: Set[int] = set()
        for child in forward_adj[node]:
            s.add(child)
            s |= cache.get(child, set())
        cache[node] = s
    return cache[source]


def ancestors(
    reverse_adj: List[List[int]], sink: int, cache: Dict[int, Set[int]] = None
) -> Set[int]:
    """All nodes that can reach ``sink`` (excluding sink itself), memoized."""
    # ancestors in forward graph == descendants in reverse graph
    return descendants(reverse_adj, sink, cache)


def longest_path_length(
    forward_adj: List[List[int]],
    topo_order: List[int],
    node_weight: List[float],
) -> List[float]:
    """Longest-path weight from each node to any leaf (inclusive of node).

    ``topo_order`` must be a valid topological ordering. Uses reverse
    traversal and DP. Used by CriticalPathPolicy.
    """
    n = len(node_weight)
    lp = list(node_weight)  # include own weight
    for u in reversed(topo_order):
        best_child = 0.0
        for v in forward_adj[u]:
            if lp[v] > best_child:
                best_child = lp[v]
        lp[u] = node_weight[u] + best_child
    return lp


def invert_adj(forward_adj: List[List[int]]) -> List[List[int]]:
    """Compute reverse adjacency from forward adjacency."""
    n = len(forward_adj)
    rev: List[List[int]] = [[] for _ in range(n)]
    for u in range(n):
        for v in forward_adj[u]:
            rev[v].append(u)
    return rev


def root_nodes(indegree: List[int]) -> List[int]:
    return [i for i, d in enumerate(indegree) if d == 0]
