"""
AliasDataFrame - Lazy-evaluated DataFrame with compression support.

Main exports:
- AliasDataFrame: Main class
- CompressionState: State class for compression tracking
"""

from .AliasDataFrame import AliasDataFrame, CompressionState

__all__ = ['AliasDataFrame', 'CompressionState']
__version__ = '1.1.0'
