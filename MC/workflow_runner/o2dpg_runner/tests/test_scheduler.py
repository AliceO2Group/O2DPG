import pytest

from o2dpg_runner.resources import ResourceManager
from o2dpg_runner.scheduler import (
    TimeframeFirstPolicy, CriticalPathPolicy, BestFitBackfillPolicy, get_policy,
)
from o2dpg_runner.scheduler.base import SchedulerState


def _setup(n=4, cpu_limit=8.0, mem_limit=16000.0):
    """Create an RM with n tasks: all 2 cpu / 1000 mem."""
    rm = ResourceManager(cpu_limit=cpu_limit, mem_limit=mem_limit, n_backfill_max=1)
    for i in range(n):
        rm.add_task(f"t{i}", None, cpu=2, cpu_relative=1, mem=1000)
    return rm


def _make_state(n, tf=None, desc=None, cp=None):
    tf = tf if tf is not None else [0] * n
    desc = desc if desc is not None else [0] * n
    cp = cp if cp is not None else [1.0] * n
    return SchedulerState(
        timeframe_of=tf,
        descendants_count=desc,
        critical_path=cp,
        task_cpu=[2.0] * n,
        task_mem=[1000.0] * n,
        timeframe_weight=[(tf[i], desc[i]) for i in range(n)],
    )


def test_timeframe_policy_order():
    s = _make_state(4, tf=[1, 0, 1, 0], desc=[5, 2, 10, 1])
    p = TimeframeFirstPolicy()
    # timeframe 0 first, then within tf more descendants first
    order = p.order([0, 1, 2, 3], s)
    # tf 0: tasks 1 (desc=2) and 3 (desc=1) -> 1 before 3
    # tf 1: tasks 0 (desc=5) and 2 (desc=10) -> 2 before 0
    assert order == [1, 3, 2, 0]


def test_timeframe_policy_submit_default_fits_all():
    rm = _setup(n=4)  # 4 * 2cpu = 8 = cpu_limit
    s = _make_state(4)
    p = TimeframeFirstPolicy()
    picked = _drain(p.pick_submittable([0, 1, 2, 3], rm), rm)
    assert len(picked) == 4
    assert all(nice == rm.nice_default for _, nice in picked)


def _drain(picks, rm):
    """Drain a pick_submittable generator, booking each pick as the
    executor would (so subsequent fits_default checks see it)."""
    out = []
    for tid, nice in picks:
        rm.book(tid, nice)
        out.append((tid, nice))
    return out


def test_timeframe_policy_should_break_legacy():
    """Prototype behavior: the first non-fitting task breaks the default
    pass entirely; following tasks only get a shot in the backfill pass
    (which itself may be blocked once an earlier task consumed its budget)."""
    rm = ResourceManager(cpu_limit=4, mem_limit=16000, n_backfill_max=4)
    rm.add_task("small1", None, cpu=2, cpu_relative=1, mem=100)
    rm.add_task("big",    None, cpu=3, cpu_relative=1, mem=100)
    rm.add_task("small2", None, cpu=2, cpu_relative=1, mem=100)
    p = TimeframeFirstPolicy(drop_should_break=False)
    picks = _drain(p.pick_submittable([0, 1, 2], rm), rm)
    nice_for = {tid: n for tid, n in picks}
    # small1 fits default
    assert nice_for[0] == rm.nice_default
    # small2, which WOULD have fit default (2+2=4), did not go default --
    # that's the legacy bug/feature. It's either backfill or not scheduled.
    assert nice_for.get(2) != rm.nice_default


def test_timeframe_policy_drop_unblocks_small2_at_default(tmp_path=None):
    """Contrast: with drop_should_break=True, small2 gets default priority."""
    rm = ResourceManager(cpu_limit=4, mem_limit=16000, n_backfill_max=4)
    rm.add_task("small1", None, cpu=2, cpu_relative=1, mem=100)
    rm.add_task("big",    None, cpu=3, cpu_relative=1, mem=100)
    rm.add_task("small2", None, cpu=2, cpu_relative=1, mem=100)
    p = TimeframeFirstPolicy(drop_should_break=True)
    picks = _drain(p.pick_submittable([0, 1, 2], rm), rm)
    nice_for = {tid: n for tid, n in picks}
    # small1 and small2 both at default -- the poster's headline result
    assert nice_for[0] == rm.nice_default
    assert nice_for[2] == rm.nice_default


