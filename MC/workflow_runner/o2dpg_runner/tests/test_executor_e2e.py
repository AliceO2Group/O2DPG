"""End-to-end executor tests using the tiny fixture workflow.

The commands are plain `echo` calls, so no CVMFS / O2 software needed.
We invoke the CLI's main() the same way the shell entry point would.
"""

import json
import logging
import os
import shutil
import sys
from types import SimpleNamespace

import pytest

from o2dpg_runner.config import RunnerConfig
from o2dpg_runner.workflow import build_workflow, load_json
from o2dpg_runner.executor import WorkflowExecutor

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "tiny_workflow.json")


def _make_logger(name, path):
    lg = logging.getLogger(name)
    lg.handlers.clear()
    lg.addHandler(logging.FileHandler(path))
    lg.setLevel(logging.INFO)
    lg.propagate = False
    return lg


def _prep_workflow_in_tmp(tmp_path):
    """Copy the fixture into tmp_path and wrap every cmd with a _done marker,
    since the stock O2 taskwrapper isn't available in tests."""
    raw = load_json(FIXTURE)
    # Patch each command so that it writes the expected _done file after success.
    for t in raw["stages"]:
        if t["name"] == "__global_init_task__":
            continue
        cwd = t.get("cwd", "./")
        name = t["name"]
        # emulate the taskwrapper: run the cmd, then write <cwd>/<name>.log_done
        t["cmd"] = f'({t["cmd"]}) > {name}.log 2>&1 && touch {name}.log_done'
    fixture_path = tmp_path / "wf.json"
    fixture_path.write_text(json.dumps(raw))
    return str(fixture_path)


def _make_executor(tmp_path, cfg_overrides=None):
    os.chdir(str(tmp_path))
    wf_path = _prep_workflow_in_tmp(tmp_path)
    cfg = RunnerConfig(
        workflowfile=wf_path,
        cpu_limit=8,
        mem_limit=16000,
        maxjobs=100,
        monitor_interval_cpu=0.2,
        monitor_interval_mem=0.5,
    )
    if cfg_overrides:
        for k, v in cfg_overrides.items():
            setattr(cfg, k, v)
    raw = load_json(wf_path)
    wf = build_workflow(raw, cfg.target_tasks, cfg.target_labels)
    action_logger = _make_logger("a", str(tmp_path / "act.log"))
    metric_logger = _make_logger("m", str(tmp_path / "met.log"))
    return WorkflowExecutor(cfg, wf, action_logger, metric_logger)


def _run(tmp_path, cfg_overrides=None):
    exe = _make_executor(tmp_path, cfg_overrides)
    return exe.execute(), exe.wf, tmp_path


class _FakeProc:
    pid = 4242

    def poll(self):
        return None

    def kill(self):
        pass


class _FakeMonitor:
    """One task, one snapshot, and a tick the test advances by hand."""

    def __init__(self):
        self.tick = 1
        self.global_cpu_pct = None
        self.global_mem_mb = None
        self.snap = SimpleNamespace(
            tid=0, name="t", t_delta_ms=1000, cpu_pct=100.0, uss_mb=1.0,
            pss_mb=2.0, swap_mb=0.0, nice=0, labels=[], disc_mb=-1,
            cgroup_cpu_pct=None, cgroup_mem_mb=None)

    def latest(self):
        return {0: self.snap}


def test_a_monitor_tick_is_recorded_once_however_often_it_is_polled(tmp_path):
    """The wait loop polls faster than the monitor fires. Recording the same
    snapshot twice defeats the 'too few samples' guard in sample_resources()."""
    exe = _make_executor(tmp_path)
    exe.monitor = _FakeMonitor()
    exe.process_list = [(0, _FakeProc())]

    for _ in range(5):
        exe.wait_for_any([], [])
    assert len(exe.rm.resources[0].time_collect) == 1

    exe.monitor.tick = 2
    exe.monitor.snap.t_delta_ms = 2000
    exe.wait_for_any([], [])
    assert exe.rm.resources[0].time_collect == [1000, 2000]


