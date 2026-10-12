import pytest

from o2dpg_runner.graph import (
    build_adjacency, kahn_topological_order, descendants, ancestors,
    longest_path_length, invert_adj, root_nodes,
)


def test_adjacency_basic():
    # 0 -> 1 -> 2
    #      \-> 3
    fwd, rev, ind = build_adjacency(4, [(0, 1), (1, 2), (1, 3)])
    assert fwd == [[1], [2, 3], [], []]
    assert rev == [[], [0], [1], [1]]
    assert ind == [0, 1, 1, 1]


def test_kahn_simple_chain():
    fwd, _, ind = build_adjacency(3, [(0, 1), (1, 2)])
    assert kahn_topological_order(3, fwd, ind) == [0, 1, 2]


def test_kahn_diamond():
    # 0 -> 1, 0 -> 2, 1 -> 3, 2 -> 3
    fwd, _, ind = build_adjacency(4, [(0, 1), (0, 2), (1, 3), (2, 3)])
    order = kahn_topological_order(4, fwd, ind)
    assert order[0] == 0
    assert order[-1] == 3
    assert set(order[1:3]) == {1, 2}


def test_kahn_detects_cycle():
    fwd, _, ind = build_adjacency(3, [(0, 1), (1, 2), (2, 0)])
    with pytest.raises(ValueError):
        kahn_topological_order(3, fwd, ind)


def test_descendants_simple():
    # 0 -> 1 -> 2
    fwd, _, _ = build_adjacency(3, [(0, 1), (1, 2)])
    assert descendants(fwd, 0) == {1, 2}
    assert descendants(fwd, 1) == {2}
    assert descendants(fwd, 2) == set()


def test_descendants_diamond_memoized():
    fwd, _, _ = build_adjacency(4, [(0, 1), (0, 2), (1, 3), (2, 3)])
    cache = {}
    assert descendants(fwd, 0, cache) == {1, 2, 3}
    # call again - cache hit should return same result
    assert descendants(fwd, 0, cache) == {1, 2, 3}
    assert descendants(fwd, 1, cache) == {3}


def test_ancestors():
    fwd, rev, _ = build_adjacency(4, [(0, 1), (0, 2), (1, 3), (2, 3)])
    assert ancestors(rev, 3) == {0, 1, 2}
    assert ancestors(rev, 0) == set()


def test_invert_adj():
    fwd, _, _ = build_adjacency(4, [(0, 1), (0, 2), (1, 3)])
    rev = invert_adj(fwd)
    assert rev == [[], [0], [0], [1]]


def test_root_nodes():
    _, _, ind = build_adjacency(4, [(0, 2), (1, 2), (2, 3)])
    assert root_nodes(ind) == [0, 1]


def test_longest_path():
    # 0(w=1) -> 1(w=2) -> 3(w=4)
    # 0(w=1) -> 2(w=10) -> 3(w=4)
    fwd, _, ind = build_adjacency(4, [(0, 1), (0, 2), (1, 3), (2, 3)])
    topo = kahn_topological_order(4, fwd, ind)
    lp = longest_path_length(fwd, topo, [1.0, 2.0, 10.0, 4.0])
    # longest from 0: 0 -> 2 -> 3 = 1+10+4 = 15
    assert lp[0] == 15.0
    assert lp[3] == 4.0
    assert lp[2] == 14.0


def test_descendants_deep_chain_no_recursion_limit():
    # Chain of 2000 nodes -- would blow prototype's recursion limit
    N = 2000
    edges = [(i, i + 1) for i in range(N - 1)]
    fwd, _, _ = build_adjacency(N, edges)
    result = descendants(fwd, 0)
    assert len(result) == N - 1
