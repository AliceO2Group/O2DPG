import time
import tempfile
import os
import pytest
import pandas as pd
from perfmonitor.performance_logger import (
    PerformanceLogger,
    default_summary_config,
    default_plot_config,
)

def test_basic_logging_and_parsing():
    with tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix=".txt") as tmp:
        log_path = tmp.name

    logger = PerformanceLogger(log_path)
    logger.log("start")
    time.sleep(0.1)
    logger.log("step::loop", index=[0])
    time.sleep(0.1)
    logger.log("step::loop", index=[1, 2])

    df = PerformanceLogger.log_to_dataframe([log_path])
    assert not df.empty
    assert "step" in df.columns
    assert "elapsed_sec" in df.columns
    assert "rss_gb" in df.columns
    assert df["step"].str.contains("step::loop").any()
    assert "index_1" in df.columns  # tests index parsing

    os.remove(log_path)


def test_missing_log_file_handling():
    df = PerformanceLogger.log_to_dataframe(["nonexistent_file.txt"])
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_plot_and_summary(tmp_path):
    log_path = tmp_path / "log.txt"
    logger = PerformanceLogger(log_path)
    logger.log("init")
    time.sleep(0.05)
    for i in range(3):
        logger.log("step::loop", index=[i])
        time.sleep(0.01)

    df = PerformanceLogger.log_to_dataframe([str(log_path)])

    summary = PerformanceLogger.summarize_with_config(df, default_summary_config)
    assert isinstance(summary, dict)
    assert "summary_by_step" in summary

    # Test plotting (non-crashing)
    PerformanceLogger.plot(df, default_plot_config)


def test_multiple_files():
    paths = []
    for i in range(2):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            path = tmp.name
        logger = PerformanceLogger(path)
        logger.log(f"file{i}::start")
        paths.append(path)

    df = PerformanceLogger.log_to_dataframe(paths)
    assert len(df) == 2
    assert "logfile" in df.columns
    for path in paths:
        os.remove(path)


def test_custom_summary():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        log_path = tmp.name

    logger = PerformanceLogger(log_path)
    for i in range(3):
        logger.log("step::measure", index=[i])
        time.sleep(0.01)

    df = PerformanceLogger.log_to_dataframe([log_path])
    config = {
        "by_index": {
            "by": ["index_0"],
            "stats": ["mean", "count"]
        }
    }
    summary = PerformanceLogger.summarize_with_config(df, config)
    assert "by_index" in summary
    os.remove(log_path)
