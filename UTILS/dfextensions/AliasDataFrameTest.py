import unittest
import pandas as pd
import numpy as np
from AliasDataFrame import AliasDataFrame  # Adjust this if you're using a different import method

class TestAliasDataFrame(unittest.TestCase):
    def setUp(self):
        df = pd.DataFrame({
            "x": np.arange(5),
            "y": np.arange(5, 10),
            "CTPLumi_countsFV0": np.array([2000, 2100, 2200, 2300, 2400])
        })
        self.adf = AliasDataFrame(df)

    def test_basic_alias(self):
        self.adf.add_alias("z", "x + y")
        self.adf.materialize_alias("z")
        expected = self.adf.df["x"] + self.adf.df["y"]
        pd.testing.assert_series_equal(self.adf.df["z"], expected, check_names=False)

    def test_dtype(self):
        self.adf.add_alias("z", "x + y", dtype=np.float16)
        self.adf.materialize_alias("z")
        self.assertEqual(self.adf.df["z"].dtype, np.float16)

    def test_constant(self):
        self.adf.add_alias("c", "42.0", dtype=np.float32, is_constant=True)
        self.adf.add_alias("z", "x + c")
        self.adf.materialize_alias("z")
        expected = self.adf.df["x"] + 42.0
        pd.testing.assert_series_equal(self.adf.df["z"], expected, check_names=False)

    def test_dependency_order(self):
        self.adf.add_alias("a", "x + y")
        self.adf.add_alias("b", "a * 2")
        self.adf.materialize_alias("b")
        expected = (self.adf.df["x"] + self.adf.df["y"]) * 2
        pd.testing.assert_series_equal(self.adf.df["b"], expected, check_names=False)

    def test_log_rate_with_constant(self):
        median = self.adf.df["CTPLumi_countsFV0"].median()
        self.adf.add_alias("countsFV0_median", f"{median}", dtype=np.float16, is_constant=True)
        self.adf.add_alias("logRate", "log(CTPLumi_countsFV0/countsFV0_median)", dtype=np.float16)
        self.adf.materialize_alias("logRate")
        expected = np.log(self.adf.df["CTPLumi_countsFV0"] / median).astype(np.float16)
        pd.testing.assert_series_equal(self.adf.df["logRate"], expected, check_names=False)

if __name__ == "__main__":
    unittest.main()
