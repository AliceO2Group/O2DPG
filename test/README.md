# O2DPG related tests

Tests are run via
```bash
${O2DPG_ROOT}/test/run_tests.sh <test_names>
```

Test implementations are placed in `${O2DPG_ROOT}/test/` and must be called `test-<test_name>.sh`.

Each test will be executed in a sub-directory and the standard and error output are piped into `<test_name>.sh.log` for later inspection. In case of an error, the log will also be printed.

To run all tests, just run with `all` as the single argument.

At the moment, the main script will exit as soon as there is a problem with one of the tests. This behaviour might change in the future.

## Adding a test

Simply add a new script with your test instructions. Make sure it exits with `!=0` in case the test fails and with `==0` if the test is assumed to successful. Make sure the script is executable, e.g. via`
```bash
chmod u+x test-<your_test_name>.sh
```
