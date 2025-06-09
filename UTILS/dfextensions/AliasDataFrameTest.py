import unittest
import pandas as pd
import numpy as np
import os
from AliasDataFrame import AliasDataFrame  # Adjust if needed

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
        self.adf.materialize_all()
        expected = self.adf.df["x"] + self.adf.df["y"]
        pd.testing.assert_series_equal(self.adf.df["z"], expected, check_names=False)

    def test_dtype(self):
        self.adf.add_alias("z", "x + y", dtype=np.float16)
        self.adf.materialize_all()
        self.assertEqual(self.adf.df["z"].dtype, np.float16)

    def test_constant(self):
        self.adf.add_alias("c", "42.0", dtype=np.float32, is_constant=True)
        self.adf.add_alias("z", "x + c")
        self.adf.materialize_all()
        expected = self.adf.df["x"] + 42.0
        pd.testing.assert_series_equal(self.adf.df["z"], expected, check_names=False)

    def test_dependency_order(self):
        self.adf.add_alias("a", "x + y")
        self.adf.add_alias("b", "a * 2")
        self.adf.materialize_all()
        expected = (self.adf.df["x"] + self.adf.df["y"]) * 2
        pd.testing.assert_series_equal(self.adf.df["b"], expected, check_names=False)

    def test_log_rate_with_constant(self):
        median = self.adf.df["CTPLumi_countsFV0"].median()
        self.adf.add_alias("countsFV0_median", f"{median}", dtype=np.float16, is_constant=True)
        self.adf.add_alias("logRate", "log(CTPLumi_countsFV0/countsFV0_median)", dtype=np.float16)
        self.adf.materialize_all()
        expected = np.log(self.adf.df["CTPLumi_countsFV0"] / median).astype(np.float16)
        pd.testing.assert_series_equal(self.adf.df["logRate"], expected, check_names=False)

class TestAliasDataFrameWithSubframes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        n_tracks = 1000
        n_clusters = 100
        cls.df_tracks = pd.DataFrame({
            "track_index": np.arange(n_tracks),
            "mX": np.random.normal(0, 10, n_tracks),
            "mY": np.random.normal(0, 10, n_tracks),
            "mZ": np.random.normal(0, 10, n_tracks),
            "mPt": np.random.exponential(1.0, n_tracks),
            "mEta": np.random.normal(0, 1, n_tracks),
        })

        cluster_idx = np.repeat(cls.df_tracks["track_index"], n_clusters)
        cls.df_clusters = pd.DataFrame({
            "track_index": cluster_idx,
            "mX": np.random.normal(0, 10, len(cluster_idx)),
            "mY": np.random.normal(0, 10, len(cluster_idx)),
            "mZ": np.random.normal(0, 10, len(cluster_idx)),
        })

        cls.adf_tracks = AliasDataFrame(cls.df_tracks)
        cls.adf_clusters = AliasDataFrame(cls.df_clusters)
        cls.adf_clusters.register_subframe("T", cls.adf_tracks)

    def test_alias_cluster_radius(self):
        self.adf_clusters.add_alias("mR", "sqrt(mX**2 + mY**2)")
        self.adf_clusters.materialize_all()
        expected = np.sqrt(self.adf_clusters.df["mX"]**2 + self.adf_clusters.df["mY"]**2)
        pd.testing.assert_series_equal(self.adf_clusters.df["mR"], expected, check_names=False)

    def test_alias_cluster_track_dx(self):
        self.adf_clusters.add_alias("mDX", "mX - T.mX")
        self.adf_clusters.materialize_all()
        merged = self.adf_clusters.df.merge(self.adf_tracks.df, on="track_index", suffixes=("", "_track"))
        expected = merged["mX"] - merged["mX_track"]
        pd.testing.assert_series_equal(self.adf_clusters.df["mDX"].reset_index(drop=True), expected.reset_index(drop=True), check_names=False)

    def test_save_and_load_integrity(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path_clusters = os.path.join(tmpdir, "clusters.parquet")
            path_tracks = os.path.join(tmpdir, "tracks.parquet")
            self.adf_clusters.save(path_clusters)
            self.adf_tracks.save(path_tracks)

            adf_tracks_loaded = AliasDataFrame.load(path_tracks)
            adf_clusters_loaded = AliasDataFrame.load(path_clusters)
            adf_clusters_loaded.register_subframe("T", adf_tracks_loaded)
            adf_clusters_loaded.add_alias("mDX", "mX - T.mX")
            adf_clusters_loaded.materialize_all()

            assert "mDX" in adf_clusters_loaded.df.columns
            # Check mean difference is negligible
            mean_diff = np.mean(adf_clusters_loaded.df["mDX"] - self.adf_clusters.df["mDX"])
            assert abs(mean_diff) < 1e-3, f"Mean difference too large: {mean_diff}"

if __name__ == "__main__":
    unittest.main()
