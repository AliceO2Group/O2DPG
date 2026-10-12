"""Cleanup utilities invoked after a task completes.

Two concerns:
 1. Early file removal based on a FileIOGraph-derived file dependency map
    (--remove-files-early). Files that no task will read/write again are
    deleted to keep disc pressure low during large productions.

 2. Production-mode log archival: .log / .log_done / .log_time files are
    appended to a tar archive and removed. Mirrors the prototype's
    production_endoftask_hook().

Both are side-effecting; errors are logged but don't abort the run.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tarfile
from typing import Dict, List, Optional, Set

log = logging.getLogger(__name__)

_TF_PATH_RE = re.compile(r"^\./tf(?P<tf>\d+)/")


def _task_template_for_timeframe(task_name: str, source_tf: int) -> str:
    """Turn task_7 from a tf7 observation into task_{tf}.

    Global tasks such as aodmerge, and any explicit cross-timeframe task
    references, are left untouched.
    """
    suffix = f"_{source_tf}"
    if task_name.endswith(suffix):
        return f"{task_name[:-len(suffix)]}_{{tf}}"
    return task_name


def _task_template_from_placeholder(task_name: str) -> str:
    return re.sub(r"_X$", "_{tf}", task_name)


def _filegraph_expand_timeframes(
    data: Dict,
    timeframes: Set[int],
    target_namelist: List[str],
    logger: Optional[logging.Logger] = None,
) -> Dict[str, List[Dict]]:
    """Build canonical per-timeframe file templates and replicate per TF.

    The FileIOGraph may have been recorded with one or many timeframes.  We
    merge all observed timeframe-local entries by normalising ``./tfX/...`` to
    ``./tf{tf}/...`` and task suffixes ``_X`` to ``_{tf}``, then instantiate the
    merged template for the timeframes of the current workflow.
    """
    logger = logger if logger is not None else log
    templates: Dict[str, Dict] = {}
    source_tfs: Set[int] = set()

    template_report = data.get("file_template_report") or []
    if template_report:
        for entry in template_report:
            filename = entry.get("file", "")
            if filename.startswith("./tfX/"):
                file_template = filename.replace("./tfX/", "./tf{tf}/", 1)
            elif "./tf{tf}/" in filename:
                file_template = filename
            else:
                continue

            source_tfs.update(int(tf) for tf in entry.get("source_timeframes", []))
            merged = templates.setdefault(
                file_template,
                {
                    "file": file_template,
                    "written_by": set(),
                    "read_by": set(),
                    "keep": bool(entry.get("keep", False)),
                },
            )
            merged["keep"] = merged["keep"] or bool(entry.get("keep", False))
            for task in entry.get("written_by", []):
                merged["written_by"].add(_task_template_from_placeholder(task))
            for task in entry.get("read_by", []):
                merged["read_by"].add(_task_template_from_placeholder(task))
    else:
        for entry in data.get("file_report", []):
            filename = entry.get("file", "")
            match = _TF_PATH_RE.match(filename)
            if match is None:
                continue

            source_tf = int(match.group("tf"))
            source_tfs.add(source_tf)
            file_template = _TF_PATH_RE.sub("./tf{tf}/", filename, count=1)
            merged = templates.setdefault(
                file_template,
                {
                    "file": file_template,
                    "written_by": set(),
                    "read_by": set(),
                    "keep": bool(entry.get("keep", False)),
                },
            )
            merged["keep"] = merged["keep"] or bool(entry.get("keep", False))
            for task in entry.get("written_by", []):
                merged["written_by"].add(_task_template_for_timeframe(task, source_tf))
            for task in entry.get("read_by", []):
                merged["read_by"].add(_task_template_for_timeframe(task, source_tf))

    if not templates:
        logger.warning("FileIOGraph contains no ./tfN/ file entries; early removal disabled")
        return {}

    logger.info(
        "FileIOGraph timeframe template built from observed timeframe(s) %s: %d file pattern(s)",
        sorted(source_tfs),
        len(templates),
    )

    result: Dict[str, List[Dict]] = {}
    for i in timeframes:
        if i == -1:
            continue
        new_entries: List[Dict] = []
        for template in templates.values():
            written_by = sorted(t.format(tf=i) for t in template["written_by"])
            read_by = sorted(t.format(tf=i) for t in template["read_by"])
            expanded = {
                "file": template["file"].format(tf=i),
                "written_by": written_by,
                "read_by": read_by,
            }
            if template["keep"] or any(w in target_namelist for w in written_by):
                expanded["keep"] = True
            new_entries.append(expanded)
        result[f"timeframe-{i}"] = new_entries
    return result


class EarlyFileRemover:
    """Owns the timeframe-expanded file dependency dict and performs
    per-task-completion file deletion."""

    def __init__(
        self,
        filegraph_path: str,
        timeframes: Set[int],
        target_namelist: List[str],
        logger: Optional[logging.Logger] = None,
    ):
        self.log = logger if logger is not None else log
        with open(filegraph_path) as f:
            data = json.load(f)
        self.file_dict = _filegraph_expand_timeframes(
            data, timeframes, target_namelist, logger=self.log,
        )
        self.timeframes = timeframes
        # Pre-build a reverse index: task_name -> list[file_entry dict] (all TFs)
        # so completions don't re-scan the whole file map.
        self._by_task: Dict[str, List[Dict]] = {}
        for entries in self.file_dict.values():
            for e in entries:
                for t in e.get("written_by", []):
                    self._by_task.setdefault(t, []).append(e)
                for t in e.get("read_by", []):
                    self._by_task.setdefault(t, []).append(e)

    def on_task_done(self, taskname: str) -> None:
        entries = self._by_task.get(taskname, [])
        for entry in entries:
            if taskname in entry.get("read_by", []):
                entry["read_by"].remove(taskname)
            if taskname in entry.get("written_by", []):
                entry["written_by"].remove(taskname)
            if (not entry.get("read_by") and not entry.get("written_by")
                    and not entry.get("keep", False)):
                self._remove_if_exists(entry["file"])

    def _remove_if_exists(self, path: str) -> bool:
        if os.path.exists(path):
            try:
                sz = os.path.getsize(path)
                os.remove(path)
                self.log.info("Removing %s (no longer needed); freed %.2f MB",
                              path, sz / 1024.0 / 1024.0)
                return True
            except OSError as e:
                self.log.warning("Could not remove %s: %s", path, e)
        return False


def archive_task_logs(logfile: str, logger: Optional[logging.Logger] = None) -> None:
    """Append <logfile>, <logfile>_done, <logfile>_time to a tar archive
    and delete the originals. Used in production mode."""
    logger = logger if logger is not None else log
    done = logfile + "_done"
    timef = logfile + "_time"
    try:
        tf = tarfile.open(name="pipeline_log_archive.log.tar", mode="a")
    except Exception as e:
        logger.warning("Could not open log archive: %s", e)
        return
    try:
        for path in (logfile, done, timef):
            if os.path.exists(path):
                try:
                    tf.add(path)
                except Exception as e:
                    logger.warning("tar add %s failed: %s", path, e)
    finally:
        tf.close()

    for path in (logfile, done, timef):
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning("Could not remove %s: %s", path, e)
