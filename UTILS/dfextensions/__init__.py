"""
dfextensions - DataFrame extensions and utilities.

Main packages:
- AliasDataFrame: Lazy-evaluated DataFrame with compression support
- groupby_regression: Grouped regression utilities
- quantile_fit_nd: N-dimensional quantile fitting
- dataframe_utils: Plotting and statistics utilities
- formula_utils: Formula-based modeling and code export
"""

# Main packages
from .AliasDataFrame import AliasDataFrame, CompressionState
from .groupby_regression import *  # Includes GroupByRegressor

# Utilities (moved to subdirectories)
from .dataframe_utils import *
from .formula_utils import FormulaLinearModel

__all__ = [
    "AliasDataFrame",
    "CompressionState",
    "FormulaLinearModel",
    "GroupByRegressor",  # from groupby_regression
]

__version__ = '1.1.0'
