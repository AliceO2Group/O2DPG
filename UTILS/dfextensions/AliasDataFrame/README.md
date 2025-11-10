# AliasDataFrame

Lazy-evaluated DataFrame with bidirectional compression support for physics data analysis.

## Features
- Lazy evaluation via aliases
- Bidirectional compression with state management
- Sub-micrometer precision for spatial data
- ROOT TTree export/import support
- Incremental compression workflows

## Quick Start
```python
from dfextensions import AliasDataFrame
import numpy as np

# Compress column
adf = AliasDataFrame(df)
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
- [Compression Guide](docs/COMPRESSION_GUIDE.md)
- [Changelog](docs/CHANGELOG.md)

## Testing
```bash
pytest AliasDataFrameTest.py -v
# Expected: 61 tests passing
```

## Version
1.1.0 - Selective Compression Mode