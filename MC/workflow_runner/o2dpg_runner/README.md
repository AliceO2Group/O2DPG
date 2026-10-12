# o2dpg_runner — modular rewrite of the O2DPG workflow runner

This package is a modular rewrite of the single-file runner
`MC/bin/o2_dpg_workflow_runner.py` (~2000 lines, module-global state).
Both are installed; which one runs is chosen at run time, so the two can be
compared on the same job. Every flag the original parser accepts, this one
accepts, with the same semantics.

## Where it lives, and how it is selected

The package and its entry point live in `MC/workflow_runner/`:

```
MC/workflow_runner/
    o2dpg_workflow_runner.py            # entry point
    o2dpg_schedule_simulator.py
    o2dpg_runner/
        cli.py                          # argparse -> RunnerConfig -> Executor
        config.py                       # RunnerConfig dataclass
        workflow.py                     # load / filter / build DAG
        graph.py                        # Kahn topo sort, memoized descendants
        resources.py                    # TaskResources, ResourceManager
        monitoring.py                   # threaded psutil monitor
        scheduler/                      # timeframe (default), critical_path, best_fit
        executor.py                     # main control loop
        cleanup.py                      # early file removal, log archival
        alienv.py                       # alienv env resolution
        cache.py                        # _done + _done.json fingerprint cache
        tests/
```

Nothing calls it directly. `MC/bin/o2_dpg_workflow_runner.py` is a
dispatcher that execs either this runner or the original one, and every
existing call site goes through it unchanged:

```bash
ALIEN_O2DPG_WORKFLOW_RUNNER=new  $O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
```

`legacy` is the default and runs `MC/bin/o2dpg_workflow_runner_legacy.py`.
An unknown value is an error, not a silent fallback.

No new required dependencies. `psutil` and optionally `graphviz` as before.

## What changed behaviorally

The default invocation should reproduce prototype behavior bit-for-bit
(same scheduling decisions, same output files, same log formats).
Everything new is opt-in.

### New CLI flags (all default to current behavior)

| Flag                          | Default       | Effect                                                                         |
| ----------------------------- | ------------- | ------------------------------------------------------------------------------ |
| `--scheduler-policy`          | `timeframe`   | Choose: `timeframe` (legacy), `critical-path`, or `best-fit`.                  |
| `--drop-should-break`         | off           | In `timeframe`, let light tasks slip past a non-fitting heavy task.            |
| `--monitor-interval-cpu`      | `1.0` (s)     | CPU polling cadence for the background monitor thread.                         |
| `--monitor-interval-mem`      | `5.0` (s)     | PSS polling cadence (much cheaper to read less often).                         |
| `--monitor-backend`           | `psutil`      | Reserved for a future cgroup-v2 backend.                                       |
| `--cache-policy`              | `off`         | Task-completion cache: `off` (legacy), `lenient`, `strict`. See below.         |

### Removed flags

- `--webhook` — the debug Mattermost channel integration is gone. The
  flag is still accepted (for compatibility) but ignored.
- `--checkpoint-on-failure` — the tarball + `alien.py cp` failure
  checkpoint was only used for Grid debugging. Same: accepted, ignored.
- `--cgroup` — superseded by `--systemd-run`. Same: accepted, ignored.
  All three log a warning when passed, and none of them aborts, so a JDL
  passing one through `ALIEN_O2DPG_ADDITIONAL_WORKFLOW_RUNNER_ARGS` still
  runs.

### Monitoring

The old runner polled psutil synchronously in the main scheduling loop,
costing 10–20 % of one core on realistic workflows. The new monitor runs
in a background thread with two independent cadences — CPU (cheap,
~1 Hz) and PSS (expensive, ~0.2 Hz). The scheduler reads the latest
snapshot non-blockingly. Result: the runner's self-CPU drops to ~1-2 %.

The scheduler's dynamic-resource sampling (`--dynamic-resources`) still
triggers in `ResourceManager.unbook()`, preserving ordering with
respect to task completions.

### Scheduler policies

Three policies ship, switchable via `--scheduler-policy`:

- **`timeframe`** (default) — exact prototype behavior. Sort by
  `(timeframe, -num_descendants)`; first non-fitting task in the default
  pass breaks the pass (this is the legacy quirk that blocks light tasks
  behind heavy ones). Set `--drop-should-break` to disable that quirk.
