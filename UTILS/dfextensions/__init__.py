# __init__.py


from .FormulaLinearModel import FormulaLinearModel
from .DataFrameUtils import *  # if it provides general helper functions
from .groupby_regression import *  # or other relevant functions

__all__ = [
    "AliasDataFrame",
    "FormulaLinearModel",
    "GroupByRegressor"
]


try:
    from .AliasDataFrame import AliasDataFrame
    __all__.append("AliasDataFrame")
except ImportError:
    pass
