# __init__.py


from .FormulaLinearModel import FormulaLinearModel
from .DataFrameUtils import *  # if it provides general helper functions
from .groupby_regression import *  # or other relevant functions
from .AliasDataFrame import AliasDataFrame, CompressionState

__all__ = [
    "AliasDataFrame",
    "FormulaLinearModel",
    "GroupByRegressor"
]

