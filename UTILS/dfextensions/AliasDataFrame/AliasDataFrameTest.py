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

    def test_bidirectional_atan2_support(self):
        """Test that both atan2 (ROOT) and arctan2 (Python) work"""
        df = pd.DataFrame({
            'x': np.array([1.0, 0.0, -1.0, 0.0]),
            'y': np.array([0.0, 1.0, 0.0, -1.0])
        })
        adf = AliasDataFrame(df)

        # Python style (arctan2)
        adf.add_alias('phi_python', 'arctan2(y, x)', dtype=np.float32)
        adf.materialize_alias('phi_python')

        # ROOT style (atan2) - should also work
        adf.add_alias('phi_root', 'atan2(y, x)', dtype=np.float32)
        adf.materialize_alias('phi_root')

        # Should be identical
        np.testing.assert_allclose(adf.df['phi_python'], adf.df['phi_root'], rtol=1e-6)

        # Expected values
        expected = np.array([0.0, np.pi/2, np.pi, -np.pi/2], dtype=np.float32)
        np.testing.assert_allclose(adf.df['phi_python'], expected, rtol=1e-6)

    def test_undefined_function_helpful_error(self):
        """Test that undefined functions give helpful error messages"""
        df = pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})
        adf = AliasDataFrame(df)

        # Test 1: Undefined function
        adf.add_alias('bad', 'nonexistent_func(x)', dtype=np.float32)
        with self.assertRaises(NameError) as cm:
            adf.materialize_alias('bad')

        error_msg = str(cm.exception)
        # Check error message contains helpful info
        self.assertIn('nonexistent_func', error_msg)
        self.assertIn('Available functions include:', error_msg)
        self.assertIn('arctan2', error_msg)  # Should mention both forms
        self.assertIn('atan2', error_msg)

        # Test 2: Undefined variable
        adf.add_alias('bad2', 'x + undefined_var', dtype=np.float32)
        with self.assertRaises(NameError) as cm:
            adf.materialize_alias('bad2')

        error_msg = str(cm.exception)
        self.assertIn('undefined_var', error_msg)

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

