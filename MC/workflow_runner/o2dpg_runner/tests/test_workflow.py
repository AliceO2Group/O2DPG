import json
import os

import pytest

from o2dpg_runner.workflow import (
    load_json, extract_global_init, filter_workflow, build_workflow,
    update_resource_estimates,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "tiny_workflow.json")


def _load():
    return load_json(FIXTURE)


def test_extract_global_init():
    spec = _load()
    env, cmd = extract_global_init(spec)
    assert env == {"FOO": "bar"}
    assert cmd is None  # cmd was "NO-COMMAND"
    # __global_init_task__ removed from stages
    assert spec["stages"][0]["name"] != "__global_init_task__"
    assert spec["stages"][0]["name"] == "bkg"


def test_filter_workflow_all():
    spec = _load()
    extract_global_init(spec)
    filtered, targets = filter_workflow(spec, ["*"], [])
    assert targets == []  # "*" means no target list
    assert len(filtered["stages"]) == len(spec["stages"])


def test_filter_workflow_by_target():
    spec = _load()
    extract_global_init(spec)
    filtered, targets = filter_workflow(spec, ["digi_1"], [])
    names = [t["name"] for t in filtered["stages"]]
    # digi_1 + its needs bkg, sgnsim_1
    assert "digi_1" in names
    assert "sgnsim_1" in names
    assert "bkg" in names
    assert "reco_1" not in names
    assert "aod" not in names
    assert targets == ["digi_1"]


def test_filter_workflow_by_label():
    spec = _load()
    extract_global_init(spec)
    filtered, targets = filter_workflow(spec, ["*"], ["QC"])
    # "*" with label filter narrows, and pulls in all deps
    names = [t["name"] for t in filtered["stages"]]
    assert "qc_1" in names
    assert "qc_2" in names
    # deps pulled in
    for need in ("reco_1", "reco_2", "digi_1", "digi_2", "sgnsim_1", "sgnsim_2", "bkg"):
        assert need in names


def test_filter_workflow_regex_target():
    spec = _load()
    extract_global_init(spec)
    filtered, targets = filter_workflow(spec, ["^qc_.*"], [])
    names = [t["name"] for t in filtered["stages"]]
    assert set(targets) == {"qc_1", "qc_2"}
    assert "aod" not in names


def test_filter_does_not_alias_input():
    """Regression: the prototype did `transformedworkflowspec = workflowspec`
    and then mutated .stages, aliasing the caller's dict. Ensure we don't."""
    spec = _load()
    extract_global_init(spec)
    original_len = len(spec["stages"])
    filtered, _ = filter_workflow(spec, ["qc_1"], [])
    # filtered should be smaller, spec unchanged
    assert len(filtered["stages"]) < original_len
    assert len(spec["stages"]) == original_len


def test_build_workflow_end_to_end():
    raw = _load()
    wf = build_workflow(raw, ["*"], [])
    # 10 tasks after removing global init
    assert wf.n_tasks() == 10
    # indegrees: bkg has 0; aod has 2 (reco_1, reco_2)
    bkg_tid = wf.tid("bkg")
    aod_tid = wf.tid("aod")
    assert wf.indegree[bkg_tid] == 0
    assert wf.indegree[aod_tid] == 2
    # timeframes: -1, 1, 2
    assert wf.timeframes == {-1, 1, 2}


def test_update_resource_estimates(tmp_path):
    raw = _load()
    wf = build_workflow(raw, ["*"], [])
    # synthesize a learned-estimates JSON keyed by "global" task name
    est = {
        "sgnsim": {"pss": {"max": 3000}, "cpu": {"mean": 3.5}},
        "digi":   {"pss": {"max": 1200}, "cpu": {"mean": 1.8}},
    }
    p = tmp_path / "res.json"
    p.write_text(json.dumps(est))
    update_resource_estimates(wf, str(p))

    for name in ("sgnsim_1", "sgnsim_2"):
        t = wf.stages[wf.tid(name)]
        assert t["resources"]["mem"] == 3000
        assert t["resources"]["cpu"] == 3.5
    for name in ("digi_1", "digi_2"):
        t = wf.stages[wf.tid(name)]
        assert t["resources"]["mem"] == 1200
        assert t["resources"]["cpu"] == 1.8
