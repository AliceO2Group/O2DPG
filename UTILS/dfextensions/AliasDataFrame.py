import sys, os; sys.path.insert(1, os.environ.get("O2DPG", "") + "/UTILS/dfextensions")
import pandas as pd
import numpy as np
import json
import uproot
import ROOT  # type: ignore
import matplotlib.pyplot as plt
import networkx as nx
import re
import ast

class SubframeRegistry:
    def __init__(self):
        self.subframes = {}

    def add_subframe(self, name, alias_df):
        self.subframes[name] = alias_df

    def get(self, name):
        return self.subframes.get(name, None)

    def items(self):
        return self.subframes.items()

def convert_expr_to_root(expr):
    class RootTransformer(ast.NodeTransformer):
        FUNC_MAP = {
            "arctan2": "atan2",
            "mod": "fmod",
            "sqrt": "sqrt",
            "log": "log",
            "log10": "log10",
            "exp": "exp",
            "abs": "abs",
            "power": "pow",
            "maximum": "TMath::Max",
            "minimum": "TMath::Min"
        }

        def visit_Call(self, node):
            def get_func_name(n):
                if isinstance(n, ast.Attribute):
                    return n.attr
                elif isinstance(n, ast.Name):
                    return n.id
                return ""

            func_name = get_func_name(node.func)
            root_func = self.FUNC_MAP.get(func_name, func_name)

            node.args = [self.visit(arg) for arg in node.args]
            node.func = ast.Name(id=root_func, ctx=ast.Load())
            return node

    try:
        expr_clean = re.sub(r"\bnp\\.", "", expr)
        tree = ast.parse(expr_clean, mode='eval')
        tree = RootTransformer().visit(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except Exception:
        return expr

class AliasDataFrame:
    def __init__(self, df):
        self.df = df
        self.aliases = {}
        self.alias_dtypes = {}
        self.constant_aliases = set()
        self._subframes = SubframeRegistry()

    def __getattr__(self, item):
        if item in self.df.columns:
            return self.df[item]
        if item in self.aliases:
            self.materialize_alias(item)
            return self.df[item]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")

    def register_subframe(self, name, adf):
        self._subframes.add_subframe(name, adf)

    def get_subframe(self, name):
        return self._subframes.get(name)

    def _default_functions(self):
        import math
        env = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        env.update({k: getattr(np, k) for k in dir(np) if not k.startswith("_")})
        env["np"] = np
        for sf_name, sf in self._subframes.items():
            env[sf_name] = sf
        return env

    def _check_for_cycles(self):
        try:
            self._topological_sort()
        except ValueError as e:
            raise ValueError("Cycle detected in alias dependencies") from e

    def add_alias(self, name, expression, dtype=None, is_constant=False):
        self.aliases[name] = expression
        if dtype is not None:
            self.alias_dtypes[name] = dtype
        if is_constant:
            self.constant_aliases.add(name)
        self._check_for_cycles()

    def _eval_in_namespace(self, expr):
        local_env = {col: self.df[col] for col in self.df.columns}
        local_env.update({k: self.df[k] for k in self.aliases if k in self.df})
        local_env.update(self._default_functions())
        return eval(expr, {}, local_env)

    def _resolve_dependencies(self):
        from collections import defaultdict
        dependencies = defaultdict(set)
        for name, expr in self.aliases.items():
            tokens = re.findall(r'\b\w+\b', expr)
            for token in tokens:
                if token in self.aliases:
                    dependencies[name].add(token)
        return dependencies

    def _check_for_cycles(self):
        graph = nx.DiGraph()
        for name, deps in self._resolve_dependencies().items():
            for dep in deps:
                graph.add_edge(dep, name)
        try:
            list(nx.topological_sort(graph))
        except nx.NetworkXUnfeasible:
            raise ValueError("Cycle detected in alias dependencies")

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
        self._check_for_cycles()
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
                self._eval_in_namespace(expr)
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

    def materialize_alias(self, name, cleanTemporary=False, dtype=None):
        if name not in self.aliases:
            print(f"[materialize_alias] Warning: alias '{name}' not found.")
            return
        expr = self.aliases[name]

        # Automatically materialize any referenced aliases or subframe aliases
        tokens = re.findall(r'\b\w+\b|\w+\.\w+', expr)
        for token in tokens:
            if '.' in token:
                sf_name, sf_attr = token.split('.', 1)
                sf = self.get_subframe(sf_name)
                if sf and sf_attr in sf.aliases and sf_attr not in sf.df.columns:
                    sf.materialize_alias(sf_attr)
            elif token in self.aliases and token not in self.df.columns:
                self.materialize_alias(token)

        result = self._eval_in_namespace(expr)
        result_dtype = dtype or self.alias_dtypes.get(name)
        if result_dtype is not None:
            try:
                result = result.astype(result_dtype)
            except AttributeError:
                result = result_dtype(result)
        self.df[name] = result

    def materialize_aliases(self, targets, cleanTemporary=True, verbose=False):
        import networkx as nx
        def build_graph():
            g = nx.DiGraph()
            for alias, expr in self.aliases.items():
                for token in re.findall(r'\b\w+\b', expr):
                    if token in self.aliases:
                        g.add_edge(token, alias)
            return g
        g = build_graph()
        required = set()
        for t in targets:
            if t not in self.aliases:
                if verbose:
                    print(f"[materialize_aliases] Skipping non-alias target: {t}")
                continue
            if t not in g:
                if verbose:
                    print(f"[materialize_aliases] Alias '{t}' not in graph")
                continue
            try:
                required |= nx.ancestors(g, t)
            except nx.NetworkXError:
                continue
            required.add(t)
        ordered = list(nx.topological_sort(g.subgraph(required)))
        added = []
        for name in ordered:
            if name not in self.df.columns:
                self.materialize_alias(name)
                added.append(name)
        if cleanTemporary:
            for col in added:
                if col not in targets and col in self.df.columns:
                    self.df.drop(columns=[col], inplace=True)
        return added

    def materialize_all(self):
        self._check_for_cycles()
        for name in self.aliases:
            self.materialize_alias(name)

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
            try:
                val = float(expr)
                expr_str = f"({val}+0)"
            except Exception:
                expr_str = convert_expr_to_root(expr)
            tree.SetAlias(alias, expr_str)
        metadata = {
            "aliases": self.aliases,
            "dtypes": {k: v.__name__ for k, v in self.alias_dtypes.items()},
            "constants": list(self.constant_aliases),
        }
        jmeta = json.dumps(metadata)
        tree.GetUserInfo().Add(ROOT.TObjString(jmeta))
        tree.Write("", ROOT.TObject.kOverwrite)
        f.Close()

    @staticmethod
    def read_tree(filename, treename="tree"):
        with uproot.open(filename) as f:
            df = f[treename].arrays(library="pd")
        adf = AliasDataFrame(df)
        f = ROOT.TFile.Open(filename)
        try:
            tree = f.Get(treename)
            for alias in tree.GetListOfAliases():
                adf.aliases[alias.GetName()] = alias.GetTitle()
            user_info = tree.GetUserInfo()
            for i in range(user_info.GetEntries()):
                obj = user_info.At(i)
                if isinstance(obj, ROOT.TObjString):
                    try:
                        jmeta = json.loads(obj.GetString().Data())
                        adf.aliases.update(jmeta.get("aliases", {}))
                        adf.alias_dtypes.update({k: getattr(np, v) for k, v in jmeta.get("dtypes", {}).items()})
                        adf.constant_aliases.update(jmeta.get("constants", []))
                        break
                    except Exception:
                        pass
        finally:
            f.Close()
        return adf