class TestAliasDataFrameCompression(unittest.TestCase):
    """Test column compression functionality"""

    def setUp(self):
        """Create test data with values suitable for compression"""
        np.random.seed(42)
        df = pd.DataFrame({
            "dy": np.random.normal(0, 2.0, 1000).astype(np.float32),
            "dz": np.random.normal(0, 1.5, 1000).astype(np.float32),
            "tgSlp": np.random.uniform(-0.5, 0.5, 1000).astype(np.float32),
            "track_id": np.arange(1000)
        })
        self.adf = AliasDataFrame(df)
        self.original_dy = df["dy"].values.copy()

    def test_basic_compression_decompression(self):
        """Test basic compression creates correct structure"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec)

        # Check compressed column exists
        self.assertIn('dy_c', self.adf.df.columns)
        self.assertEqual(self.adf.df['dy_c'].dtype, np.int16)

        # Check original removed from storage
        self.assertNotIn('dy', self.adf.df.columns)

        # Check decompression alias exists
        self.assertIn('dy', self.adf.aliases)
        self.assertEqual(self.adf.aliases['dy'], 'sinh(dy_c/40.)')

        # Check compression_info populated
        self.assertIn('dy', self.adf.compression_info)
        info = self.adf.compression_info['dy']
        self.assertEqual(info['compressed_col'], 'dy_c')
        self.assertEqual(info['compressed_dtype'], 'int16')
        self.assertEqual(info['decompressed_dtype'], 'float16')

        # Materialize and check values approximately equal
        self.adf.materialize_alias('dy')
        decompressed = self.adf.df['dy'].values
        np.testing.assert_allclose(decompressed, self.original_dy, rtol=0.01, atol=0.05)

    def test_compression_with_precision_measurement(self):
        """Test optional precision measurement"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec, measure_precision=True)

        # Check precision info exists
        self.assertIn('precision', self.adf.compression_info['dy'])
        prec = self.adf.compression_info['dy']['precision']

        # Check all metrics present
        self.assertIn('rmse', prec)
        self.assertIn('max_error', prec)
        self.assertIn('mean_error', prec)

        # Sanity check values
        self.assertGreater(prec['rmse'], 0)
        self.assertLess(prec['rmse'], 0.1)  # Should be small for good compression

    def test_compress_alias_source(self):
        """Test compressing an alias (not materialized column)"""
        # Create alias first
        self.adf.add_alias('dy_scaled', 'dy * 2.0', dtype=np.float32)

        spec = {
            'dy_scaled': {
                'compress': 'round(asinh(dy_scaled)*40)',
                'decompress': 'sinh(dy_scaled_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        # Should work - compresses evaluated alias
        self.adf.compress_columns(spec)

        self.assertIn('dy_scaled_c', self.adf.df.columns)
        self.assertIn('dy_scaled', self.adf.aliases)

    def test_double_compression_raises_error(self):
        """Test that compressing already compressed column raises error"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec)

        # Try to compress again - should fail
        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns(spec)

        self.assertIn('already compressed', str(cm.exception))

    def test_compressed_column_name_collision_raises_error(self):
        """Test that compressed column name collision is detected"""
        # Create column that would conflict
        self.adf.df['dy_c'] = np.zeros(len(self.adf.df))

        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns(spec)

        self.assertIn('already exists', str(cm.exception))
        self.assertIn('dy_c', str(cm.exception))

    def test_decompress_inplace(self):
        """Test inplace decompression removes compressed column"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec)
        self.adf.decompress_columns(['dy'], inplace=True)

        # Check decompressed column is physical
        self.assertIn('dy', self.adf.df.columns)
        self.assertEqual(self.adf.df['dy'].dtype, np.float16)

        # Check compressed column removed
        self.assertNotIn('dy_c', self.adf.df.columns)

        # Check compression_info cleaned up
        self.assertNotIn('dy', self.adf.compression_info)

    def test_decompress_keep_compressed_false(self):
        """Test decompress with keep_compressed=False and keep_schema=False"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec)
        # New API: explicitly remove schema
        self.adf.decompress_columns(['dy'], keep_compressed=False, keep_schema=False)

        # Check decompressed column exists
        self.assertIn('dy', self.adf.df.columns)

        # Check compressed column removed
        self.assertNotIn('dy_c', self.adf.df.columns)

        # Check compression_info cleaned up
        self.assertNotIn('dy', self.adf.compression_info)

    def test_missing_compressed_column_raises_error(self):
        """Test error when compressed column is manually deleted"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec)

        # Manually delete compressed column (simulate corruption)
        self.adf.df.drop(columns=['dy_c'], inplace=True)

        # Should raise clear error
        with self.assertRaises(ValueError) as cm:
            self.adf.decompress_columns(['dy'])

        self.assertIn('missing', str(cm.exception).lower())
        self.assertIn('dy_c', str(cm.exception))

    def test_partial_failure_handling(self):
        """Test that failure on one column does not roll back prior successful compressions"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            },
            'dz': {
                'compress': 'dz +* invalid_syntax',  # Invalid expression
                'decompress': 'sinh(dz_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        # Should raise error on 'dz'
        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns(spec)

        # Check that 'dy' was successfully compressed (partial success)
        self.assertIn('dy_c', self.adf.df.columns)
        self.assertIn('dy', self.adf.aliases)
        self.assertIn('dy', self.adf.compression_info)

        # Check that 'dz' did NOT create compressed column
        self.assertNotIn('dz_c', self.adf.df.columns)
        self.assertNotIn('dz', self.adf.compression_info)

        # Check original 'dz' still exists
        self.assertIn('dz', self.adf.df.columns)

        # Check error message indicates the failure
        self.assertIn('Compression failed', str(cm.exception))
        self.assertIn('dz', str(cm.exception))

    def test_roundtrip_save_load(self):
        """Test compression metadata survives save/load"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            },
            'dz': {
                'compress': 'round(asinh(dz)*40)',
                'decompress': 'sinh(dz_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec, measure_precision=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "compressed.parquet")
            self.adf.save(path)

            adf_loaded = AliasDataFrame.load(path)

            # Check compression_info preserved (2 columns + __meta__)
            self.assertEqual(len(adf_loaded.compression_info), 3)
            self.assertIn('dy', adf_loaded.compression_info)
            self.assertIn('dz', adf_loaded.compression_info)

            # Check aliases preserved
            self.assertIn('dy', adf_loaded.aliases)
            self.assertEqual(adf_loaded.aliases['dy'], 'sinh(dy_c/40.)')

            # Check precision info preserved
            self.assertIn('precision', adf_loaded.compression_info['dy'])

            # Materialize and verify values
            adf_loaded.materialize_alias('dy')
            np.testing.assert_allclose(
                adf_loaded.df['dy'].values,
                self.original_dy,
                rtol=0.01, atol=0.05
            )

    def test_roundtrip_export_import_tree(self):
        """Test compression metadata survives ROOT export/import"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec)

        with tempfile.NamedTemporaryFile(suffix=".root", delete=False) as tmp:
            self.adf.export_tree(tmp.name, treename="compressed", dropAliasColumns=False)
            tmp_path = tmp.name

        try:
            adf_loaded = AliasDataFrame.read_tree(tmp_path, treename="compressed")

            # Check compression_info preserved
            self.assertIn('dy', adf_loaded.compression_info)

            # Check can use decompression alias
            adf_loaded.materialize_alias('dy')
            np.testing.assert_allclose(
                adf_loaded.df['dy'].values,
                self.original_dy,
                rtol=0.01, atol=0.05
            )
        finally:
            os.remove(tmp_path)

    def test_multiple_columns_compression(self):
        """Test compressing multiple columns at once"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            },
            'dz': {
                'compress': 'round(asinh(dz)*40)',
                'decompress': 'sinh(dz_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            },
            'tgSlp': {
                'compress': 'round(tgSlp*1000)',
                'decompress': 'tgSlp_c/1000.',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec)

        # Check all compressed
        self.assertIn('dy_c', self.adf.df.columns)
        self.assertIn('dz_c', self.adf.df.columns)
        self.assertIn('tgSlp_c', self.adf.df.columns)

        # Check all have decompression aliases
        self.assertIn('dy', self.adf.aliases)
        self.assertIn('dz', self.adf.aliases)
        self.assertIn('tgSlp', self.adf.aliases)

        # Check compression_info complete (3 columns + __meta__)
        self.assertEqual(len(self.adf.compression_info), 4)
        self.assertIn('__meta__', self.adf.compression_info)

    def test_get_compression_info(self):
        """Test compression info retrieval"""
        spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

        self.adf.compress_columns(spec)

        # Test single column info
        info = self.adf.get_compression_info('dy')
        self.assertIsInstance(info, dict)
        self.assertEqual(info['compressed_col'], 'dy_c')

        # Test all columns as DataFrame
        df_info = self.adf.get_compression_info()
        self.assertIsInstance(df_info, pd.DataFrame)
        self.assertEqual(len(df_info), 1)
        self.assertIn('dy', df_info.index)

    def test_backward_compatibility_no_compression_info(self):
        """Test loading old files without compression_info works"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "old_format.parquet")

            # Save without compression
            self.adf.save(path)

            # Load should work fine - __meta__ should be present
            adf_loaded = AliasDataFrame.load(path)
            # Only __meta__ should be present (no actual compressed columns)
            self.assertEqual(len(adf_loaded.compression_info), 1)
            self.assertIn('__meta__', adf_loaded.compression_info)


class TestCompressionStateMachine(unittest.TestCase):
    """Test compression state machine transitions and invariants"""

    def setUp(self):
        """Create test data for compression tests"""
        np.random.seed(42)
        df = pd.DataFrame({
            "dy": np.random.normal(0, 2.0, 1000).astype(np.float32),
            "dz": np.random.normal(0, 1.5, 1000).astype(np.float32),
            "tgSlp": np.random.uniform(-0.5, 0.5, 1000).astype(np.float32),
        })
        self.adf = AliasDataFrame(df)
        self.original_dy = df["dy"].values.copy()
        
        self.spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            },
            'dz': {
                'compress': 'round(asinh(dz)*40)',
                'decompress': 'sinh(dz_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }

    def test_metadata_versioning(self):
        """Test that __meta__ is present in compression_info"""
        self.assertIn("__meta__", self.adf.compression_info)
        meta = self.adf.compression_info["__meta__"]
        self.assertEqual(meta["schema_version"], 1)
        self.assertEqual(meta["state_machine"], "CompressionState.v1")

    def test_schema_only_definition(self):
        """Test SCHEMA_ONLY state (forward declaration)"""
        # Define schema without data
        self.adf.define_compression_schema(self.spec)
        
        # Check state is SCHEMA_ONLY
        from dfextensions.AliasDataFrame import CompressionState
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.SCHEMA_ONLY)
        self.assertEqual(self.adf.get_compression_state('dz'), CompressionState.SCHEMA_ONLY)
        
        # Check no physical columns created
        self.assertNotIn('dy_c', self.adf.df.columns)
        self.assertNotIn('dz_c', self.adf.df.columns)
        
        # Check original columns still exist
        self.assertIn('dy', self.adf.df.columns)
        self.assertIn('dz', self.adf.df.columns)
        
        # Check metadata stored
        info = self.adf.compression_info['dy']
        self.assertEqual(info['compressed_col'], 'dy_c')
        self.assertEqual(info['compress_expr'], self.spec['dy']['compress'])
        self.assertEqual(info['state'], CompressionState.SCHEMA_ONLY)

    def test_schema_only_then_compress(self):
        """Test SCHEMA_ONLY → COMPRESSED transition"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Step 1: Define schema
        self.adf.define_compression_schema(self.spec)
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.SCHEMA_ONLY)
        
        # Step 2: Apply compression using schema
        self.adf.compress_columns(columns=['dy'])
        
        # Check state transitioned to COMPRESSED
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        
        # Check physical columns exist
        self.assertIn('dy_c', self.adf.df.columns)
        self.assertEqual(self.adf.df['dy_c'].dtype, np.int16)
        
        # Check decompression alias exists
        self.assertIn('dy', self.adf.aliases)
        self.assertEqual(self.adf.aliases['dy'], self.spec['dy']['decompress'])
        
        # Check original removed
        self.assertNotIn('dy', self.adf.df.columns)

    def test_direct_compression_without_schema(self):
        """Test None → COMPRESSED transition (inline compression)"""
        from dfextensions.AliasDataFrame import CompressionState
        
        self.adf.compress_columns({'dy': self.spec['dy']})
        
        # Check state is COMPRESSED
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        
        # Check invariants
        self.assertIn('dy_c', self.adf.df.columns)
        self.assertIn('dy', self.adf.aliases)
        self.assertNotIn('dy', self.adf.df.columns)

    def test_full_compression_cycle(self):
        """Test COMPRESSED → DECOMPRESSED → COMPRESSED (recompression)"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Step 1: Compress
        self.adf.compress_columns({'dy': self.spec['dy']})
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        
        # Step 2: Decompress with keep_schema=True
        self.adf.decompress_columns(['dy'], keep_schema=True, keep_compressed=False)
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.DECOMPRESSED)
        
        # Check invariants after decompression
        self.assertIn('dy', self.adf.df.columns)  # Physical column
        self.assertNotIn('dy', self.adf.aliases)   # No alias
        self.assertNotIn('dy_c', self.adf.df.columns)  # Compressed removed
        
        # Step 3: Recompress using stored schema
        self.adf.compress_columns(columns=['dy'])
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        
        # Check invariants after recompression
        self.assertIn('dy_c', self.adf.df.columns)
        self.assertIn('dy', self.adf.aliases)
        self.assertNotIn('dy', self.adf.df.columns)
        
        # Verify data integrity
        self.adf.materialize_alias('dy')
        np.testing.assert_allclose(
            self.adf.df['dy'].values,
            self.original_dy,
            rtol=0.01, atol=0.05
        )

    def test_decompress_with_keep_schema_false(self):
        """Test COMPRESSED → None transition (remove all metadata)"""
        from dfextensions.AliasDataFrame import CompressionState
        
        self.adf.compress_columns({'dy': self.spec['dy']})
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        
        self.adf.decompress_columns(['dy'], keep_schema=False)
        
        # Check state removed
        self.assertIsNone(self.adf.get_compression_state('dy'))
        self.assertNotIn('dy', self.adf.compression_info)
        
        # Check physical column exists
        self.assertIn('dy', self.adf.df.columns)
        self.assertNotIn('dy', self.adf.aliases)

    def test_error_on_double_compression(self):
        """Test that re-compressing COMPRESSED state raises error"""
        self.adf.compress_columns({'dy': self.spec['dy']})
        
        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns({'dy': self.spec['dy']})
        
        self.assertIn('already compressed', str(cm.exception))
        # Check that it suggests decompression
        self.assertIn('decompress', str(cm.exception).lower())

    def test_collision_same_schema_recompression(self):
        """Test recompression with matching schema is allowed"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Compress, decompress, recompress
        self.adf.compress_columns({'dy': self.spec['dy']})
        self.adf.decompress_columns(['dy'], keep_schema=True, keep_compressed=False)
        
        # This should work - reuses dy_c name from schema
        self.adf.compress_columns(columns=['dy'])
        
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        self.assertIn('dy_c', self.adf.df.columns)

    def test_collision_foreign_column(self):
        """Test collision with unrelated column raises error"""
        # Create conflicting column
        self.adf.df['dy_c'] = np.zeros(len(self.adf.df))
        
        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns({'dy': self.spec['dy']})
        
        self.assertIn('already exists', str(cm.exception))
        self.assertIn('dy_c', str(cm.exception))

    def test_collision_other_schema(self):
        """Test collision with another column's compressed_col raises error"""
        # First create an unrelated column called 'dy_c'
        self.adf.df['dy_c'] = np.ones(len(self.adf.df))
        
        # Now try to compress dy, which would want to create dy_c
        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns({'dy': self.spec['dy']})
        
        # Check error message mentions the conflict
        self.assertIn('already exists', str(cm.exception).lower())
        self.assertIn('dy_c', str(cm.exception))

    def test_compress_all_schema_only_columns(self):
        """Test compress_columns() with no args compresses all SCHEMA_ONLY"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Define schemas
        self.adf.define_compression_schema(self.spec)
        
        # Compress all at once (no args)
        self.adf.compress_columns()
        
        # Check both compressed
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        self.assertEqual(self.adf.get_compression_state('dz'), CompressionState.COMPRESSED)

    def test_is_compressed_helper(self):
        """Test is_compressed() helper method"""
        self.assertFalse(self.adf.is_compressed('dy'))
        
        self.adf.compress_columns({'dy': self.spec['dy']})
        self.assertTrue(self.adf.is_compressed('dy'))
        
        self.adf.decompress_columns(['dy'], keep_schema=True)
        self.assertFalse(self.adf.is_compressed('dy'))

    def test_get_compression_info_excludes_meta(self):
        """Test get_compression_info() filters __meta__"""
        self.adf.compress_columns({'dy': self.spec['dy']})
        
        # Single column - should work
        info = self.adf.get_compression_info('dy')
        self.assertIsInstance(info, dict)
        self.assertIn('state', info)
        
        # All columns - should exclude __meta__
        df_info = self.adf.get_compression_info()
        self.assertNotIn('__meta__', df_info.index)
        self.assertIn('dy', df_info.index)

    def test_precision_measurement_with_state(self):
        """Test precision measurement works with new state system"""
        self.adf.compress_columns({'dy': self.spec['dy']}, measure_precision=True)
        
        info = self.adf.compression_info['dy']
        self.assertIn('precision', info)
        self.assertIn('rmse', info['precision'])
        self.assertGreater(info['precision']['rmse'], 0)

    def test_schema_from_info_helper(self):
        """Test _schema_from_info() reconstructs spec correctly"""
        self.adf.define_compression_schema({'dy': self.spec['dy']})
        
        reconstructed = self.adf._schema_from_info('dy')
        
        self.assertEqual(reconstructed['compress'], self.spec['dy']['compress'])
        self.assertEqual(reconstructed['decompress'], self.spec['dy']['decompress'])
        self.assertEqual(reconstructed['compressed_dtype'], self.spec['dy']['compressed_dtype'])

    def test_invalid_state_transition_schema_only_to_decompress(self):
        """Test that SCHEMA_ONLY → DECOMPRESS is a no-op"""
        from dfextensions.AliasDataFrame import CompressionState
        
        self.adf.define_compression_schema({'dy': self.spec['dy']})
        
        # Try to decompress SCHEMA_ONLY column (should be no-op)
        self.adf.decompress_columns(['dy'])
        
        # State should still be SCHEMA_ONLY
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.SCHEMA_ONLY)

    def test_backward_compatibility_old_files(self):
        """Test that old files without __meta__ are handled"""
        # Simulate old file by removing __meta__
        if "__meta__" in self.adf.compression_info:
            del self.adf.compression_info["__meta__"]
        
        # get_compression_info should still work
        df_info = self.adf.get_compression_info()
        self.assertIsInstance(df_info, pd.DataFrame)

    def test_state_invariants_after_compress(self):
        """Test state invariants after compression"""
        from dfextensions.AliasDataFrame import CompressionState
        
        self.adf.compress_columns({'dy': self.spec['dy']})
        
        # Invariant checks
        state = self.adf.get_compression_state('dy')
        self.assertEqual(state, CompressionState.COMPRESSED)
        
        # Physical compressed column exists
        self.assertIn('dy_c', self.adf.df.columns)
        
        # Original is alias, not physical
        self.assertNotIn('dy', self.adf.df.columns)
        self.assertIn('dy', self.adf.aliases)
        
        # Metadata consistent
        info = self.adf.compression_info['dy']
        self.assertEqual(info['state'], CompressionState.COMPRESSED)
        self.assertEqual(info['compressed_col'], 'dy_c')

    def test_state_invariants_after_decompress(self):
        """Test state invariants after decompression"""
        from dfextensions.AliasDataFrame import CompressionState
        
        self.adf.compress_columns({'dy': self.spec['dy']})
        self.adf.decompress_columns(['dy'], keep_schema=True, keep_compressed=True)
        
        # Invariant checks
        state = self.adf.get_compression_state('dy')
        self.assertEqual(state, CompressionState.DECOMPRESSED)
        
        # Decompressed column is physical
        self.assertIn('dy', self.adf.df.columns)
        
        # Not an alias
        self.assertNotIn('dy', self.adf.aliases)
        
        # Compressed column still exists (keep_compressed=True)
        self.assertIn('dy_c', self.adf.df.columns)
        
        # Metadata consistent
        info = self.adf.compression_info['dy']
        self.assertEqual(info['state'], CompressionState.DECOMPRESSED)

    def test_selective_registration_from_spec(self):
        """Test compress_columns(spec, columns=[subset]) only registers subset"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Compress only dy from full spec
        self.adf.compress_columns(self.spec, columns=['dy'])
        
        # Check ONLY dy registered and compressed
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        self.assertIsNone(self.adf.get_compression_state('dz'))  # NOT registered
        
        # Check metadata
        self.assertIn('dy', self.adf.compression_info)
        self.assertNotIn('dz', self.adf.compression_info)
        
        # Check physical columns
        self.assertIn('dy_c', self.adf.df.columns)
        self.assertNotIn('dz_c', self.adf.df.columns)

    def test_multiple_selective_calls(self):
        """Test Pattern 2: Multiple compress_columns calls with subsets"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # First call: compress dy
        self.adf.compress_columns(self.spec, columns=['dy'])
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        
        # Second call: compress dz (should work, not error)
        self.adf.compress_columns(self.spec, columns=['dz'])
        self.assertEqual(self.adf.get_compression_state('dz'), CompressionState.COMPRESSED)
        
        # Both should be compressed now
        self.assertTrue(self.adf.is_compressed('dy'))
        self.assertTrue(self.adf.is_compressed('dz'))
        
        # Both have separate metadata
        self.assertIn('dy', self.adf.compression_info)
        self.assertIn('dz', self.adf.compression_info)

    def test_selective_mode_skips_same_schema_compressed(self):
        """Test that re-compressing with SAME schema is silently skipped (idempotent)"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Compress
        self.adf.compress_columns(self.spec, columns=['dy'])
        dy_c_before = self.adf.df['dy_c'].copy()
        
        # Try to compress again with same schema (should skip)
        self.adf.compress_columns(self.spec, columns=['dy'])
        
        # Should still be compressed, data unchanged
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        np.testing.assert_array_equal(self.adf.df['dy_c'], dy_c_before)

    def test_selective_mode_errors_on_schema_change_when_compressed(self):
        """Test error when trying to change schema of COMPRESSED column"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Compress with original schema
        self.adf.compress_columns(self.spec, columns=['dy'])
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        
        # Try to compress with different schema
        new_spec = {
            'dy': {
                'compress': 'round(dy*1000)',  # Different transform
                'decompress': 'dy_c/1000.',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float32
            }
        }
        
        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns(new_spec, columns=['dy'])
        
        self.assertIn('already compressed', str(cm.exception).lower())
        self.assertIn('different schema', str(cm.exception).lower())
        self.assertIn('decompress first', str(cm.exception).lower())

    def test_selective_mode_validates_column_exists(self):
        """Test that selective mode validates column exists in DataFrame"""
        spec = {
            'nonexistent': {
                'compress': 'round(nonexistent*10)',
                'decompress': 'nonexistent_c/10.',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float32
            }
        }
        
        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns(spec, columns=['nonexistent'])
        
        self.assertIn('not found in DataFrame', str(cm.exception))
        self.assertIn('nonexistent', str(cm.exception))

    def test_selective_mode_validates_columns_in_spec(self):
        """Test that selective mode validates requested columns are in spec"""
        with self.assertRaises(ValueError) as cm:
            self.adf.compress_columns(self.spec, columns=['dy', 'nonexistent'])
        
        self.assertIn('not found in compression_spec', str(cm.exception))
        self.assertIn('nonexistent', str(cm.exception))

    def test_selective_mode_updates_schema_for_schema_only(self):
        """Test that Pattern 2 can update schema for SCHEMA_ONLY columns"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Step 1: Register initial schema (Pattern 1)
        old_spec = {
            'dy': {
                'compress': 'round(dy*10)',
                'decompress': 'dy_c/10.',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float32
            }
        }
        self.adf.define_compression_schema(old_spec)
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.SCHEMA_ONLY)
        
        # Step 2: Update schema using Pattern 2
        new_spec = {
            'dy': {
                'compress': 'round(asinh(dy)*40)',
                'decompress': 'sinh(dy_c/40.)',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float16
            }
        }
        self.adf.compress_columns(new_spec, columns=['dy'])
        
        # Check schema was updated and compressed
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        info = self.adf.compression_info['dy']
        self.assertEqual(info['compress_expr'], 'round(asinh(dy)*40)')
        self.assertEqual(info['decompressed_dtype'], 'float16')

    def test_real_world_incremental_compression_pattern2(self):
        """Test Scenario 3 from spec: incremental compression using Pattern 2"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Add tgSlp to test data
        self.adf.df['tgSlp'] = np.random.uniform(-0.5, 0.5, len(self.adf.df))
        
        # Step 1: Compress subset for initial analysis (Pattern 2)
        self.adf.compress_columns(self.spec, columns=['dy', 'dz'])
        
        self.assertTrue(self.adf.is_compressed('dy'))
        self.assertTrue(self.adf.is_compressed('dz'))
        self.assertIsNone(self.adf.get_compression_state('tgSlp'))
        
        # Step 2: Later compress additional column (Pattern 2)
        tgSlp_spec = {
            'tgSlp': {
                'compress': 'round(tgSlp*1000)',
                'decompress': 'tgSlp_c/1000.',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float32
            }
        }
        self.adf.compress_columns(tgSlp_spec, columns=['tgSlp'])
        
        # All three compressed now
        self.assertTrue(self.adf.is_compressed('dy'))
        self.assertTrue(self.adf.is_compressed('dz'))
        self.assertTrue(self.adf.is_compressed('tgSlp'))
        
        # Verify data integrity
        self.assertIn('dy_c', self.adf.df.columns)
        self.assertIn('dz_c', self.adf.df.columns)
        self.assertIn('tgSlp_c', self.adf.df.columns)

    def test_pattern1_pattern2_mixing(self):
        """Test mixing Pattern 1 (schema-first) and Pattern 2 (selective)"""
        from dfextensions.AliasDataFrame import CompressionState
        
        # Pattern 1: Define full schema
        self.adf.define_compression_schema(self.spec)
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.SCHEMA_ONLY)
        self.assertEqual(self.adf.get_compression_state('dz'), CompressionState.SCHEMA_ONLY)
        
        # Pattern 2: Compress only dy with potentially updated schema
        updated_spec = {
            'dy': {
                'compress': 'round(dy*100)',  # Different from original
                'decompress': 'dy_c/100.',
                'compressed_dtype': np.int16,
                'decompressed_dtype': np.float32
            }
        }
        self.adf.compress_columns(updated_spec, columns=['dy'])
        
        # dy should be compressed with new schema
        self.assertEqual(self.adf.get_compression_state('dy'), CompressionState.COMPRESSED)
        self.assertEqual(self.adf.compression_info['dy']['compress_expr'], 'round(dy*100)')
        
        # dz should still be SCHEMA_ONLY with original schema
        self.assertEqual(self.adf.get_compression_state('dz'), CompressionState.SCHEMA_ONLY)
        self.assertEqual(self.adf.compression_info['dz']['compress_expr'], self.spec['dz']['compress'])


if __name__ == "__main__":
    unittest.main()