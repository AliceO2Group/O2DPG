""" AliasDataframe.py
import sys,os; sys.path.insert(1, os.environ[f"O2DPG"]+"/UTILS/dfextensions");
from  AliasDataFrame import *
Utility helpers extension of the pandas DataFrame to support on-demand computed columns (aliases)
"""
import pandas as pd
import numpy as np
import json
import uproot
import ROOT     # type: ignore
import matplotlib.pyplot as plt
import networkx as nx

class AliasDataFrame:
    """
    A wrapper for pandas DataFrame that supports on-demand computed columns (aliases)
    with dependency tracking and persistence.
    """

    def __init__(self, df):
        self.df = df
        self.aliases = {}
        self.alias_dtypes = {}  # Optional output types for each alias
        self.constant_aliases = set()  # Optional set of constants that should not be materialized

    def add_alias(self, name, expression, dtype=None, is_constant=False):
        try:
            dummy_env = {k: 1 for k in list(self.df.columns) + list(self.aliases.keys())}
            dummy_env.update(self._default_functions())
            eval(expression, self._default_functions(), dummy_env)
        except Exception as e:
            print(f"[Alias add warning] '{name}' may be invalid: {e}")
        self.aliases[name] = expression
        if dtype is not None:
            self.alias_dtypes[name] = dtype
        if is_constant:
            if name in self._resolve_dependencies() and self._resolve_dependencies()[name]:
                print(f"[Alias warning] '{name}' marked as constant but has dependencies.")
            self.constant_aliases.add(name)

    def _default_functions(self):
        import math
        env = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        env.update({k: getattr(np, k) for k in dir(np) if not k.startswith("_")})
        env["np"] = np
        return env

    def _resolve_dependencies(self):
        from collections import defaultdict

        dependencies = defaultdict(set)
        for name, expr in self.aliases.items():
            tokens = expr.replace('(', ' ').replace(')', ' ').replace('*', ' ').replace('+', ' ').replace('-', ' ').replace('/', ' ').split()
            for token in tokens:
                if token in self.aliases:
                    dependencies[name].add(token)
        return dependencies

    def plot_alias_dependencies(self):
        deps = self._resolve_dependencies()
        G = nx.DiGraph()
        for alias, subdeps in deps.items():
            for dep in subdeps:
                G.add_edge(dep, alias)
        pos = nx.spring_layout(G)
        plt.figure(figsize=(10, 6))
        nx.draw(G, pos, with_labels=True, node_color='lightblue', edge_color='gray', node_size=2000, font_size=10, arrows=True)
        plt.title("Alias Dependency Graph")
        plt.show()

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
                local_env = {col: self.df[col] for col in self.df.columns}
                local_env.update({k: self.df[k] for k in self.aliases if k in self.df})
                eval(expr, self._default_functions(), local_env)
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

    def materialize_alias0(self, name, dtype=None):
        if name in self.aliases:
            local_env = {col: self.df[col] for col in self.df.columns}
            local_env.update({k: self.df[k] for k in self.aliases if k in self.df})
            for cname in self.constant_aliases:
                try:
                    val = eval(self.aliases[cname], self._default_functions())
                    local_env[cname] = val
                except Exception as e:
                    print(f"[Alias constant] Failed to evaluate constant '{cname}': {e}")
            result = eval(self.aliases[name], self._default_functions(), local_env)
            result_dtype = dtype or self.alias_dtypes.get(name)
            if result_dtype is not None:
                try:
                    result = result.astype(result_dtype)
                except AttributeError:
                    result = result_dtype(result)
            if name not in self.constant_aliases:
                self.df[name] = result

    def materialize_alias(self, name, cleanTemporary=False, dtype=None):
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

        original_columns = set(self.df.columns)

        for alias in to_materialize:
            if alias in self.constant_aliases:
                continue
            local_env = {col: self.df[col] for col in self.df.columns}
            local_env.update({k: self.df[k] for k in self.aliases if k in self.df})
            for cname in self.constant_aliases:
                try:
                    val = eval(self.aliases[cname], self._default_functions())
                    local_env[cname] = val
                except Exception as e:
                    print(f"[Alias constant] Failed to evaluate constant '{cname}': {e}")
            try:
                result = eval(self.aliases[alias], self._default_functions(), local_env)
                result_dtype = dtype or self.alias_dtypes.get(alias)
                if result_dtype is not None:
                    try:
                        result = result.astype(result_dtype)
                    except AttributeError:
                        result = result_dtype(result)
                self.df[alias] = result
            except Exception as e:
                print(f"Failed to materialize {alias}: {e}")

        if cleanTemporary:
            for alias in to_materialize:
                if alias != name and alias not in original_columns:
                    self.df.drop(columns=[alias], inplace=True)

    def materialize_all(self, dtype=None):
        order = self._topological_sort()
        for name in order:
            if name in self.constant_aliases:
                continue
            try:
                local_env = {col: self.df[col] for col in self.df.columns}
                local_env.update({k: self.df[k] for k in self.df.columns if k in self.aliases})
                for cname in self.constant_aliases:
                    val = eval(self.aliases[cname], self._default_functions())
                    local_env[cname] = val
                result = eval(self.aliases[name], self._default_functions(), local_env)
                result_dtype = dtype or self.alias_dtypes.get(name)
                if result_dtype is not None:
                    try:
                        result = result.astype(result_dtype)
                    except AttributeError:
                        result = result_dtype(result)
                self.df[name] = result
            except Exception as e:
                print(f"Failed to materialize {name}: {e}")

    def save(self, path_prefix, dropAliasColumns=True):
        import pyarrow as pa
        import pyarrow.parquet as pq

        if dropAliasColumns:
            cols = [c for c in self.df.columns if c not in self.aliases]
        else:
            cols = list(self.df.columns)

        table = pa.Table.from_pandas(self.df[cols])
        metadata = {
            "aliases": json.dumps(self.aliases),
            "dtypes": json.dumps({k: v.__name__ for k, v in self.alias_dtypes.items()}),
            "constants": json.dumps(list(self.constant_aliases))
        }
        existing_meta = table.schema.metadata or {}
        combined_meta = existing_meta.copy()
        combined_meta.update({k.encode(): v.encode() for k, v in metadata.items()})
        table = table.replace_schema_metadata(combined_meta)
        pq.write_table(table, f"{path_prefix}.parquet", compression="zstd")

        with open(f"{path_prefix}.aliases.json", "w") as f:
            json.dump(metadata, f, indent=2)

    @staticmethod
    def load(path_prefix):
        import pyarrow.parquet as pq
        table = pq.read_table(f"{path_prefix}.parquet")
        df = table.to_pandas()
        adf = AliasDataFrame(df)

        meta = table.schema.metadata or {}
        if b"aliases" in meta and b"dtypes" in meta:
            adf.aliases = json.loads(meta[b"aliases"].decode())
            adf.alias_dtypes = {k: getattr(np, v) for k, v in json.loads(meta[b"dtypes"].decode()).items()}
            if b"constants" in meta:
                adf.constant_aliases = set(json.loads(meta[b"constants"].decode()))
        else:
            with open(f"{path_prefix}.aliases.json") as f:
                data = json.load(f)
                adf.aliases = json.loads(data["aliases"])
                adf.alias_dtypes = {k: getattr(np, v) for k, v in json.loads(data["dtypes"]).items()}
                if "constants" in data:
                    adf.constant_aliases = set(json.loads(data["constants"]))

        return adf

    def export_tree(self, filename, treename="tree", dropAliasColumns=True):
        if dropAliasColumns:
            export_cols = [col for col in self.df.columns if col not in self.aliases]
        else:
            export_cols = list(self.df.columns)
        dtype_casts = {col: np.float32 for col in export_cols if self.df[col].dtype == np.float16}
        export_df = self.df[export_cols].astype(dtype_casts)

        with uproot.recreate(filename) as f:
            f[treename] = export_df
        f = ROOT.TFile.Open(filename, "UPDATE")
        tree = f.Get(treename)
        for alias, expr in self.aliases.items():
            expr_str = expr
            try:
                val = float(expr)
                expr_str = f"({val}+0)"
            except Exception:
                pass
            tree.SetAlias(alias, expr_str)
        tree.Write("", ROOT.TObject.kOverwrite)
        f.Close()

    @staticmethod
    def read_tree(filename, treename="tree"):
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
