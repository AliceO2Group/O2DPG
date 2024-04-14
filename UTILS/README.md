# General utilities

## Fetching PRs (based on labels)

The tool [`o2dpg_make_github_pr_report.py`](o2dpg_make_github_pr_report.py) can be used to create a markdown report PRs in a given repository.
Note that PRs are fetched and reported based on assigned labels. By default, the report tool will look for labels of the form `async-*`.
PRs are fetched and sorted first by their state, closed and merged, just closed and open.
Within that sorting, they are grouped by assigned labels and the last sorting is based on time. The time-based sorting is based on

* state `closed` and `merged`: `merged_at`,
* state `closed` and not `merged`: `updated_at`,
* state `open`: `updated_at.`

To fetch for instance PRs for `O2`, the following command would do the job and it will write the markdown report to `o2dpg_pr_report_O2DPG.md`:
```bash
./UTILS/o2dpg_make_github_pr_report.py --repo O2DPG
```

A few more things can be configured. To see the full list of options and flags, type
```bash
./UTILS/o2dpg_make_github_pr_report.py --help
```
