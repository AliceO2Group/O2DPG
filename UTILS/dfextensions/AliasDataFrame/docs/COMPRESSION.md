# AliasDataFrame Compression Guide

## Overview

AliasDataFrame supports bidirectional column compression to reduce memory usage and file size while maintaining data accessibility through lazy decompression.

**Key Benefits:**
- 35-40% file size reduction
- Reversible compression (no data structure loss)
- Sub-micrometer precision for spatial coordinates
- Lazy decompression via aliases

---

## Quick Start

### Basic Compression

```python
from dfextensions.AliasDataFrame import AliasDataFrame
import numpy as np

# Define compression schema
spec = {
    'dy': {
        'compress': 'round(asinh(dy)*40)',      # Transform for compression
        'decompress': 'sinh(dy_c/40.)',         # Transform for decompression
        'compressed_dtype': np.int16,           # Storage dtype
        'decompressed_dtype': np.float16        # Reconstructed dtype
    }
}

# Compress column
adf = AliasDataFrame(df)
adf.compress_columns(spec)

# Access decompressed values (via alias)
dy_values = adf.dy  # Automatically decompressed

# Save (aliases become ROOT TTree aliases)
adf.export_tree("output.root", "tree")
```

---

## Compression Modes

### Mode 1: Define Schema First (Pattern 1)
```python
# Step 1: Define schema upfront
adf.define_compression_schema(spec)

# Step 2: Compress when data ready
adf.compress_columns(columns=['dy', 'dz'])
```

**Use Case:** Known schema, compress incrementally as data arrives

---

### Mode 2: On-Demand Compression (Pattern 2)
```python
# Compress only specific columns
adf.compress_columns(spec, columns=['dy', 'dz'])  # Only dy, dz

# Later, add more columns
adf.compress_columns(spec, columns=['tgSlp'])     # Add tgSlp
```

**Use Case:** Incremental development, selective compression

---

### Mode 3: Compress All
```python
# Compress all columns in spec
adf.compress_columns(spec)
```

**Use Case:** Compress entire dataset at once

---

## State Management

### Compression States

Each column has one of these states:
- **COMPRESSED** - Column stored compressed, accessible via alias
- **DECOMPRESSED** - Column materialized, schema retained
- **SCHEMA_ONLY** - Schema defined, not yet compressed

### State Transitions

```
None ──────────────► COMPRESSED
  │                      │
  └──► SCHEMA_ONLY ──────┤
                         │
                         ▼
                   DECOMPRESSED
                         │
                         └──────► COMPRESSED (recompression)
```

### Checking State

```python
# Check if column is compressed
if adf.is_compressed('dy'):
    print("dy is compressed")

# Get detailed state
state = adf.get_compression_state('dy')  # Returns 'compressed', 'decompressed', 'schema_only', or None

# View all compression info
info = adf.get_compression_info()
print(info)
```

---

## Decompression

### Basic Decompression

```python
# Decompress columns (keeps schema for recompression)
adf.decompress_columns(['dy', 'dz'])

# Remove schema entirely
adf.decompress_columns(['dy'], keep_schema=False, keep_compressed=False)
```

### Recompression

```python
# After decompression, can recompress with stored schema
adf.decompress_columns(['dy'])
# ... modify data ...
adf.compress_columns(columns=['dy'])  # Uses stored schema
```

---

## Precision Measurement

```python
# Measure compression quality
adf.compress_columns(spec, measure_precision=True)

# View precision info
info = adf.get_compression_info()
print(f"RMSE: {info['dy']['precision']['rmse']}")
print(f"Max error: {info['dy']['precision']['max_error']}")
```

**Metrics provided:**
- RMSE (root mean squared error)
- Max absolute error
- Mean error
- Sample counts (total vs finite)

---

## Common Patterns

### Pattern: Incremental Data Collection

```python
# Day 1: Define schema for all columns
adf.define_compression_schema(full_spec)

# Day 2: Compress available columns
adf.compress_columns(columns=['dy', 'dz'])

# Day 3: Compress more as data arrives
adf.compress_columns(columns=['y', 'z', 'tgSlp'])
```

### Pattern: Schema Refinement

