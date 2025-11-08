import unittest
import pandas as pd
import numpy as np
import os
from dfextensions.AliasDataFrame import AliasDataFrame  # Adjust if needed
import tempfile

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

    def test_circular_dependency_raises_error(self):
        self.adf.add_alias("a", "b * 2")
        with self.assertRaises(ValueError):
            self.adf.add_alias("b", "a + 1")

    def test_undefined_symbol_raises_error(self):
        self.adf.add_alias("z", "x + non_existent_variable")
        with self.assertRaises(Exception):
            self.adf.materialize_all()

    def test_invalid_syntax_raises_error(self):
        self.adf.add_alias("z", "x +* y")
        with self.assertRaises(SyntaxError):
            self.adf.materialize_all()

    def test_partial_materialization(self):
        self.adf.add_alias("a", "x + 1")
        self.adf.add_alias("b", "a + 1")
        self.adf.add_alias("c", "y + 1")
        self.adf.materialize_alias("b")
        self.assertIn("a", self.adf.df.columns)
        self.assertIn("b", self.adf.df.columns)
        self.assertNotIn("c", self.adf.df.columns)

    def test_export_import_tree_roundtrip(self):
        df = pd.DataFrame({
            "x": np.linspace(0, 10, 100),
            "y": np.linspace(10, 20, 100)
        })
        adf = AliasDataFrame(df)
        adf.add_alias("z", "x + y", dtype=np.float64)
        adf.materialize_all()

        with tempfile.NamedTemporaryFile(suffix=".root", delete=False) as tmp:
            adf.export_tree(tmp.name, treename="testTree", dropAliasColumns=False)
            tmp_path = tmp.name

        adf_loaded = AliasDataFrame.read_tree(tmp_path, treename="testTree")

        assert "z" in adf_loaded.aliases
        assert adf_loaded.aliases["z"] == "x + y"
        adf_loaded.materialize_alias("z")
        pd.testing.assert_series_equal(adf.df["z"], adf_loaded.df["z"], check_names=False)

        os.remove(tmp_path)
    def test_getattr_column_and_alias_access(self):
        df = pd.DataFrame({
            "x": np.arange(5),
            "y": np.arange(5) * 2
        })
        adf = AliasDataFrame(df)
        adf.add_alias("z", "x + y", dtype=np.int32)

        # Access real column
        assert (adf.x == df["x"]).all()
        # Access alias before materialization
        assert "z" not in adf.df.columns
        z_val = adf.z
        assert "z" in adf.df.columns
        expected = df["x"] + df["y"]
        np.testing.assert_array_equal(z_val, expected)


