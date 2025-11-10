# Changelog

All notable changes to AliasDataFrame will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

## [1.1.0] - 2025-01-09

### Added
- **Selective compression mode (Pattern 2)** - Compress specific columns from a larger schema
  - New API: `compress_columns(spec, columns=['dy', 'dz'])`
  - Enables incremental compression workflows
  - Only specified columns are registered and compressed
- **Idempotent compression** - Re-compressing with same schema is safe (no-op)
  - Prevents errors in automation and scripting
  - Useful for incremental data collection
- **Schema updates** - Update compression schema for specific columns
  - Works for SCHEMA_ONLY and DECOMPRESSED states
  - Errors on COMPRESSED state (must decompress first)
- **Enhanced validation** - Column existence checked before compression
  - Clear error messages with available columns listed
  - Validates columns present in compression spec
- **Pattern mixing support** - Combine Pattern 1 and Pattern 2
  - Pattern 1: Schema-first (define all, compress incrementally)
  - Pattern 2: On-demand (compress as needed)
  - Column-local schema semantics (schemas can diverge)

### Changed
- `compress_columns()` now supports 5 modes (previously 3):
  1. Schema-only definition: `compress_columns(spec, columns=[])`
  2. Apply existing schema: `compress_columns(columns=['dy'])`
  3. Compress all in spec: `compress_columns(spec)`
  4. **Selective compression (NEW)**: `compress_columns(spec, columns=['dy', 'dz'])`
  5. Auto-compress eligible: `compress_columns()`
- Improved error messages for compression failures
  - Specific guidance for state transition errors
  - Clear suggestions for resolution
- Updated documentation with comprehensive examples

### Fixed
- None (fully backward compatible)

### Performance
- Negligible overhead from new validation (~O(1) dict lookups)
- No regression in existing compression performance
- Validated with 9.6M row TPC residual dataset

### Documentation
- Added `docs/COMPRESSION_GUIDE.md` with comprehensive usage guide
- Updated method docstrings with Pattern 2 examples
- Added state machine documentation
- Added troubleshooting section

### Testing
- Added 10 comprehensive tests for selective compression mode
- All 61 tests passing
- Test coverage: ~95%
- No regression in existing functionality

### Use Case
Enables incremental compression for TPC residual analysis:
- 9.6M cluster-track residuals
- 8 compressed columns
- 508 MB → 330 MB (35% file size reduction)
- Sub-micrometer precision maintained
- Compress columns incrementally as data is collected

---

## [1.0.0] - 2024-XX-XX

### Added
- Initial compression/decompression implementation
- State machine with 3 states (COMPRESSED, DECOMPRESSED, SCHEMA_ONLY)
- Bidirectional compression with mathematical transforms
- Lazy decompression via aliases
- Precision measurement (RMSE, max error, mean error)
- Schema persistence across save/load cycles
- Forward declaration support ("zero pointer" pattern)
- Collision detection for compressed column names
- ROOT TTree export with compression aliases
- Comprehensive test suite

### Features
- Compress columns using expression-based transforms
- Decompress columns with optional schema retention
- Measure compression quality metrics
- Save/load compressed DataFrames
- Export to ROOT with decompression aliases
- Recompress after modification

### Documentation
- Complete API documentation
- Usage examples
- State machine explanation

---

## Version Numbering

This project uses [Semantic Versioning](https://semver.org/):
- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality (backward compatible)
- **PATCH** version for bug fixes (backward compatible)

---

## Contributing

When adding entries to this changelog:
1. Add new changes to the [Unreleased] section
2. Move to versioned section on release
3. Follow the format: Added / Changed / Deprecated / Removed / Fixed / Security
4. Include use cases and examples for major changes
5. Note backward compatibility status

---

**Last Updated:** 2025-01-09
