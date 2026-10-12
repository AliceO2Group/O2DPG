import pytest

from o2dpg_runner.resources import (
    ResourceManager, ResourceLimitExceeded, Semaphore, TaskResources,
    ResourceBoundaries,
)


def _make_rm(cpu=8.0, mem=16000.0, **kw):
    return ResourceManager(cpu_limit=cpu, mem_limit=mem, **kw)


def test_add_task_within_limits():
    rm = _make_rm()
    rm.add_task("a", None, cpu=2, cpu_relative=1, mem=1000)
    assert len(rm.resources) == 1
    assert rm.resources[0].name == "a"


def test_add_task_exceeds_limits_raises():
    rm = _make_rm(cpu=4)
    with pytest.raises(ResourceLimitExceeded):
        rm.add_task("big", None, cpu=8, cpu_relative=1, mem=100)


def test_is_within_limits_checks_mem_correctly():
    """Regression: prototype compared CPU to mem_limit by mistake."""
    rm = _make_rm(cpu=100, mem=1000, optimistic_resources=True)
    # CPU under limit, MEM over limit -> should be caught
    res = rm.add_task("t", None, cpu=1, cpu_relative=1, mem=5000)
    # After add_task's limit_resources, mem is capped
    assert res.mem_assigned == 1000


def test_book_and_unbook_default():
    rm = _make_rm()
    rm.add_task("a", None, 2, 1, 1000)
    res = rm.resources[0]
    res.nice_value = rm.nice_default
    rm.book(0, rm.nice_default)
    assert rm.n_procs == 1
    assert rm.cpu_booked == 2
    assert rm.mem_booked == 1000
    rm.unbook(0)
    assert rm.n_procs == 0
    assert rm.cpu_booked == 0
    assert rm.mem_booked == 0


def test_book_and_unbook_backfill():
    rm = _make_rm()
    rm.add_task("a", None, 2, 1, 1000)
    res = rm.resources[0]
    res.nice_value = rm.nice_backfill
    rm.book(0, rm.nice_backfill)
    assert rm.n_procs_backfill == 1
    assert rm.n_procs == 0
    rm.unbook(0)
    assert rm.n_procs_backfill == 0


def test_fits_default():
    rm = _make_rm(cpu=4, mem=4000)
    rm.add_task("a", None, 2, 1, 1000)
    rm.add_task("b", None, 3, 1, 1000)
    rm.resources[0].nice_value = rm.nice_default
    rm.book(0, rm.nice_default)
    # now 2 cpu / 1000 mem booked; b (3 cpu) doesn't fit
    assert not rm.fits_default(rm.resources[1])


def test_fits_backfill_rejects_too_big():
    rm = _make_rm(cpu=4, mem=4000)
    rm.add_task("big", None, 4, 1, 1000)  # equals cpu_limit -> 100% > 90%
    rm.resources[0].limit_resources()  # ensure assigned=cpu_limit
    rm.resources[0].cpu_assigned = 4   # at 90% threshold
    assert not rm.fits_backfill(rm.resources[0])


def test_semaphore_blocks_duplicate():
    rm = _make_rm()
    rm.add_task("a", None, 1, 1, 100, semaphore_string="S")
    rm.add_task("b", None, 1, 1, 100, semaphore_string="S")
    assert rm.resources[0].semaphore is rm.resources[1].semaphore
    rm.resources[0].nice_value = rm.nice_default
    rm.book(0, rm.nice_default)
    assert not rm.can_be_submitted_at_all(rm.resources[1])
    rm.unbook(0)
    assert rm.can_be_submitted_at_all(rm.resources[1])


def test_related_tasks_share_bucket():
    rm = _make_rm()
    rm.add_task("sgnsim_1", "sgnsim", 2, 1, 1000)
    rm.add_task("sgnsim_2", "sgnsim", 2, 1, 1000)
    assert rm.resources[0].related_tasks is rm.resources[1].related_tasks


def test_dynamic_sampling_propagates():
    rm = ResourceManager(cpu_limit=8, mem_limit=16000, dynamic_resources=True)
    rm.add_task("t_1", "t", 2, 1, 1000)
    rm.add_task("t_2", "t", 2, 1, 1000)
    # Feed monitor samples for t_1
    for i in range(5):
        rm.add_monitored(0, i * 1.0, cpu_fraction=1.5, mem_mb=800.0)
    rm.resources[0].nice_value = rm.nice_default
    rm.book(0, rm.nice_default)
    rm.unbook(0)  # this triggers sampling + propagation
    # t_2 should now have an adjusted assignment based on observed sample
    assert rm.resources[1].cpu_assigned > 0
    # The sampled CPU was ~1.5; t_2's cpu_assigned should reflect that ballpark
    assert rm.resources[1].mem_assigned == pytest.approx(800.0, abs=1)


def test_a_zero_cpu_sample_leaves_siblings_alone():
    """A task seen only through its psutil baseline reads 0.0 cores. Passing
    that on would make every sibling look free and admit them all at once."""
    manager = ResourceManager(cpu_limit=8, mem_limit=16000, dynamic_resources=True)
    manager.add_task("t_1", "t", 2, 1, 1000)
    manager.add_task("t_2", "t", 2, 1, 1000)
    for i in range(5):
        manager.add_monitored(0, i * 1.0, cpu_fraction=0.0, mem_mb=800.0)
    manager.resources[0].nice_value = manager.nice_default
    manager.book(0, manager.nice_default)
    manager.unbook(0)
    assert manager.resources[1].cpu_assigned == pytest.approx(2.0)


def test_at_proc_cap():
    rm = _make_rm()
    rm.procs_parallel_max = 2
    assert not rm.at_proc_cap()
    for i in range(2):
        rm.add_task(f"t{i}", None, 1, 1, 100)
        rm.resources[i].nice_value = rm.nice_default
        rm.book(i, rm.nice_default)
    assert rm.at_proc_cap()
