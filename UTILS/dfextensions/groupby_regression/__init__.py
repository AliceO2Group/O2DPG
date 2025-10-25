"""
GroupBy Regression Package

Provides two implementations:
- Robust (groupby_regression.py): Production-proven, full features, custom fitters
- Optimized (groupby_regression_optimized.py): Speed-optimized (v2/v3/v4)

Quick Start:
    # Robust implementation (battle-tested)
    from dfextensions.groupby_regression import GroupByRegressor
    _, dfGB = GroupByRegressor.make_parallel_fit(...)
    
    # Fast implementation (17-200× faster)
    from dfextensions.groupby_regression import make_parallel_fit_v4
    _, dfGB = make_parallel_fit_v4(...)

See docs/README.md for choosing between implementations.
"""

# Import main classes from modules (will add after files are moved)
# from .groupby_regression import GroupByRegressor
# from .groupby_regression_optimized import (
#     make_parallel_fit_v2,
#     make_parallel_fit_v3,
#     make_parallel_fit_v4,
#     GroupByRegressorOptimized,
# )

# Version info
__version__ = '2.0.0'
__author__ = 'Marian Ivanov'

# Expose at package level (will uncomment after files are moved)
# __all__ = [
#     'GroupByRegressor',
#     'make_parallel_fit_v2',
#     'make_parallel_fit_v3',
#     'make_parallel_fit_v4',
#     'GroupByRegressorOptimized',
# ]
