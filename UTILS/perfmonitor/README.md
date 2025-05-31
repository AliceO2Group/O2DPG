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
              elapsed_sec           rss_gb
                     mean  max  min   mean   max   min
step
loop::step[0]         0.10 0.10 0.10  0.14  0.14  0.14
loop::step[1]         0.20 0.20 0.20  0.15  0.15  0.15
loop::step[2]         0.30 0.30 0.30  0.15  0.15  0.15
setup::start          0.00 0.00 0.00  0.13  0.13  0.13
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

```python
custom_summary = {
    "by": ["step", "index_0"],
    "stats": ["mean", "max"]
}

custom_plots = {
    "RSS Over Time": {
        "kind": "line",
        "varX": "timestamp",
        "varY": "rss_gb",
        "title": "RSS vs Time",
        "sort": "timestamp",
    }
}

PerformanceLogger.plot(df, custom_plots)
```

## License
???
