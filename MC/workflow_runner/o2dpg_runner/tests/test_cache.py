import json
import os

import pytest

from o2dpg_runner.cache import (
    TaskCache, compute_fingerprint, done_path, fingerprint_path,
    remove_done_flag,
)


def _make_task(cmd="echo hi", needs=None, env=None):
    return {
        "name": "t",
        "cmd": cmd,
        "needs": needs or [],
        "env": env or {},
    }


def _mkdone(tmpdir, logname="t.log"):
    logfile = os.path.join(str(tmpdir), logname)
    open(done_path(logfile), "w").close()
    return logfile


def test_fingerprint_stable():
    t = _make_task("cmd1", needs=["a", "b"])
    f1 = compute_fingerprint(t)
    f2 = compute_fingerprint(t)
    assert f1 == f2


def test_fingerprint_changes_on_cmd():
    f1 = compute_fingerprint(_make_task("cmd1"))
    f2 = compute_fingerprint(_make_task("cmd2"))
    assert f1["cmd_hash"] != f2["cmd_hash"]


def test_fingerprint_needs_order_insensitive():
    f1 = compute_fingerprint(_make_task(needs=["a", "b"]))
    f2 = compute_fingerprint(_make_task(needs=["b", "a"]))
    assert f1["needs"] == f2["needs"]


def test_cache_off_skips_if_done(tmp_path):
    logfile = _mkdone(tmp_path)
    c = TaskCache("off")
    fp = compute_fingerprint(_make_task())
    assert c.is_done(logfile, fp) is True


def test_cache_off_does_not_skip_without_done(tmp_path):
    logfile = os.path.join(str(tmp_path), "t.log")
    c = TaskCache("off")
    fp = compute_fingerprint(_make_task())
    assert c.is_done(logfile, fp) is False


def test_cache_lenient_keeps_when_no_sidecar(tmp_path):
    logfile = _mkdone(tmp_path)
    c = TaskCache("lenient")
    fp = compute_fingerprint(_make_task())
    assert c.is_done(logfile, fp) is True


def test_cache_strict_invalidates_without_sidecar(tmp_path):
    logfile = _mkdone(tmp_path)
    c = TaskCache("strict")
    fp = compute_fingerprint(_make_task())
    assert c.is_done(logfile, fp) is False
    # also cleared the _done file
    assert not os.path.exists(done_path(logfile))


def test_cache_lenient_invalidates_on_cmd_change(tmp_path):
    logfile = _mkdone(tmp_path)
    c = TaskCache("lenient")
    old_fp = compute_fingerprint(_make_task("old_cmd"))
    c.record(logfile, old_fp)
    new_fp = compute_fingerprint(_make_task("new_cmd"))
    assert c.is_done(logfile, new_fp) is False
    assert not os.path.exists(done_path(logfile))


def test_cache_lenient_tolerates_env_change(tmp_path, caplog):
    logfile = _mkdone(tmp_path)
    c = TaskCache("lenient")
    old_fp = compute_fingerprint(_make_task(env={"ALICE_O2_VERSION": "v1"}))
    c.record(logfile, old_fp)
    new_fp = compute_fingerprint(_make_task(env={"ALICE_O2_VERSION": "v2"}))
    assert c.is_done(logfile, new_fp) is True


def test_cache_strict_invalidates_on_env_change(tmp_path):
    logfile = _mkdone(tmp_path)
    c = TaskCache("strict")
    old_fp = compute_fingerprint(_make_task(env={"ALICE_O2_VERSION": "v1"}))
    c.record(logfile, old_fp)
    new_fp = compute_fingerprint(_make_task(env={"ALICE_O2_VERSION": "v2"}))
    assert c.is_done(logfile, new_fp) is False


def test_cache_record_off_does_nothing(tmp_path):
    logfile = _mkdone(tmp_path)
    c = TaskCache("off")
    fp = compute_fingerprint(_make_task())
    c.record(logfile, fp)
    assert not os.path.exists(fingerprint_path(logfile))


def test_remove_done_flag_removes_both(tmp_path):
    logfile = _mkdone(tmp_path)
    fp_path = fingerprint_path(logfile)
    with open(fp_path, "w") as f:
        f.write("{}")
    remove_done_flag(logfile)
    assert not os.path.exists(done_path(logfile))
    assert not os.path.exists(fp_path)