- **`critical-path`** — sort by longest-remaining CPU-weighted path to a
  leaf. Standard HEFT-style heuristic; tends to win when resource
  estimates are accurate (after `--update-resources`).
- **`best-fit`** — iterative best-fit bin-packing over the candidate set
  against the remaining CPU/MEM budget. Maximizes parallelism at the cost
  of slightly less predictable task ordering.

Comparing these three on the same workflow with the same
estimates gives a direct A/B measurement of scheduling strategy impact.

### Cache policy

`_done` files remain the primary skip marker (O2 taskwrapper compatibility
is preserved). With `--cache-policy lenient`, a sidecar `_done.json` is
written containing a fingerprint of (command, env subset, software tag,
needs). On rerun, if the command or `needs` list changed, the `_done`
file is removed and the task re-runs. `strict` additionally invalidates
on env/software changes.

No behavior change unless you pass the flag.

## What to know

Things that only came out of running this, and that cost time to find again.

**A task's first CPU reading is always 0.** `psutil.cpu_percent(interval=None)`
has no baseline on its first call and returns `0.0` by construction. That is
why `sample_resources()` refuses to learn from fewer than three samples, and
why a sampled CPU of `0` is treated as missing information rather than as a
task that needs no CPU. Propagating a zero would make every sibling look free
and admit them all at once.

**A monitor tick is not a poll.** The wait loop polls at 0.1 s ramping to 1 s
while the monitor thread fires at `--monitor-interval-cpu`. Samples must be
taken once per tick; recording per poll grows the sample lists without bound
over a long job and, worse, satisfies the three-sample guard with copies of
one reading.

**A tracer or a monitor has to sit inside the systemd scope.** With
`--systemd-run`, wrapping the outside of `systemd-run` means observing
`systemd-run` and nothing else. The wrapper goes on the inner command.

**`--maxjobs 1` serialises a workflow; `--cpu-limit 1` does not.** The latter
makes every task that declares more than one core unschedulable, and the run
stops with `ResourceLimitExceeded`.

**The prototype and this runner disagree on short tasks, in this runner's
favour.** The prototype samples from its scheduling loop at roughly 5 s, so a
task shorter than ~15 s never reaches three samples and `--dynamic-resources`
learns nothing from it. The monitor thread here runs at 1 s.

## Bug fixes incorporated

Silently fixed relative to the prototype:

1. `TaskResources.is_within_limits()` compared CPU to mem_limit instead
   of MEM to mem_limit; the memory safety net was effectively disabled.
2. `find_all_dependent_tasks()` cached duplicates but returned
   deduped; cache hits returned different values than cache misses.
3. `filter_workflow()` aliased the caller's dict and mutated it in place.
4. `getallrequirements()` recursed without memoization — exponential on
   diamond DAGs; `sys.setrecursionlimit(100000)` was a workaround.
5. `send_webhook()` shell-interpolated task names into `os.system`
   (command injection). Removed along with the webhook feature.
6. `SIGHandler` only caught SIGINT; Grid preemption via SIGTERM was
   ignored. Now both are handled.
7. The emitted `produce_script` output used `cd $OLDPWD` which broke if
   a task `cd`s internally. Now uses subshells: `( cd "$workdir" && ... )`.
8. `candidates` list used `.count()` for membership checks (O(n));
   replaced by set-based lookups.
9. A sampled CPU of `0` was propagated to the un-started sibling tasks,
   which then all looked free and were admitted at once. It is now treated
   as missing information, as a sampled memory of `0` already was. The
   prototype carries this too, masked by its slower monitoring.
10. The dry-run path returned a plain `subprocess.Popen`, which has no
    `.nice()`. Fixed here the same way it was later fixed in the
    prototype: by returning a `psutil.Popen`.

## Running the tests

```bash
cd MC/workflow_runner
python -m pytest o2dpg_runner/tests/ -q
```

`pytest` is required. The tests run in CI, in the `Workflow-runner unit
tests` job of `.github/workflows/syntax-checks.yml`.

The tests cover:
- `test_graph.py` — Kahn topological sort, memoized descendants/ancestors,
  longest path, diamond + deep-chain cases.
- `test_workflow.py` — load, global-init extraction, filtering by target
  and by label, regex, resource-estimate update.
- `test_resources.py` — booking/unbooking, semaphores, related-task
  grouping, dynamic sampling, limit enforcement.
- `test_scheduler.py` — all three policies, the `should_break` quirk
  and its removal, `n_backfill_max` cap, semaphore blocking.