class TestAliasDataFrameWithSubframes(unittest.TestCase):
    def setUp(self):
        n_tracks = 1000
        n_clusters = 100
        df_tracks = pd.DataFrame({
            "track_index": np.arange(n_tracks),
            "mX": np.random.normal(0, 10, n_tracks),
            "mY": np.random.normal(0, 10, n_tracks),
            "mZ": np.random.normal(0, 10, n_tracks),
            "mPt": np.random.exponential(1.0, n_tracks),
            "mEta": np.random.normal(0, 1, n_tracks),
        })

        cluster_idx = np.repeat(df_tracks["track_index"], n_clusters)
        df_clusters = pd.DataFrame({
            "track_index": cluster_idx,
            "mX": np.random.normal(0, 10, len(cluster_idx)),
            "mY": np.random.normal(0, 10, len(cluster_idx)),
            "mZ": np.random.normal(0, 10, len(cluster_idx)),
        })

        self.df_tracks = df_tracks
        self.df_clusters = df_clusters

    def test_alias_cluster_track_dx(self):
        adf_clusters = AliasDataFrame(self.df_clusters.copy())
        adf_tracks = AliasDataFrame(self.df_tracks.copy())
        adf_clusters.register_subframe("T", adf_tracks, index_columns="track_index")
        adf_clusters.add_alias("mDX", "mX - T.mX")
        adf_clusters.materialize_all()
        merged = adf_clusters.df.merge(adf_tracks.df, on="track_index", suffixes=("", "_trk"))
        expected = merged["mX"] - merged["mX_trk"]
        pd.testing.assert_series_equal(adf_clusters.df["mDX"].reset_index(drop=True), expected.reset_index(drop=True), check_names=False)

    def test_subframe_invalid_alias_raises(self):
        adf_clusters = AliasDataFrame(self.df_clusters.copy())
        adf_tracks = AliasDataFrame(self.df_tracks.copy())
        adf_clusters.register_subframe("T", adf_tracks, index_columns="track_index")
        adf_clusters.add_alias("invalid", "T.nonexistent")

        with self.assertRaises(KeyError) as cm:
            adf_clusters.materialize_alias("invalid")

        self.assertIn("T", str(cm.exception))
        self.assertIn("nonexistent", str(cm.exception))

    def test_save_and_load_integrity(self):
        adf_clusters = AliasDataFrame(self.df_clusters.copy())
        adf_tracks = AliasDataFrame(self.df_tracks.copy())
        adf_clusters.register_subframe("T", adf_tracks, index_columns="track_index")
        adf_clusters.add_alias("mDX", "mX - T.mX")
        adf_clusters.materialize_all()

        with tempfile.TemporaryDirectory() as tmpdir:
            path_clusters = os.path.join(tmpdir, "clusters.parquet")
            path_tracks = os.path.join(tmpdir, "tracks.parquet")
            adf_clusters.save(path_clusters)
            adf_tracks.save(path_tracks)

            adf_tracks_loaded = AliasDataFrame.load(path_tracks)
            adf_clusters_loaded = AliasDataFrame.load(path_clusters)
            adf_clusters_loaded.register_subframe("T", adf_tracks_loaded, index_columns="track_index")
            adf_clusters_loaded.add_alias("mDX", "mX - T.mX")
            adf_clusters_loaded.materialize_all()

            self.assertIn("mDX", adf_clusters_loaded.df.columns)
            merged = adf_clusters_loaded.df.merge(adf_tracks_loaded.df, on="track_index", suffixes=("", "_trk"))
            expected = merged["mX"] - merged["mX_trk"]
            pd.testing.assert_series_equal(adf_clusters_loaded.df["mDX"].reset_index(drop=True), expected.reset_index(drop=True), check_names=False)
            self.assertDictEqual(adf_clusters.aliases, adf_clusters_loaded.aliases)

    def test_getattr_subframe_alias_access(self):
        # Parent frame
        df_main = pd.DataFrame({"track_id": [0, 1, 2], "x": [10, 20, 30]})
        adf_main = AliasDataFrame(df_main)
        # Subframe with alias
        df_sub = pd.DataFrame({"track_id": [0, 1, 2], "residual": [1.1, 2.2, 3.3]})
        adf_sub = AliasDataFrame(df_sub)
        adf_sub.add_alias("residual_scaled", "residual * 100", dtype=np.float64)

        # Register subframe
        adf_main.register_subframe("track", adf_sub, index_columns="track_id")

        # Add alias depending on subframe alias
        adf_main.add_alias("resid100", "track.residual_scaled", dtype=np.float64)

        # Trigger materialization via __getattr__
        assert "resid100" not in adf_main.df.columns
        result = adf_main.resid100
        assert "resid100" in adf_main.df.columns
        np.testing.assert_array_equal(result, df_sub["residual"] * 100)



    def test_getattr_chained_subframe_access(self):
        df_main = pd.DataFrame({"id": [0, 1, 2]})
        df_sub = pd.DataFrame({"id": [0, 1, 2], "a": [5, 6, 7]})
        adf_main = AliasDataFrame(df_main)
        adf_sub = AliasDataFrame(df_sub)
        adf_sub.add_alias("cutA", "a > 5")
        adf_main.register_subframe("sub", adf_sub, index_columns="id")

        adf_sub.materialize_alias("cutA")

        # Check chained access
        expected = np.array([False, True, True])
        assert np.all(adf_main.sub.cutA == expected)  # explicit value check

    def test_multi_column_index_join(self):
        """Test subframe join with composite key (track_index, firstTFOrbit)"""
        df_main = pd.DataFrame({
            'track_index': [0, 0, 1, 1],
            'firstTFOrbit': [100, 200, 100, 200],
            'x': [1, 2, 3, 4]
        })
        df_sub = pd.DataFrame({
            'track_index': [0, 0, 1, 1],
            'firstTFOrbit': [100, 200, 100, 200],
            'y': [10, 20, 30, 40]
        })

        adf_main = AliasDataFrame(df_main)
        adf_sub = AliasDataFrame(df_sub)
        adf_main.register_subframe("T", adf_sub, index_columns=["track_index", "firstTFOrbit"])
        adf_main.add_alias("sum_xy", "x + T.y")
        adf_main.materialize_alias("sum_xy")

        expected = [11, 22, 33, 44]
        np.testing.assert_array_equal(adf_main.df['sum_xy'].values, expected)

if __name__ == "__main__":
    unittest.main()
