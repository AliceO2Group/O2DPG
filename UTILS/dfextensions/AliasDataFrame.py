import sys, os; sys.path.insert(1, os.environ.get("O2DPG", "") + "/UTILS/dfextensions")
import pandas as pd
import numpy as np
import json
import uproot
try:
    import ROOT  # type: ignore
except ImportError as e:
    print(f"[AliasDataFrame] WARNING: ROOT import failed: {e}")
    ROOT = None
import matplotlib.pyplot as plt
import networkx as nx
import re
import ast

class SubframeRegistry:
    """
    Registry to manage subframes (nested AliasDataFrame instances).
    """
    def __init__(self):
        self.subframes = {}  # name → {'frame': adf, 'index': index_columns}

    def add_subframe(self, name, alias_df, index_columns, pre_index=False):
        if pre_index and not alias_df.df.index.names == index_columns:
            alias_df.df.set_index(index_columns, inplace=True)
        self.subframes[name] = {'frame': alias_df, 'index': index_columns}

    def get(self, name):
        return self.subframes.get(name, {}).get('frame', None)

    def get_entry(self, name):
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

            # Use NumpyRootMapper for function name translation
            root_func = NumpyRootMapper.get_root_name(func_name)
            # Fallback to old FUNC_MAP for backward compatibility
            if root_func == func_name:
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
# Add BEFORE class AliasDataFrame:

class NumpyRootMapper:
    """Maps NumPy function names to ROOT C++ equivalents"""

    # Maps function names to (numpy_attr, root_name)
    # Some functions are aliases (asinh → arcsinh in numpy)
    MAPPING = {
        # Hyperbolic functions (needed for compression)
        'sinh': ('sinh', 'sinh'),
        'cosh': ('cosh', 'cosh'),
        'tanh': ('tanh', 'tanh'),
        'arcsinh': ('arcsinh', 'asinh'),
        'arccosh': ('arccosh', 'acosh'),
        'arctanh': ('arctanh', 'atanh'),
        'asinh': ('arcsinh', 'asinh'),     # Alias: np.arcsinh
        'acosh': ('arccosh', 'acosh'),     # Alias: np.arccosh
        'atanh': ('arctanh', 'atanh'),     # Alias: np.arctanh

        # Trigonometric
        'sin': ('sin', 'sin'),
        'cos': ('cos', 'cos'),
        'tan': ('tan', 'tan'),
        'arcsin': ('arcsin', 'asin'),
        'arccos': ('arccos', 'acos'),
        'arctan': ('arctan', 'atan'),
        'arctan2': ('arctan2', 'atan2'),
        'asin': ('arcsin', 'asin'),        # Alias: np.arcsin
        'acos': ('arccos', 'acos'),        # Alias: np.arccos
        'atan': ('arctan', 'atan'),        # Alias: np.arctan

        # Exponential/log
        'exp': ('exp', 'exp'),
        'log': ('log', 'log'),
        'log10': ('log10', 'log10'),
        'sqrt': ('sqrt', 'sqrt'),
        'pow': ('power', 'pow'),
        'power': ('power', 'pow'),

        # Rounding
        'round': ('round', 'round'),
        'floor': ('floor', 'floor'),
        'ceil': ('ceil', 'ceil'),
        'abs': ('abs', 'abs'),
    }

    @classmethod
    def get_numpy_functions_for_eval(cls):
        """Get dict of function_name → numpy_function for evaluation"""
        funcs = {}
        for name, (np_attr, _) in cls.MAPPING.items():
            if hasattr(np, np_attr):
                funcs[name] = getattr(np, np_attr)
        return funcs

    @classmethod
    def get_root_name(cls, name):
        """Get ROOT C++ equivalent name for a function"""
        entry = cls.MAPPING.get(name)
        return entry[1] if entry else name
