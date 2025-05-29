"""timeseries_diff.py
import sys,os; sys.path.insert(1, os.environ[f"O2DPG"]+"/UTILS/dfextensions");
from  AliasDataFrame import *
Utility helpers extension of the pandas DataFrame to support on-demand computed columns (aliases)
"""

import pandas as pd
import numpy as np
import json
import os
import uproot

class AliasDataFrame:
    """
    A wrapper for pandas DataFrame that supports on-demand computed columns (aliases)
    with dependency tracking and persistence.
    Example usage:
    >>> import pandas as pd
    >>> df = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})
    >>> adf = AliasDataFrame(df)
    >>> adf.add_alias("z", "x + y")
    >>> adf.add_alias("w", "z * 2")
    >>> adf.materialize_all()
    >>> print(adf.df)
    You can also save and load the dataframe along with aliases:
    >>> adf.save("mydata")
    >>> adf2 = AliasDataFrame.load("mydata")
    >>> adf2.describe_aliases()
    """

    def __init__(self, df):
        self.df = df
        self.aliases = {}

    def add_alias(self, name, expression):
        self.aliases[name] = expression

    def _resolve_dependencies(self):
        from collections import defaultdict

        dependencies = defaultdict(set)
        for name, expr in self.aliases.items():
            tokens = expr.replace('(', ' ').replace(')', ' ').replace('*', ' ').replace('+', ' ').replace('-', ' ').replace('/', ' ').split()
            for token in tokens:
                if token in self.aliases:
                    dependencies[name].add(token)
        return dependencies

    def _topological_sort(self):
        from collections import defaultdict, deque

        dependencies = self._resolve_dependencies()
        reverse_deps = defaultdict(set)
        indegree = defaultdict(int)

        for alias, deps in dependencies.items():
            indegree[alias] = len(deps)
            for dep in deps:
                reverse_deps[dep].add(alias)

        queue = deque([alias for alias in self.aliases if indegree[alias] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in reverse_deps[node]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self.aliases):
            raise ValueError("Cycle detected in alias dependencies")

        return result

    def validate_aliases(self):
        broken = []
        for name, expr in self.aliases.items():
            try:
                eval(expr, {}, self.df)
            except Exception:
                broken.append(name)
        return broken

    def describe_aliases(self):
        print("Aliases:")
        for name, expr in self.aliases.items():
            print(f"  {name}: {expr}")

        broken = self.validate_aliases()
        if broken:
            print("\nBroken Aliases:")
            for name in broken:
                print(f"  {name}")

        print("\nDependencies:")
        deps = self._resolve_dependencies()
        for k, v in deps.items():
            print(f"  {k}: {sorted(v)}")

    def materialize_alias0(self, name):
        if name in self.aliases:
            local_env = {col: self.df[col] for col in self.df.columns}
            local_env.update({k: self.df[k] for k in self.aliases if k in self.df})
            self.df[name] = eval(self.aliases[name], {}, local_env)
    def materialize_alias(self, name, cleanTemporary=False):
        if name not in self.aliases:
            return
        to_materialize = []
        visited = set()
        def visit(n):
            if n in visited:
                return
            visited.add(n)
            if n in self.aliases:
                expr = self.aliases[n]
                tokens = expr.replace('(', ' ').replace(')', ' ').replace('*', ' ').replace('+', ' ').replace('-', ' ').replace('/', ' ').split()
                for token in tokens:
                    visit(token)
                to_materialize.append(n)

        visit(name)

        # Track which ones were newly created
        original_columns = set(self.df.columns)

        for alias in to_materialize:
            local_env = {col: self.df[col] for col in self.df.columns}
            local_env.update({k: self.df[k] for k in self.aliases if k in self.df})
            try:
                self.df[alias] = eval(self.aliases[alias], {}, local_env)
            except Exception as e:
                print(f"Failed to materialize {alias}: {e}")

        if cleanTemporary:
            for alias in to_materialize:
                if alias != name and alias not in original_columns:
                    self.df.drop(columns=[alias], inplace=True)


    def materialize_all(self):
        order = self._topological_sort()
        for name in order:
            try:
                local_env = {col: self.df[col] for col in self.df.columns}
                local_env.update({k: self.df[k] for k in self.df.columns if k in self.aliases})
                self.df[name] = eval(self.aliases[name], {}, local_env)
            except Exception as e:
                print(f"Failed to materialize {name}: {e}")

    def save(self, path_prefix):
        self.df.to_parquet(f"{path_prefix}.parquet", compression="zstd")
        with open(f"{path_prefix}.aliases.json", "w") as f:
            json.dump(self.aliases, f, indent=2)

    @staticmethod
    def load(path_prefix):
        df = pd.read_parquet(f"{path_prefix}.parquet")
        with open(f"{path_prefix}.aliases.json") as f:
            aliases = json.load(f)
        adf = AliasDataFrame(df)
        adf.aliases = aliases
        return adf

    def export_tree(self, filename, treename="tree", dropAliasColumns=True):
        if dropAliasColumns:
            export_cols = [col for col in self.df.columns if col not in self.aliases]
        else:
            export_cols = list(self.df.columns)
        # Convert float16 columns to float32 for ROOT compatibility
        dtype_casts = {col: np.float32 for col in export_cols if self.df[col].dtype == np.float16}
        export_df = self.df[export_cols].astype(dtype_casts)

        with uproot.recreate(filename) as f:
            f[treename] = export_df

        import ROOT
        f = ROOT.TFile.Open(filename, "UPDATE")
        tree = f.Get(treename)
        for alias, expr in self.aliases.items():
            tree.SetAlias(alias, expr)
        tree.Write("", ROOT.TObject.kOverwrite)
        f.Close()

    def read_tree(self, filename, treename="tree"):
        with uproot.open(filename) as f:
            df = f[treename].arrays(library="pd")
        adf = AliasDataFrame(df)
        f = ROOT.TFile.Open(filename, "UPDATE")
        try:
            tree = f.Get(treename)
            if not tree:
                raise ValueError(f"Tree '{treename}' not found in file '{filename}'")
            for alias in tree.GetListOfAliases():
                adf.aliases[alias.GetName()] = alias.GetTitle()
        finally:
            f.Close()
        return adf