- `test_cache.py` — cache policies (off/lenient/strict), fingerprint
  sensitivity, sidecar round-trip.
- `test_executor_e2e.py` — the tiny fixture workflow driven end-to-end
  with real subprocesses, exercising each policy, `--dry-run`,
  `--produce-script`, rerun-from-cache behavior.
- `test_simulator.py` — simulator-only coverage for Amdahl-derived
  critical-path weights, unschedulable-task handling, and simulated
  backfill behaviour (`slowdown` and `holefill`).

Integration test (from the prototype, still valid):
```bash
NSIGEVENTS=5 NTIMEFRAMES=2 bash MC/bin/tests/wf_test_pp.sh
```

## A/B measurement

The Python entry point accepts the same `workflow.json` under all
scheduling policies. A typical comparison:

```bash
# baseline (prototype-equivalent)
./o2dpg_workflow_runner.py -f wf.json \
    --metric-logfile metric_timeframe.log

# drop the should_break quirk
./o2dpg_workflow_runner.py -f wf.json --drop-should-break \
    --metric-logfile metric_timeframe_nobrk.log

# critical path
./o2dpg_workflow_runner.py -f wf.json --scheduler-policy critical-path \
    --metric-logfile metric_cp.log

# best-fit bin-packing
./o2dpg_workflow_runner.py -f wf.json --scheduler-policy best-fit \
    --metric-logfile metric_bf.log
```

The metric logs have the same schema as before (`o2dpg_sim_metrics.py`
post-processing is unaffected), plus the run's meta line now records
`scheduler_policy`, `drop_should_break`, and `cache_policy` for easy
downstream grouping.

## Simulator notes

`MC/bin/o2dpg_schedule_simulator.py` is an offline discrete-event model
of the runner. It exists to compare policies and tune worker-count /
resource parameters quickly, not to emulate Linux scheduling perfectly.

- The simulator now uses the same walltime-weighted critical-path input
  as the runner when learned `resources.walltime` data is available.
- Amdahl worker overrides are applied before simulator scheduler-state
  construction, so optimization runs evaluate policies against the same
  task costs they simulate.
- Tasks that exceed the hard simulated CPU/MEM limits are kept in the
  workflow model and reported as unschedulable, rather than being
  dropped from resource bookkeeping.

### Simulated backfill

The real runner has a two-lane admission model: default tasks stay
within the hard budget, while backfill tasks may use a bounded amount of
overcommit and run at lower priority. The simulator now offers a
"sweet-spot" family of approximations for that behaviour:

- `--backfill-model off` — no backfill, one hard budget only.
- `--backfill-model structural` — replay the runner's second admission
  lane (`n_backfill`, CPU factor, MEM factor), but do not change task
  duration.
- `--backfill-model slowdown` — same structural backfill admission, plus
  a single fitted slowdown factor applied to backfill task walltimes.
- `--backfill-model holefill` — preferred realistic mode. Foreground
  tasks keep their nominal duration; backfill tasks consume only the CPU
  left idle by currently running foreground tasks. When the foreground
  hole is smaller than the task's nominal CPU demand, the task slows
  down proportionally. When the hole is large enough, it runs at nominal
  speed.

Relevant knobs:

- `--n-backfill`
- `--backfill-cpu-factor`
- `--backfill-mem-factor`
- `--backfill-slowdown-factor`

`holefill` is the recommended mode for scheduling studies: it
keeps simulated CPU efficiency physically bounded by 100%, tracks
observed runtime improvements from backfilling much better than the
single-factor slowdown model, and still stays simple enough to explain.

Two modelling choices are worth keeping in mind:

- foreground tasks are assumed not to slow down due to backfill;
- hole allocation is online and greedy, so enabling backfill may still
  change the order in which later tasks become runnable.

This is intentionally a scheduler-level approximation, not a kernel CPU
sharing model. It is accurate enough for comparative studies while still
remaining easy to reason about and calibrate against real runs.

### Suggested simulator usage

For realistic policy comparison, use learned resources and the holefill
backfill model:

```bash
./o2dpg_schedule_simulator.py \
  --timeframes 1 2 4 5 8 12 20 \
  --update-resources learned.json \
  -f workflow.json \
  --backfill-model holefill
```

Use `off` as the baseline and `holefill` as the realistic backfill
comparison. The older `slowdown` mode remains useful as a coarse control
study, but it is no longer the preferred setting for reporting numbers.
