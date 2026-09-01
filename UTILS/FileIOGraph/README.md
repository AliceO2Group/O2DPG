# FileIOGraph — learning which task produces and which tasks consume each file

An O2DPG Monte Carlo workflow declares task dependencies, but not which
file each task reads or writes. The tools here observe a pilot run and
write that missing relation down, so a production run can

(a) verify the data paths, and
(b) delete an intermediate file the moment its last consumer is finished
    (`o2dpg_workflow_runner.py --remove-files-early`).

## Backends

The observation is pluggable:

```bash
ALIEN_O2DPG_WORKFLOW_RUNNER=new $O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py \
    -f workflow.json --filegraph-backends fanotify
```

`--filegraph-backends` exists only in the runner under
`MC/workflow_runner`, hence the environment variable.

Each named backend writes `filegraph_<backend>_<pid>.json`; fanotify also
writes `pipeline_fileaccess_report_<pid>.json`, the name the runner has
always used. Naming several at once is how they are compared.

| Backend | How it observes | How it attributes | Privilege |
|---|---|---|---|
| `fanotify` | `monitor_fileaccess_v2.exe`, a mount-wide sidecar | walks `/proc/<pid>` up to the runner, after the event | `CAP_SYS_ADMIN` |
| `strace` | each task command wrapped in its own `strace` | by construction, from the trace file it lands in | none |

`O2DPG_PRODUCE_FILEGRAPH=<exe>` still selects fanotify and names the
monitor to run.

### fanotify

The original. It needs `CAP_SYS_ADMIN`, granted per machine with
`setcap cap_sys_admin+ep monitor_fileaccess_v2.exe`, so a pilot run is
only possible where somebody with root has prepared the binary — and file
capabilities do not survive a `nosuid` mount, so the copy distributed
through CVMFS can never carry one.

Unprivileged fanotify does not help: since Linux 5.13 `fanotify_init()`
needs no `CAP_SYS_ADMIN`, but such a group may not use `FAN_MARK_MOUNT`
and does not receive the pid, and the pid is the whole attribution
mechanism.

Two further properties are worth knowing. A mount-wide mark sees
everything, so in a two-timeframe pilot only 4 301 of 563 611 records were
inside the working directory. And because the process chain is resolved
from `/proc` after the event, an access made by a process that has already
exited yields the chain `<pid>;0` and is dropped.

### strace

Wraps each task command, so attribution needs no inference. It sees the
`open` itself rather than the close, and `-y` gives the path the kernel
resolved the descriptor to, so relative paths, `chdir` and directory
descriptors all come out right.

`--seccomp-bpf` is what makes this affordable; the backend probes for it
and uses it when present. Without it every `read()` costs two ptrace
stops: on a read-heavy task, 22.5 s against a 0.95 s baseline, versus
1.00 s with it. The residual is about 59 µs per traced `open`.

## Checking one backend against another

```bash
python3 compare_reports.py --reference filegraph_fanotify_123.json \
                          --candidate filegraph_strace_123.json
```

`EXACT` means edge for edge, `SAFE` that the candidate is a superset,
`UNSAFE` that it misses an edge the reference has. The asymmetry is the
point — an extra reader only keeps a file on disc longer, a missing one
deletes a file a later task still needs.

`tests/equivalence_test.py` runs a synthetic workflow whose graph is known
by construction under several backends at once and grades all of them, in
seconds and without any ALICE software:

```bash
python3 tests/equivalence_test.py --backends strace --reference fanotify \
        --ntf 8 --cpu-limit 8 --sleep 0.05
```

Drop `--reference fanotify` where no privileged monitor exists; the
synthetic workflow still carries its own analytic truth.

Offline tests: `python3 -m unittest discover -s tests -t tests`.

## Building

```bash
g++ monitor_fileaccess_v2.cpp -O2 -o monitor_fileaccess_v2.exe
sudo setcap cap_sys_admin+ep monitor_fileaccess_v2.exe   # fanotify only
```
