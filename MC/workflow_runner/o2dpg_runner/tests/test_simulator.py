import os
import sys

import pytest

from o2dpg_runner.workflow import build_workflow

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import o2dpg_schedule_simulator as sim


def _wf(stages):
    return build_workflow({"stages": stages}, ["*"], [])


def _task(name, cpu, mem=100.0, walltime=1.0, needs=None, timeframe=1):
    return {
        "name": name,
        "needs": list(needs or []),
        "cmd": "true",
        "cwd": ".",
        "timeframe": timeframe,
        "labels": [],
        "resources": {"cpu": cpu, "mem": mem, "walltime": walltime},
    }


def test_simulator_uses_amdahl_override_in_critical_path_state():
    wf = _wf([
        _task("a", cpu=1, walltime=1.0),
        _task("b", cpu=1, walltime=5.0),
    ])
    model = sim.AmdahlModel(
        t_serial=20.0,
        t_parallel_tot=0.0,
        n_ref=1,
        cpu_mean_ref=1.0,
        min_workers=1,
        max_workers=1,
    )
    result = sim.simulate(
        wf,
        "critical-path",
        cpu_limit=8.0,
        mem_limit=1000.0,
        amdahl_models={"a": model},
        worker_assignment={"a": 1},
        maxjobs=1,
    )
    assert result.tasks[0].name == "a"


def test_simulator_keeps_tid_mapping_when_task_exceeds_limits():
    wf = _wf([
        _task("too_big", cpu=20, walltime=3.0),
        _task("ok", cpu=1, walltime=2.0),
    ])
    result = sim.simulate(
        wf,
        "timeframe",
        cpu_limit=4.0,
        mem_limit=1000.0,
        maxjobs=1,
    )
    assert [t.name for t in result.tasks] == ["ok"]
    assert result.deadlocked_tids == [0]


def test_simulator_backfill_slowdown_marks_and_slows_backfill_tasks():
    wf = _wf([
        _task("small1", cpu=2, walltime=3.0),
        _task("big", cpu=3, walltime=8.0),
        _task("small2", cpu=2, walltime=3.0),
    ])
    result = sim.simulate(
        wf,
        "timeframe",
        cpu_limit=4.0,
        mem_limit=1000.0,
        backfill_model="slowdown",
        n_backfill=1,
        backfill_slowdown_factor=1.25,
    )
    by_name = {t.name: t for t in result.tasks}
    assert "big" in by_name
    assert by_name["big"].start == pytest.approx(0.0)
    compute_wt = 8.0 * 1.25
    assert by_name["big"].walltime == pytest.approx(compute_wt + 0.1)
    # cpu is the average over the whole slot, so the idle overhead dilutes it;
    # cpu * walltime is the CPU-seconds actually spent
    assert by_name["big"].cpu == pytest.approx(
        3.0 / 1.25 * compute_wt / (compute_wt + 0.1))
    assert by_name["big"].cpu_booked == pytest.approx(3.0)
    assert result.cpu_utilization(4.0) <= 1.0


def test_simulator_holefill_uses_only_foreground_hole():
    wf = _wf([
        _task("fg", cpu=2, walltime=4.0),
        _task("bf", cpu=3, walltime=2.0),
    ])
    result = sim.simulate(
        wf,
        "timeframe",
        cpu_limit=4.0,
        mem_limit=1000.0,
        backfill_model="holefill",
        n_backfill=1,
        task_overhead=0.0,
    )
    by_name = {t.name: t for t in result.tasks}
    assert by_name["fg"].walltime == pytest.approx(4.0)
    assert by_name["bf"].walltime == pytest.approx(3.0)
    assert by_name["bf"].cpu == pytest.approx(2.0)
    assert by_name["bf"].cpu_booked == pytest.approx(3.0)
    assert result.cpu_utilization(4.0) == pytest.approx(0.875)


def test_amdahl_model_rejects_negative_components():
    with pytest.raises(ValueError):
        sim.AmdahlModel.from_dict(
            {
                "t_serial": -1.0,
                "t_parallel_tot": 5.0,
                "n_ref": 4,
                "cpu_mean_ref": 4.0,
            }
        )
