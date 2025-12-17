# O2DPG related tests


## Generator related tests

At the moment, the tests focus on generator configurations and custom generators as defined in the respective `ini` files.

Tests are run via
```bash
${O2DPG_ROOT}/test/run_tests.sh [--fail-immediately]
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
Note, that `run_tests.sh` will automatically detect all generators used in an `ini`. For at least one generator defined in the `ini` file there must be a test. Each test is defined as a function in the `<name-of-ini-file>.C` macro. Assuming you want to test `External` and `Pythia8` generator, the macro should look like
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
${O2DPG_ROOT}/test/run_tests.sh [--fail-immediately]
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
usage: run_tests.sh [--fail-immediately] [--keep-artifacts]

  FLAGS:

  --fail-immediately : abort as soon as the first tests fails
  --keep-artifacts : keep simulation and tests artifacts, by default everything but the logs is removed after each test

  ENVIRONMENT VARIABLES:

  O2DPG_TEST_REPO_DIR : Point to the source repository you want to test.
  O2DPG_TEST_HASH_BASE : The base hash you want to use for comparison (optional)
  O2DPG_TEST_HASH_HEAD : The head hash you want to use for comparison (optional)

  If O2DPG_TEST_HASH_BASE is not set, it will be looked for ALIBUILD_BASE_HASH.
  If also not set, this will be set to HEAD~1. However, if there are unstaged
  changes, it will be set to HEAD.

  If O2DPG_TEST_HASH_HEAD is not set, it will be looked for ALIBUILD_HEAD_HASH.
  If also not set, this will be set to HEAD. However, if there are unstaged
  changes, it will left blank.
```
