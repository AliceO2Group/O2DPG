# Performance Monitor

Lightweight logging and analysis utility for tracking performance (execution time and memory) of scripts or processing pipelines.

## Features

* Logs elapsed time and memory (RSS) per step
* Supports multi-level index tags for loop tracking
* Saves logs in delimiter-separated format (default: `|`)
* Parses logs to `pandas.DataFrame` for analysis
* Summarizes stats (mean, max, min) with configurable grouping
* Plots memory/time using `matplotlib`
* Optionally saves plots to a PDF
* Combines logs from multiple files

## Installation

This is a self-contained utility. Just place the `perfmonitor/` directory into your Python path.

## Example Usage

```python
import time
import pandas as pd
import matplotlib.pyplot as plt
from perfmonitor import PerformanceLogger, default_plot_config, default_summary_config

# Initialize logger
logger = PerformanceLogger("perf_log.txt")
logger.log("setup::start")

# Simulate steps with increasing delays
for i, delay in enumerate([0.1, 0.2, 0.3]):
    time.sleep(delay)
    logger.log("loop::step", index=[i])

# Parse logs from one or more files
df = PerformanceLogger.log_to_dataframe(["perf_log.txt"])
print(df.head())
```

### Expected Output

Example output from `print(df.head())`:

```
              timestamp            step  elapsed_sec  rss_gb        user             host       logfile  index_0
0  2025-05-31 09:12:01,120  setup::start         0.00     0.13     user123      host.local  perf_log.txt      NaN
1  2025-05-31 09:12:01,220  loop::step[0]        0.10     0.14     user123      host.local  perf_log.txt      0.0
2  2025-05-31 09:12:01,420  loop::step[1]        0.20     0.15     user123      host.local  perf_log.txt      1.0
3  2025-05-31 09:12:01,720  loop::step[2]        0.30     0.15     user123      host.local  perf_log.txt      2.0
```

## Summary Statistics

```python
summary = PerformanceLogger.summarize_with_config(df, default_summary_config)
print(summary)
```

### Example Summary Output

```
Out[5]:
{'summary_by_step':              elapsed_sec                  rss_gb
                     mean   max  min count   mean   max   min count
 step
 loop::step          0.34  0.61  0.1    15  0.148  0.22  0.13    15
 setup::start        0.00  0.00  0.0     5  0.148  0.22  0.13     5,
 'summary_by_step_and_index':                    elapsed_sec                   rss_gb
                           mean   max   min count   mean   max   min count
 step       index_0
 loop::step 0.0           0.102  0.11  0.10     5  0.148  0.22  0.13     5
            1.0           0.308  0.31  0.30     5  0.148  0.22  0.13     5
            2.0           0.610  0.61  0.61     5  0.148  0.22  0.13     5}
```

## Plotting

```python
# Show plots
PerformanceLogger.plot(df, default_plot_config)

# Save plots to PDF
PerformanceLogger.plot(df, default_plot_config, output_pdf="perf_plots.pdf")
```

## Multi-Level Index Extraction

Step IDs can include index metadata like:

```
load::data[1,2]
```

This will be automatically parsed into new DataFrame columns:

* `index_0` → 1
* `index_1` → 2

## Advanced: Custom Configuration
can be obtained modyfying the `default_plot_config` and `default_summary_config` dictionaries.
and invoking the `PerformanceLogger.plot` and `PerformanceLogger.summarize_with_config` with that configs

PerformanceLogger.plot(df, default_plot_config, output_pdf="perf_plots.pdf")

```python
default_plot_config={
    "RSS vs Time": {
        "kind": "line",
        "varX": "timestamp",
        "varY": "rss_gb",
        "title": "RSS over Time",
        "sort": "timestamp"
    },
    "RSS vs Step (chronological)": {
        "kind": "line",
        "varX": "rowID",
        "varY": "rss_gb",
        "title": "RSS vs Step",
        "xlabel": "step",
        "xticklabels": "step",
        "sort": "rowID"
    },
    "Elapsed Time vs Step": {
        "kind": "bar",
        "varX": "step",
        "varY": "elapsed_sec",
        "title": "Elapsed Time per Step",
        "sort": None
    },
    "RSS Summary Stats": {
        "varX": "step",
        "varY": "rss_gb",
        "aggregation": ["mean", "median", "std"],
        "title": "RSS Summary Statistics",
        "xlabel": "Step",
        "ylabel": "RSS (GB)",
        "sort": "step"
    }
    
}

default_summary_config={
    "summary_by_step": {
        "by": ["step"],
        "stats": ["mean", "max", "min", "count"]
    },
    "summary_by_step_and_index": {
        "by": ["step", "index_0"],
        "stats": ["mean", "max", "min", "count"]
    }
}
```


## License
???
