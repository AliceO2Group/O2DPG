# O2DPG related tests


## Generator related tests

At the moment, the tests focus on generator configurations and custom generators as defined in the respective `ini` files.

Tests are run via
```bash
${O2DPG_ROOT}/test/run_tests.sh [--fail-immediately] [--keep-artifacts] [SUBTEST...]
```

Tests are run for changed
1. generator `ini` files,
1. test macros of a certain generator `ini` file,
1. macros that are used in generator `ini` files,
1. macros that are included in macros which are in turn used in generator `ini` files.

Passing the flag `--fail-immediately` aborts as soon as one test fails. Otherwise, all tests will be at least tried.

### Adding tests

Whenever an `ini` file is detedcted to be tested, a test macro is required to be present that checks the simulation kinematics. The macro is expected in a `tests/` directory which should be located next to the `ini` file itself. To be identified, the macro must have the name as
```bash
<name-of-ini-file>.C
```
Note, that `run_tests.sh` will automatically detect all generators used in an `ini`. For at least one generator defined in the `ini` file there must be a test. Each test is defined as a function in the `<name-of-ini-file>.C` macro. Assuming you want to test `External`, `Pythia8` and `Hybrid` generators, the macro should look like
```cpp
int pythia8()
{
    // do your test
    return ret;
}

int External()
{
    // do your test
    return ret;
}

int Hybrid()
{
    // do your test
    return ret;
}
```
The return type must be an integer, `0` in case of success and `!=0` in case of failure.

## Important notes and instructions

### Run test locally

If there is an `O2DPG` environment loaded and the source directory with development changes is different from what is behind `O2DPG_ROOT`, the test should be run with
```bash
O2DPG_TEST_REPO_DIR=</path/to/source/O2DPG> ${O2DPG_ROOT}/test/run_tests.sh [--fail-immediately]
```
If you are inside the source directory, you can simply run
```bash
${O2DPG_ROOT}/test/run_tests.sh [--fail-immediately] [--keep-artifacts] [SUBTEST...]
```
If the change you are testing is to a test script itself (`run_tests.sh` or
any `run_*_tests.sh`), invoke the checkout's own entrypoint instead, e.g.
`bash test/run_tests.sh` from inside the checkout: `run_tests.sh` finds its
sub-scripts next to itself, so calling `${O2DPG_ROOT}/test/run_tests.sh`
tests the *released* copy of the script you just edited, not your change,
even with `O2DPG_TEST_REPO_DIR` pointed at the checkout.

### Running a subset

`run_tests.sh` runs the generator, workflow and RelVal sub-tests. To run only
some of them, name them:

```bash
${O2DPG_ROOT}/test/run_tests.sh generator relval
```

The offline harnesses under `test/tests/` check the entrypoint's selection,
exit-code aggregation and O2PDPSuite tag resolution without needing an O2
environment:

```bash
bash test/tests/run_tests_selection.sh
bash test/tests/exit_code_aggregation.sh
bash test/tests/resolve_tag.sh
```

### Keeping all test artifacts

By default, all test artifacts except for logs are removed after each single test is over to save disk space. If you want to keep everything, run with
```bash
${O2DPG_ROOT}/test/run_tests.sh --keep-artifacts
```

### More help

For more help, run
```bash
${O2DPG_ROOT}/test/run_tests.sh -h
```
which will give you
```

usage: run_tests.sh [--fail-immediately] [--keep-artifacts] [SUBTEST...]

  SUBTEST : one or more of: generator workflow relval (default: all)

  FLAGS:

  --fail-immediately : stop after the first failing sub-test
  --keep-artifacts   : keep simulation artifacts, not just the logs

  ENVIRONMENT VARIABLES:

  O2DPG_TEST_REPO_DIR  : the source repository to test
  O2DPG_TEST_HASH_BASE : base hash for the changed-file diff (optional)
  O2DPG_TEST_HASH_HEAD : head hash for the changed-file diff (optional)

```

## When your change needs an unreleased O2

The `Simulation tests against CVMFS` check runs against a published
`O2PDPSuite` release, so a change that depends on an unmerged or unreleased O2
commit cannot pass it. Two escape hatches, in order of preference:

1. If the O2 change is already in a published daily, pin it: add a line
   `sim-tests-tag: daily-YYYYMMDD-HHMM-1` to the pull request description.
2. If it is not published anywhere yet, touch `test/needs-o2-dev` with a
   one-line reason and a link to the O2 pull request. That enables
   `build/O2DPG/sim/o2dev`, which builds O2 from source against `dev`. It is
   much slower, so it is opt-in.