def test_timeframe_policy_drop_should_break():
    """With drop_should_break=True, light tasks can slip past heavy ones
    in the default pass."""
    rm = ResourceManager(cpu_limit=4, mem_limit=16000, n_backfill_max=4)
    rm.add_task("small1", None, cpu=2, cpu_relative=1, mem=100)
    rm.add_task("big",    None, cpu=3, cpu_relative=1, mem=100)
    rm.add_task("small2", None, cpu=2, cpu_relative=1, mem=100)
    s = _make_state(3)
    p = TimeframeFirstPolicy(drop_should_break=True)
    picks = _drain(p.pick_submittable([0, 1, 2], rm), rm)
    nice_for = {tid: n for tid, n in picks}
    # small1 fits default; big doesn't (2+3=5>4); small2 fits default (2+2=4)
    assert nice_for.get(0) == rm.nice_default
    assert nice_for.get(2) == rm.nice_default


def test_critical_path_policy_order():
    # node 2 has the highest critical path -> should come first
    s = _make_state(3, cp=[5.0, 3.0, 10.0])
    p = CriticalPathPolicy()
    assert p.order([0, 1, 2], s) == [2, 0, 1]


def test_best_fit_policy_fills_budget():
    # cpu_limit=10; tasks: 3,3,4 -> best-fit should pack all three
    rm = ResourceManager(cpu_limit=10, mem_limit=16000, n_backfill_max=1)
    rm.add_task("a", None, cpu=3, cpu_relative=1, mem=100)
    rm.add_task("b", None, cpu=3, cpu_relative=1, mem=100)
    rm.add_task("c", None, cpu=4, cpu_relative=1, mem=100)
    s = _make_state(3, cp=[1.0, 1.0, 1.0], desc=[0, 0, 0])
    p = BestFitBackfillPolicy()
    ordered = p.order([0, 1, 2], s)
    picks = _drain(p.pick_submittable(ordered, rm), rm)
    assert len(picks) == 3
    assert all(n == rm.nice_default for _, n in picks)
    # verify that with overfilled budget, best-fit DOES stop
    rm2 = ResourceManager(cpu_limit=5, mem_limit=16000, n_backfill_max=0)
    rm2.add_task("a", None, cpu=3, cpu_relative=1, mem=100)
    rm2.add_task("b", None, cpu=3, cpu_relative=1, mem=100)
    ordered2 = p.order([0, 1], _make_state(2))
    picks2 = _drain(p.pick_submittable(ordered2, rm2), rm2)
    assert len(picks2) == 1  # only one fits the cpu=5 budget


def test_get_policy_names():
    assert isinstance(get_policy("timeframe"), TimeframeFirstPolicy)
    assert isinstance(get_policy("critical-path"), CriticalPathPolicy)
    assert isinstance(get_policy("best-fit"), BestFitBackfillPolicy)
    with pytest.raises(ValueError):
        get_policy("nonsense")


def test_semaphore_prevents_concurrent_submit():
    rm = ResourceManager(cpu_limit=8, mem_limit=16000, n_backfill_max=1)
    rm.add_task("a", None, 1, 1, 100, semaphore_string="S")
    rm.add_task("b", None, 1, 1, 100, semaphore_string="S")
    s = _make_state(2)
    # book a directly
    rm.resources[0].nice_value = rm.nice_default
    rm.book(0, rm.nice_default)
    p = TimeframeFirstPolicy()
    picks = list(p.pick_submittable([1], rm))
    assert picks == []


def test_n_backfill_cap():
    rm = ResourceManager(cpu_limit=2, mem_limit=16000, n_backfill_max=1)
    rm.add_task("a", None, 1, 1, 100)
    rm.add_task("b", None, 1, 1, 100)
    rm.add_task("c", None, 1, 1, 100)
    # fill default with a+b
    for i in (0, 1):
        rm.resources[i].nice_value = rm.nice_default
        rm.book(i, rm.nice_default)
    assert rm.cpu_booked == 2
    # c doesn't fit default; backfill allowed? n_backfill_max=1
    p = TimeframeFirstPolicy()
    picks = list(p.pick_submittable([2], rm))
    # one backfill slot, c gets it
    assert len(picks) == 1
    assert picks[0][1] == rm.nice_backfill
    rm.resources[2].nice_value = rm.nice_backfill
    rm.book(2, rm.nice_backfill)
    # next candidate tries to backfill but cap reached
    rm.add_task("d", None, 1, 1, 100)
    picks2 = list(p.pick_submittable([3], rm))
    assert picks2 == []