```python
# V1: Initial compression
adf.compress_columns(v1_spec, columns=['dy'])

# Decompress to refine
adf.decompress_columns(['dy'], keep_schema=False)

# V2: Improved compression
adf.compress_columns(v2_spec, columns=['dy'])
```

### Pattern: Selective Processing

```python
# Compress only columns needed for analysis
adf.compress_columns(spec, columns=['dy', 'dz', 'mP3'])

# Other columns remain uncompressed
# (no compression overhead for unused data)
```

---

## Best Practices

### ✅ DO

1. **Define schema once** - Centralize compression definitions
2. **Measure precision** - Verify acceptable error for your use case
3. **Use asinh for residuals** - Handles outliers well
4. **Keep schema** - Enable recompression after modifications
5. **Test round-trip** - Verify compress → decompress → recompress

### ❌ DON'T

1. **Don't compress categorical data** - Use original values
2. **Don't change dtype mid-workflow** - Stick to schema
3. **Don't compress derived columns** - Keep computation in aliases
4. **Don't ignore precision metrics** - Verify acceptable error
5. **Don't nest compression** - One level only

---

## Real-World Example: TPC Residuals

```python
# Define compression schema (once, centrally)
dfResCompresion = {
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
    'y': {
        'compress': 'round(y*(0x7fff/50))',
        'decompress': 'y_c*(50/0x7fff)',
        'compressed_dtype': np.int16,
        'decompressed_dtype': np.float32
    },
    'z': {
        'compress': 'round(z*(0x7fff/300))',
        'decompress': 'z_c*(300/0x7fff)',
        'compressed_dtype': np.int16,
        'decompressed_dtype': np.float32
    },
    # ... more columns
}

# Compress dataset
adf = AliasDataFrame(df_residuals)
adf.compress_columns(dfResCompresion, measure_precision=True)

# Export (508 MB → 330 MB, 35% reduction)
adf.export_tree("residuals_compressed.root", "tree")

# Later: Load and use (aliases decompress automatically)
adf_loaded = AliasDataFrame.import_tree("residuals_compressed.root", "tree")
dy_values = adf_loaded.dy  # Decompressed on-the-fly
```

**Results:**
- File size: 508 MB → 330 MB (35% reduction)
- Memory: 1579 MB → 1471 MB (7% reduction)
- Precision: RMSE < 0.018 mm for residuals
- Processing: <30 seconds for 9.6M rows

---

## Troubleshooting

### Error: "Column already compressed"

```python
# Problem: Trying to compress COMPRESSED column
# Solution: Decompress first or use selective mode (idempotent)
adf.decompress_columns(['dy'])
adf.compress_columns(spec, columns=['dy'])
```

### Error: "Column not found in DataFrame"

```python
# Problem: Column doesn't exist yet
# Solution: Define schema, compress later when data exists
adf.define_compression_schema(spec)  # Schema only
# ... later when data exists ...
adf.compress_columns(columns=['dy'])
```

### Error: "Different schema"

```python
# Problem: Trying to change schema of COMPRESSED column
# Solution: Decompress first
adf.decompress_columns(['dy'], keep_schema=False)
adf.compress_columns(new_spec, columns=['dy'])
```

---

## API Reference

### Compression Methods

```python
# Compress columns
adf.compress_columns(compression_spec=None, columns=None, 
                     suffix='_c', drop_original=True, 
                     measure_precision=False)

# Decompress columns
adf.decompress_columns(columns=None, keep_compressed=True, 
                       keep_schema=True)

# Define schema without compressing
adf.define_compression_schema(compression_spec, suffix='_c')
```

### Introspection Methods

```python
# Check if compressed
is_compressed = adf.is_compressed('column_name')

# Get state
state = adf.get_compression_state('column_name')

# Get all compression info
info = adf.get_compression_info()  # Returns DataFrame

# Get single column info
info = adf.get_compression_info('column_name')  # Returns dict
```

---

## Version History

### v1.0 (Current)
- Basic compression/decompression
- State machine with 3 states
- Precision measurement
- Schema persistence
- Selective compression (Pattern 2)
- Idempotent compression

---

## See Also

- **API_REFERENCE.md** - Complete API documentation
- **EXAMPLES.md** - More code examples
- **CHANGELOG.md** - Detailed version history
