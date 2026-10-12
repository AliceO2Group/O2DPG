"""Task-completion cache.

Preserves the O2-taskwrapper-compatible `<task>.log_done` marker file as
the primary source of truth (so that downstream tools and the wrapper
itself continue to work unchanged), and optionally writes a sidecar
`<task>.log_done.json` containing a fingerprint of the inputs that
determine the task's output.

Cache policies:
  off     - current behavior: a _done file means "skip"
  lenient - read _done.json when present; invalidate only if the
            command string changed. Warn on env / software changes.
  strict  - invalidate on any fingerprint change.

Fingerprint components:
  cmd_hash            hash of the task command string
  env_hash            hash of the allow-listed subset of the task env
  software            the alienv package string (or '' if default)
  needs               list of upstream task names

The sidecar is written best-effort after the _done file exists (so
torn writes don't leave stale fingerprints around).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# Env vars that actually affect task semantics. Keep this conservative:
# everything else is considered noise (TMPDIR, PWD, terminal colors, etc.).
# Users can override via the workflow by not relying on env and by expressing
# variation through the cmd itself.
SEMANTIC_ENV_KEYS = (
    "ALICE_O2_VERSION", "O2_ROOT", "O2DPG_ROOT", "O2PHYSICS_ROOT",
    "NEVENTS", "NWORKERS", "SEED", "INTERACTIONRATE",
    "SIMENGINE", "NSIGEVENTS", "NTIMEFRAMES", "GENERATOR",
    "ALIDIST_TAG",
)


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", "replace"))
        h.update(b"\x1f")  # separator
    return h.hexdigest()[:16]


def compute_fingerprint(
    task: Dict,
    alienv_package: str = "",
    allow_env_keys: Tuple[str, ...] = SEMANTIC_ENV_KEYS,
) -> Dict[str, str]:
    """Compute a fingerprint for a task spec.

    Does NOT depend on upstream task fingerprints -- upstream changes
    propagate via the _done/_done.json of upstream tasks (if upstream
    was re-run, its _done file was removed and the current task will
    see a missing dependency marker and re-run).
    """
    cmd = task.get("cmd", "") or ""
    env_subset = {}
    task_env = task.get("env") or {}
    for k in allow_env_keys:
        if k in task_env:
            env_subset[k] = str(task_env[k])
    env_str = json.dumps(env_subset, sort_keys=True)
    needs = sorted(task.get("needs", []) or [])
    needs_str = json.dumps(needs)

    return {
        "cmd_hash": _hash(cmd),
        "env_hash": _hash(env_str),
        "software": alienv_package or "",
        "needs": needs,
        "cmd_preview": cmd[:120],  # for human debugging
    }


def done_path(logfile: str) -> str:
    return logfile + "_done"


def fingerprint_path(logfile: str) -> str:
    return logfile + "_done.json"


class TaskCache:
    """Policy-aware interface for checking/recording task completion."""

    def __init__(self, policy: str = "off"):
        if policy not in ("off", "lenient", "strict"):
            raise ValueError(f"unknown cache policy: {policy}")
        self.policy = policy

    def is_done(self, logfile: str, current_fp: Dict[str, str]) -> bool:
        """Return True iff the task can be skipped.

        logfile: path like /cwd/taskname.log  (we append _done / _done.json)
        current_fp: fingerprint dict from compute_fingerprint(task)
        """
        dp = done_path(logfile)
        if not (os.path.exists(dp) and os.path.isfile(dp)):
            return False

        if self.policy == "off":
            return True

        fp_path = fingerprint_path(logfile)
        if not os.path.exists(fp_path):
            # Old run; nothing to compare against.
            if self.policy == "strict":
                log.info("%s: strict cache policy but no fingerprint -> invalidating", logfile)
                self._invalidate(logfile)
                return False
            log.debug("%s: no fingerprint sidecar; keeping _done (lenient)", logfile)
            return True

        try:
            with open(fp_path) as f:
                prev = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("%s: fingerprint unreadable (%s); invalidating", fp_path, e)
            self._invalidate(logfile)
            return False

        cmd_changed = prev.get("cmd_hash") != current_fp["cmd_hash"]
        env_changed = prev.get("env_hash") != current_fp["env_hash"]
        sw_changed = prev.get("software") != current_fp["software"]
        needs_changed = prev.get("needs") != current_fp["needs"]

        if self.policy == "lenient":
            if cmd_changed or needs_changed:
                log.info("%s: cmd/needs changed -> invalidating (lenient)", logfile)
                self._invalidate(logfile)
                return False
            if env_changed:
                log.warning("%s: env fingerprint changed but keeping cache (lenient)", logfile)
            if sw_changed:
                log.warning("%s: software fingerprint changed but keeping cache (lenient)",
                            logfile)
            return True

        # strict
        if cmd_changed or env_changed or sw_changed or needs_changed:
            reasons = []
            if cmd_changed: reasons.append("cmd")
            if env_changed: reasons.append("env")
            if sw_changed: reasons.append("software")
            if needs_changed: reasons.append("needs")
            log.info("%s: changed (%s) -> invalidating (strict)", logfile, ",".join(reasons))
            self._invalidate(logfile)
            return False
        return True

    def record(self, logfile: str, current_fp: Dict[str, str]) -> None:
        """Write the fingerprint sidecar after the task's _done file exists.

        Best effort: errors are logged but not raised.
        """
        if self.policy == "off":
            return
        dp = done_path(logfile)
        if not os.path.exists(dp):
            # _done doesn't exist (e.g. skipped in dry-run); nothing to record.
            return
        try:
            with open(fingerprint_path(logfile), "w") as f:
                json.dump(current_fp, f, indent=2)
        except OSError as e:
            log.warning("Could not write fingerprint for %s: %s", logfile, e)

    def _invalidate(self, logfile: str) -> None:
        for p in (done_path(logfile), fingerprint_path(logfile)):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError as e:
                log.warning("Could not remove %s: %s", p, e)


def remove_done_flag(logfile: str) -> None:
    """Explicit invalidation used by --rerun-from."""
    for p in (done_path(logfile), fingerprint_path(logfile)):
        if os.path.exists(p) and os.path.isfile(p):
            os.remove(p)