def test_executor_runs_all_tasks(tmp_path):
    rc, wf, path = _run(tmp_path)
    assert rc is False  # no errors
    # every task should have produced a _done file
    for t in wf.stages:
        done_file = path / (t.get("cwd", ".") or ".") / f"{t['name']}.log_done"
        assert done_file.exists(), f"missing _done for {t['name']}"


def test_executor_respects_target_filter(tmp_path):
    rc, wf, path = _run(tmp_path, {"target_tasks": ["qc_1"]})
    assert rc is False
    # only bkg, sgnsim_1, digi_1, reco_1, qc_1 should have run
    expected = {"bkg", "sgnsim_1", "digi_1", "reco_1", "qc_1"}
    got = {t["name"] for t in wf.stages}
    assert got == expected


def test_executor_skips_done_tasks_on_rerun(tmp_path):
    # first run
    rc1, _, _ = _run(tmp_path)
    assert rc1 is False

    # second run: stages unchanged -> every task should be skipped via _done.
    os.chdir(str(tmp_path))
    wf_path = str(tmp_path / "wf.json")
    cfg = RunnerConfig(
        workflowfile=wf_path,
        cpu_limit=8, mem_limit=16000,
    )
    raw = load_json(wf_path)
    wf = build_workflow(raw, cfg.target_tasks, cfg.target_labels)
    act = _make_logger("a2", str(tmp_path / "act2.log"))
    met = _make_logger("m2", str(tmp_path / "met2.log"))
    exe = WorkflowExecutor(cfg, wf, act, met)
    # All tasks should appear skippable up front.
    for tid in range(wf.n_tasks()):
        assert exe.ok_to_skip(tid), f"{wf.id_to_name[tid]} should be skippable"


def test_executor_critical_path_policy(tmp_path):
    rc, wf, path = _run(tmp_path, {"scheduler_policy": "critical-path"})
    assert rc is False
    assert all((path / (t.get("cwd", ".") or ".") / f"{t['name']}.log_done").exists()
               for t in wf.stages)


def test_executor_best_fit_policy(tmp_path):
    rc, wf, path = _run(tmp_path, {"scheduler_policy": "best-fit"})
    assert rc is False
    assert all((path / (t.get("cwd", ".") or ".") / f"{t['name']}.log_done").exists()
               for t in wf.stages)


def test_executor_drop_should_break(tmp_path):
    rc, wf, path = _run(tmp_path, {"drop_should_break": True})
    assert rc is False


def test_executor_produce_script(tmp_path):
    os.chdir(str(tmp_path))
    wf_path = _prep_workflow_in_tmp(tmp_path)
    cfg = RunnerConfig(
        workflowfile=wf_path,
        cpu_limit=8, mem_limit=16000,
        produce_script=str(tmp_path / "run.sh"),
    )
    raw = load_json(wf_path)
    wf = build_workflow(raw, cfg.target_tasks, cfg.target_labels)
    act = _make_logger("a3", str(tmp_path / "act3.log"))
    met = _make_logger("m3", str(tmp_path / "met3.log"))
    exe = WorkflowExecutor(cfg, wf, act, met)
    exe.execute()
    text = open(str(tmp_path / "run.sh")).read()
    assert "bkg" in text
    assert "aod" in text
    assert "#!/usr/bin/env bash" in text


def test_executor_dry_run(tmp_path):
    rc, wf, path = _run(tmp_path, {"dry_run": True})
    assert rc is False
    # dry run should NOT create _done files
    any_done = any((path / (t.get("cwd", ".") or ".") / f"{t['name']}.log_done").exists()
                   for t in wf.stages)
    assert not any_done


def test_executor_cache_lenient_end_to_end(tmp_path):
    # first run with lenient cache
    rc1, _, _ = _run(tmp_path, {"cache_policy": "lenient"})
    assert rc1 is False
    # fingerprint sidecars should exist
    for t in ["bkg", "qc_1", "aod"]:
        # find cwd
        cwd = next(s["cwd"] for s in load_json(str(tmp_path / "wf.json"))["stages"]
                   if s["name"] == t)
        assert os.path.exists(str(tmp_path / cwd / f"{t}.log_done"))
        assert os.path.exists(str(tmp_path / cwd / f"{t}.log_done.json"))