class AliasDataFrame:
    """
    AliasDataFrame allows for defining and evaluating lazy-evaluated column aliases
    on top of a pandas DataFrame, including nested subframes with hierarchical indexing.
    """
    def __init__(self, df):
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"AliasDataFrame must be initialized with a pandas.DataFrame. "
                f"Received type: {type(df)}"
            )
        self.df = df
        self.aliases = {}
        self.alias_dtypes = {}
        self.constant_aliases = set()
        self.compression_info = {}  # NEW: track compressed columns
        self._subframes = SubframeRegistry()

    def __getattr__(self, item: str):
        if item in self.df.columns:
            return self.df[item]
        if item in self.aliases:
            self.materialize_alias(item)
            return self.df[item]
        sf = self._subframes.get(item)
        if sf is not None:
            return sf
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")


    def register_subframe(self, name, adf, index_columns, pre_index=False):
        self._subframes.add_subframe(name, adf, index_columns, pre_index=pre_index)

    def get_subframe(self, name):
        return self._subframes.get(name)

    def _default_functions(self):
        import math
        env = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}

        # Add numpy functions (will override math versions with vectorized numpy)
        env.update(NumpyRootMapper.get_numpy_functions_for_eval())

        env["np"] = np
        for sf_name, sf_entry in self._subframes.items():
            env[sf_name] = sf_entry['frame']

        env["int"] = lambda x: np.array(x).astype(np.int32)
        env["uint"] = lambda x: np.array(x).astype(np.uint32)
        env["float"] = lambda x: np.array(x).astype(np.float32)
        env["round"] = np.round
        env["clip"] = np.clip

        return env

    def _prepare_subframe_joins(self, expr):
        tokens = re.findall(r'(\b\w+)\.(\w+)', expr)
        for sf_name, sf_col in tokens:
            entry = self._subframes.get_entry(sf_name)
            if not entry:
                continue
            sub_adf = entry['frame']
            sub_df = sub_adf.df
            index_cols = entry['index']
            if isinstance(index_cols, str):
                index_cols = [index_cols]
            merge_cols = index_cols + [sf_col]
            suffix = f'__{sf_name}'

            try:
                cols_to_merge = sub_df[merge_cols]
            except KeyError:
                if sf_col in sub_adf.aliases:
                    sub_adf.materialize_alias(sf_col)
                    sub_df = sub_adf.df
                    cols_to_merge = sub_df[merge_cols]
                else:
                    raise KeyError(f"Subframe '{sf_name}' does not contain or define alias '{sf_col}'")

            joined = self.df.merge(cols_to_merge, on=index_cols, suffixes=('', suffix))
            col_renamed = f'{sf_col}{suffix}'
            if col_renamed in joined.columns:
                self.df[col_renamed] = joined[col_renamed].values
                expr = expr.replace(f'{sf_name}.{sf_col}', col_renamed)
        return expr

    def _check_for_cycles(self):
        try:
            self._topological_sort()
        except ValueError as e:
            raise ValueError("Cycle detected in alias dependencies") from e

    def add_alias(self, name, expression, dtype=None, is_constant=False):
        """
        Define a new alias.
        Args:
            name: Name of the alias.
            expression: Expression string using pandas or NumPy operations.
            dtype: Optional numpy dtype to enforce.
            is_constant: Whether the alias represents a scalar constant.
        """
        self.aliases[name] = expression
        if dtype is not None:
            self.alias_dtypes[name] = dtype
        if is_constant:
            self.constant_aliases.add(name)
        self._check_for_cycles()

    def _eval_in_namespace(self, expr):
        expr = self._prepare_subframe_joins(expr)
        local_env = {col: self.df[col] for col in self.df.columns}
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
        """
        Evaluate an alias and store its result as a real column.
        Args:
            name: Alias name to materialize.
            cleanTemporary: Whether to clean up intermediate dependencies.
            dtype: Optional override dtype to cast to.

        Raises:
            KeyError: If alias is not defined.
            Exception: If alias evaluation fails.
        """
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
            "constants": json.dumps(list(self.constant_aliases)),
            "compression_info": json.dumps(self.compression_info)  # NEW
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
        if b"compression_info" in meta:
            adf.compression_info = json.loads(meta[b"compression_info"].decode())
        else:
            adf.compression_info = {}  # backward compat
        return adf

    def export_tree(self, filename_or_file, treename="tree", dropAliasColumns=True,compression=uproot.ZLIB(level=1)):
        """
        uproot.LZMA(level=5)
        :param filename_or_file:
        :param treename:
        :param dropAliasColumns:
        :param compression:
        :return:
        """
        is_path = isinstance(filename_or_file, str)

        if is_path:
            with uproot.recreate(filename_or_file,compression=compression) as f:
                self._write_to_uproot(f, treename, dropAliasColumns)
            self._write_metadata_to_root(filename_or_file, treename)
        else:
            self._write_to_uproot(filename_or_file, treename, dropAliasColumns)
        for subframe_name, entry in self._subframes.items():
            entry["frame"]._write_metadata_to_root(filename_or_file, f"{treename}__subframe__{subframe_name}")

    def _write_to_uproot(self, uproot_file, treename, dropAliasColumns):
        export_cols = [col for col in self.df.columns if not dropAliasColumns or col not in self.aliases]
        dtype_casts = {col: np.float32 for col in export_cols if self.df[col].dtype == np.float16}
        export_df = self.df[export_cols].astype(dtype_casts)

        #uproot_file[treename] = export_df
        uproot_file[treename] = {col: export_df[col].values for col in export_df.columns}
        for subframe_name, entry in self._subframes.items():
            entry["frame"].export_tree(uproot_file, f"{treename}__subframe__{subframe_name}", dropAliasColumns)

    def _write_metadata_to_root(self, filename, treename):
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
            "subframe_indices": {k: v["index"] for k, v in self._subframes.items()},
            "dtypes": {k: v.__name__ for k, v in self.alias_dtypes.items()},
            "constants": list(self.constant_aliases),
            "subframes": list(self._subframes.subframes.keys()),
            "compression_info": self.compression_info  # NEW
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
                        for sf_name in jmeta.get("subframes", []):
                            sf = AliasDataFrame.read_tree(filename, treename=f"{treename}__subframe__{sf_name}")
                            index = jmeta.get("subframe_indices", {}).get(sf_name)
                            if index is None:
                                raise ValueError(f"Missing index_columns for subframe '{sf_name}' in metadata")
                            adf.register_subframe(sf_name, sf, index_columns=index)
                        adf.compression_info = jmeta.get("compression_info", {})
                        break
                    except Exception:
                        pass
        finally:
            f.Close()
        return adf

    # ========================================================================
    # Compression Support
    # ========================================================================

    def compress_columns(self, compression_spec, suffix='_c', drop_original=True,
                         measure_precision=False):
        """
        Compress columns using bidirectional transforms.

        Stores compressed version as materialized column, adds decompression
        alias for lazy evaluation. Original column name becomes alias pointing
        to decompressed expression.

        Parameters
        ----------
        compression_spec : dict
            Format: {
                'column_name': {
                    'compress': 'expression',           # e.g., 'round(asinh(dy)*40)'
                    'decompress': 'expression',         # e.g., 'sinh(dy_c/40.)'
                    'compressed_dtype': np.int16,       # Storage dtype
                    'decompressed_dtype': np.float16    # Reconstructed dtype
                }
            }
        suffix : str, optional
            Compressed column name suffix (default: '_c')
        drop_original : bool, optional
            Remove original column after compression (default: True)
        measure_precision : bool, optional
            Compute and store compression precision loss (default: False)

        Returns
        -------
        self : AliasDataFrame
            For method chaining

        Raises
        ------
        ValueError
            If column already compressed, compressed name conflicts, or
            required config keys missing

        Examples
        --------
        >>> spec = {
        ...     'dy': {
        ...         'compress': 'round(asinh(dy)*40)',
        ...         'decompress': 'sinh(dy_c/40.)',
        ...         'compressed_dtype': np.int16,
        ...         'decompressed_dtype': np.float16
        ...     }
        ... }
        >>> adf.compress_columns(spec)
        >>> # Storage: dy_c (int16), dy is alias → sinh(dy_c/40.)

        Notes
        -----
        - Compressed columns are materialized immediately
        - Decompression aliases are lazy (evaluated on demand)
        - Compression metadata stored for round-trip persistence
        - Processing is column-by-column: if one fails, previously processed
          columns remain compressed. Use get_compression_info() to check state.
        - Error handling delegates to add_alias() for expression validation
        """
        for orig_col, config in compression_spec.items():
            # Validate config
            required_keys = ['compress', 'decompress', 'compressed_dtype', 'decompressed_dtype']
            missing = [k for k in required_keys if k not in config]
            if missing:
                raise ValueError(
                    f"Compression config for '{orig_col}' missing required keys: {missing}"
                )

            # Guard: prevent double compression
            if orig_col in self.compression_info:
                raise ValueError(
                    f"Column '{orig_col}' is already compressed. "
                    f"Use decompress_columns(['{orig_col}'], inplace=True) to decompress first."
                )

            compressed_col = f"{orig_col}{suffix}"

            # Guard: prevent name collision
            if compressed_col in self.df.columns:
                raise ValueError(
                    f"Compressed column name '{compressed_col}' already exists in DataFrame. "
                    f"Choose a different suffix or rename the existing column."
                )
            if compressed_col in self.aliases:
                raise ValueError(
                    f"Compressed column name '{compressed_col}' conflicts with existing alias. "
                    f"Choose a different suffix."
                )

            # Cache original values if measuring precision
            original_values = None
            if measure_precision and orig_col in self.df.columns:
                original_values = self.df[orig_col].values.copy()

            # Step 1: Create and materialize compressed version
            try:
                self.add_alias(compressed_col, config['compress'],
                               dtype=config['compressed_dtype'])
                self.materialize_alias(compressed_col)
                # Remove from aliases to avoid false cycle detection
                if compressed_col in self.aliases:
                    del self.aliases[compressed_col]
                    if compressed_col in self.alias_dtypes:
                        del self.alias_dtypes[compressed_col]
            except SyntaxError as e:
                raise ValueError(
                    f"Compression failed for '{orig_col}': invalid compress expression.\n"
                    f"Expression: {config['compress']}\n"
                    f"Error: {e}"
                ) from e
            except KeyError as e:
                raise ValueError(
                    f"Compression failed for '{orig_col}': undefined variable in compress expression.\n"
                    f"Expression: {config['compress']}\n"
                    f"Error: {e}"
                ) from e
            except Exception as e:
                raise ValueError(
                    f"Compression failed for '{orig_col}' during compress step: {e}"
                ) from e

            # Step 2: Measure precision loss if requested
            precision_info = None
            if measure_precision and original_values is not None:
                # Create safe temporary column name
                temp_decompressed = f"__temp_decompress_{orig_col}"
                if temp_decompressed in self.df.columns or temp_decompressed in self.aliases:
                    raise ValueError(
                        f"Internal error: temporary column name '{temp_decompressed}' already exists. "
                        f"This should not happen - please report this bug."
                    )

                try:
                    self.add_alias(temp_decompressed, config['decompress'],
                                   dtype=config['decompressed_dtype'])
                    self.materialize_alias(temp_decompressed)
                    decompressed_values = self.df[temp_decompressed].values

                    # Compute precision metrics
                    diff = original_values - decompressed_values
                    precision_info = {
                        'rmse': float(np.sqrt(np.mean(diff**2))),
                        'max_error': float(np.max(np.abs(diff))),
                        'mean_error': float(np.mean(diff))
                    }

                    # Clean up temporary column
                    self.df.drop(columns=[temp_decompressed], inplace=True)
                    if temp_decompressed in self.aliases:
                        del self.aliases[temp_decompressed]
                        if temp_decompressed in self.alias_dtypes:
                            del self.alias_dtypes[temp_decompressed]
                except Exception as e:
                    # Non-fatal: log but continue
                    precision_info = {'error': str(e)}

            # Step 3: Remove original from storage (if requested and exists)
            if drop_original and orig_col in self.df.columns:
                self.df.drop(columns=[orig_col], inplace=True)

            # Step 4: Add decompression alias (original name → decompressed expression)
            try:
                self.add_alias(orig_col, config['decompress'],
                               dtype=config['decompressed_dtype'])
            except SyntaxError as e:
                raise ValueError(
                    f"Compression failed for '{orig_col}': invalid decompress expression.\n"
                    f"Expression: {config['decompress']}\n"
                    f"Error: {e}"
                ) from e
            except Exception as e:
                raise ValueError(
                    f"Compression failed for '{orig_col}' during decompress alias creation: {e}"
                ) from e

            # Step 5: Store metadata (JSON-safe: dtypes as strings)
            self.compression_info[orig_col] = {
                'compressed_col': compressed_col,
                'compress_expr': config['compress'],
                'decompress_expr': config['decompress'],
                'compressed_dtype': np.dtype(config['compressed_dtype']).name,
                'decompressed_dtype': np.dtype(config['decompressed_dtype']).name,
                'original_removed': drop_original
            }

            if precision_info is not None:
                self.compression_info[orig_col]['precision'] = precision_info

        return self

    def decompress_columns(self, columns=None, inplace=False, keep_compressed=True):
        """
        Materialize decompressed versions of compressed columns.

        Parameters
        ----------
        columns : list of str, optional
            Columns to decompress. If None, decompress all compressed columns.
        inplace : bool, optional
            If True, replace compressed columns with decompressed versions
            and remove compression metadata. If False, materialize decompressed
            alongside compressed (default: False).
        keep_compressed : bool, optional
            If False and inplace=False, remove compressed columns after
            materializing decompressed versions. Ignored when inplace=True
            (default: True).

        Returns
        -------
        self : AliasDataFrame
            For method chaining

        Raises
        ------
        ValueError
            If specified column is not compressed or compressed column missing

        Examples
        --------
        >>> # Keep both compressed and decompressed (default)
        >>> adf.decompress_columns(['dy', 'dz'])

        >>> # Materialize decompressed, remove compressed
        >>> adf.decompress_columns(['dy'], keep_compressed=False)

        >>> # Replace compressed with decompressed permanently
        >>> adf.decompress_columns(inplace=True)

        Notes
        -----
        - Uses materialize_alias() to evaluate decompression expressions
        - inplace=True converts compressed storage back to decompressed storage
        - keep_compressed only affects behavior when inplace=False
        - Validates compressed column exists before attempting decompression
        """
        if columns is None:
            columns = list(self.compression_info.keys())

        for col in columns:
            info = self.compression_info.get(col)
            if info is None:
                raise ValueError(
                    f"Column '{col}' is not marked as compressed. "
                    f"Available compressed columns: {list(self.compression_info.keys())}"
                )

            compressed_col = info['compressed_col']

            # Validate compressed column exists
            if compressed_col not in self.df.columns:
                raise ValueError(
                    f"Compressed column '{compressed_col}' for '{col}' is missing. "
                    f"Cannot decompress without source data."
                )

            # Materialize decompressed alias
            self.materialize_alias(col)

            if inplace:
                # Enforce decompressed dtype
                target_dtype = np.dtype(info['decompressed_dtype']).type
                self.df[col] = self.df[col].astype(target_dtype)

                # Remove compressed column
                self.df.drop(columns=[compressed_col], inplace=True)

                # Remove compression metadata
                del self.compression_info[col]

            elif not keep_compressed:
                # Remove compressed column but keep as decompressed
                self.df.drop(columns=[compressed_col], inplace=True)

                # Remove compression metadata (no longer compressed)
                del self.compression_info[col]

        return self

    def get_compression_info(self, column=None):
        """
        Get compression metadata for columns.

        Parameters
        ----------
        column : str, optional
            Specific column. If None, return all compression info as DataFrame.

        Returns
        -------
        dict or pd.DataFrame
            Compression metadata for specified column or all columns

        Examples
        --------
        >>> adf.get_compression_info('dy')
        {'compressed_col': 'dy_c', 'compress_expr': 'round(asinh(dy)*40)', ...}

        >>> adf.get_compression_info()  # All compressed columns as DataFrame
        """
        if column is None:
            if not self.compression_info:
                return pd.DataFrame()
            return pd.DataFrame.from_dict(self.compression_info, orient='index')
        else:
            return self.compression_info.get(column, {})

    def describe_compression(self):
        """
        Print human-readable compression summary.

        Shows compressed columns, expressions, dtypes, and precision metrics
        if available.

        Examples
        --------
        >>> adf.describe_compression()
        Compressed Columns:
        -------------------
        dy:
          Compressed as: dy_c (int16)
          Expression: round(asinh(dy)*40)
          Decompression: sinh(dy_c/40.) → float16
          Precision: RMSE=0.0012, Max=0.0045
        """
        if not self.compression_info:
            print("No compressed columns")
            return

        print("Compressed Columns:")
        print("-" * 70)
        for col, info in self.compression_info.items():
            print(f"\n{col}:")
            print(f"  Compressed as: {info['compressed_col']} ({info['compressed_dtype']})")
            print(f"  Expression: {info['compress_expr']}")
            print(f"  Decompression: {info['decompress_expr']} → {info['decompressed_dtype']}")
            print(f"  Original removed: {info['original_removed']}")

            if 'precision' in info:
                prec = info['precision']
                if 'error' in prec:
                    print(f"  Precision: measurement failed ({prec['error']})")
                else:
                    print(f"  Precision: RMSE={prec['rmse']:.6f}, "
                          f"Max={prec['max_error']:.6f}, "
                          f"Mean={prec['mean_error']:.6f}")
