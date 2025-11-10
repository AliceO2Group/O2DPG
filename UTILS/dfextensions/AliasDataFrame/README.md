# AliasDataFrame

Lazy-evaluated DataFrame with hierarchical subframes and bidirectional compression for physics data analysis.

## Features

### Core Features
- ✅ **Lazy evaluation** - Named expression-based columns (aliases)
- ✅ **Hierarchical subframes** - Multi-table joins (clusters→tracks→collisions)
- ✅ **Dependency tracking** - Automatic resolution with cycle detection
- ✅ **Compression** - Bidirectional column compression with state management
- ✅ **Persistence** - Save/load to Parquet and ROOT TTree

### Compression Features (v1.1.0)
- ✅ Selective compression (compress only what you need)
- ✅ Idempotent operations (safe to call multiple times)
- ✅ Schema persistence (survives decompress/compress cycles)
- ✅ Sub-micrometer precision for spatial data
- ✅ 35-40% file size reduction

## Quick Start

### Aliases
```python
from dfextensions import AliasDataFrame

adf = AliasDataFrame(df)
adf.add_alias("pt", "sqrt(px**2 + py**2)")
adf.materialize_alias("pt")
```

### Subframes
```python
adf_clusters.register_subframe("track", adf_tracks, index_columns="track_index")
adf_clusters.add_alias("dX", "mX - track.mX")
```

### Compression
```python
spec = {
'dy': {
'compress': 'round(asinh(dy)*40)',
'decompress': 'sinh(dy_c/40.)',
'compressed_dtype': np.int16,
'decompressed_dtype': np.float16
}
}
adf.compress_columns(spec)
```

## Documentation

- **[User Guide](docs/USER_GUIDE.md)** - Complete guide to aliases and subframes
- **[Compression Guide](docs/COMPRESSION.md)** - Compression features and workflows
- **[Changelog](docs/CHANGELOG.md)** - Version history

## Testing

```bash
pytest AliasDataFrameTest.py -v
# Expected: 61 tests passing
```

## Version

1.1.0 - Selective Compression Mode

## Author

Marian Ivanov  
MIT License