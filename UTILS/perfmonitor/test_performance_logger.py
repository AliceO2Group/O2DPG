# test_performance_logger.py
import unittest
import os
import pandas as pd
from UTILS.perfmonitor.performance_logger import PerformanceLogger, default_plot_config, default_summary_config

class TestPerformanceLogger(unittest.TestCase):
    def setUp(self):
        self.log_path = "test_log.txt"
        self.logger = PerformanceLogger(self.log_path)
        # Ensure the log file is empty before each test
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def tearDown(self):
        # Clean up the log file after each test
        if os.path.exists(self.log_path):
            os.remove(self.log_path)

    def test_log(self):
        self.logger.log("TestStep")
        self.assertTrue(os.path.exists(self.log_path))
        with open(self.log_path, "r") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("TestStep", lines[0])

    def test_log_to_dataframe(self):
        self.logger.log("TestStep")
        df = PerformanceLogger.log_to_dataframe(self.log_path)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["step"], "TestStep")

    def test_summarize_with_config(self):
        self.logger.log("Step1")
        self.logger.log("Step2")
        df = PerformanceLogger.log_to_dataframe(self.log_path)
        summary = PerformanceLogger.summarize_with_config(df, default_summary_config["summary_by_step"])
        self.assertIn("elapsed_sec", summary.columns)
        self.assertIn("rss_gb", summary.columns)

    def test_plot(self):
        self.logger.log("Step1")
        self.logger.log("Step2")
        df = PerformanceLogger.log_to_dataframe(self.log_path)
        try:
            PerformanceLogger.plot(df, default_plot_config)
        except Exception as e:
            self.fail(f"Plotting failed with exception: {e}")

if __name__ == "__main__":
    unittest.main()

