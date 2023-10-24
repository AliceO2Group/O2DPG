# Simulation examples

## Create and run a simulation workflow

The script [O2DPG_pp_minbias.sh](O2DPG_pp_minbias.sh) contains 4 steps:
1. creation of the simulation workflow,
1. execution of the workflow up until AOD stage,
1. running QC (optional. if requested),
1. running test analyses (optional, if requested).

To execute the script (here with QC and test analyses), run
```bash
DOQC=1 DOANALYSIS=1 ${O2DPG_ROOT}/MC/run/examples/O2DPG_pp_minbias.sh
```

There are additional settings to control memory can CPU usage. Similar to the `DOQC` or `DOANALYSIS` flag, you can prepend for instance
* `MEMLIMIT=12000`, which would set the memory limit to 12,000 MB,
* `CPULIMIT=12`, which would set the number of CPUs to use to 8,
to the above execution line.
