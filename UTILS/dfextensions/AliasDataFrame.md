# AliasDataFrame – Hierarchical Lazy Evaluation for Pandas + ROOT

`AliasDataFrame` is an extension of `pandas.DataFrame` that enables **named expression-based columns (aliases)** with:

* ✅ **Lazy evaluation** (on-demand computation)
* ✅ **Automatic dependency resolution** (topological sort, cycle detection)
* ✅ **Hierarchical aliasing** across **linked subframes** (e.g. clusters referencing tracks via index joins)
* ✅ **Persistence** to Parquet and ROOT TTree formats, including full alias metadata

It is designed for physics and data analysis workflows where derived quantities, calibration constants, and multi-table joins should remain symbolic until final export.

---

## ✨ Core Features

### ✅ Alias Definition & Lazy Evaluation

Define symbolic columns as expressions involving other columns or aliases:

```python
adf.add_alias("pt", "sqrt(px**2 + py**2)")
adf.materialize_alias("pt")
```

### ✅ Subframe Support (Hierarchical Dependencies)

Reference a subframe (e.g. per-cluster frame linked to a per-track frame):

```python
adf_clusters.register_subframe("T", adf_tracks, index_columns=["track_index"])
adf_clusters.add_alias("dX", "mX - T.mX")
adf_clusters.materialize_alias("dX")
```

Under the hood, this performs a join using `track_index` between clusters and tracks, rewrites `T.mX` to the joined column, and evaluates in that context.

### ✅ Dependency Graph & Cycle Detection

* Automatically resolves dependency order
* Detects and raises on circular alias definitions
* Visualize with:

```python
adf.plot_alias_dependencies()
```

### ✅ Constant Aliases & Dtype Enforcement

```python
adf.add_alias("scale", "1.5", dtype=np.float32, is_constant=True)
```

---

## 💾 Persistence

### ➤ Save to Parquet

```python
adf.save("data/my_frame")  # Saves data + alias metadata
```

### ➤ Load from Parquet

```python
adf2 = AliasDataFrame.load("data/my_frame")
```

### ➤ Export to ROOT TTree (with aliases!)

```python
adf.export_tree("output.root", treename="MyTree")
```

### ➤ Import from ROOT TTree

```python
adf = AliasDataFrame.read_tree("output.root", treename="MyTree")
```

Subframe alias metadata (including join indices) is preserved recursively.

---

## 🧪 Unit-Tested Features

Tests included for:

* Basic alias chaining and materialization
* Dtype conversion
* Constant and hierarchical aliasing
* Partial materialization
* Subframe joins on index columns
* Persistence round-trips for `.parquet` and `.root`
* Error detection: cycles, invalid expressions, undefined symbols

---

## 🧠 Internals

* Expression evaluation via `eval()` with math/Numpy-safe scope
* Dependency analysis via `networkx`
* Subframes stored in a registry (`SubframeRegistry`) with index-aware entries
* Subframe alias resolution is performed via on-the-fly joins using provided index columns
* Metadata embedded into:

  * `.parquet` via Arrow schema metadata
  * `.root` via `TTree::SetAlias` and `TObjString`

---

## 🔍 Introspection & Debugging

```python
adf.describe_aliases()       # Print aliases, dependencies, broken ones
adf.validate_aliases()       # List broken/inconsistent aliases
```

---

## 🧩 Requirements

* `pandas`, `numpy`, `pyarrow`, `uproot`, `networkx`, `matplotlib`, `ROOT`

---

## 🔁 Comparison with Other Tools

| Feature                       | AliasDataFrame | pandas    | Vaex     | Awkward Arrays | polars    | Dask      |
| ----------------------------- | -------------- | --------- | -------- | -------------- | --------- | --------- |
| Lazy alias columns            | ✅ Yes          | ⚠️ Manual | ✅ Yes    | ❌              | ✅ Partial | ✅ Partial |
| Dependency tracking           | ✅ Full graph   | ❌         | ⚠️ Basic | ❌              | ❌         | ❌         |
| Subframe hierarchy (joins)    | ✅ Index-based  | ❌         | ❌        | ⚠️ Nested only | ❌         | ⚠️ Manual |
| Constant alias support        | ✅ With dtype   | ❌         | ❌        | ❌              | ❌         | ❌         |
| Visualization of dependencies | ✅ `networkx`   | ❌         | ❌        | ❌              | ❌         | ❌         |
| Export to ROOT TTree          | ✅ Optional     | ❌         | ❌        | ✅ via uproot   | ❌         | ❌         |

---

## ❓ Why AliasDataFrame?

In many data workflows, users recreate the same patterns again and again:

* Manually compute derived columns with ad hoc logic
* Scatter constants and correction factors in multiple files
* Perform fragile joins between tables (e.g. clusters ↔ tracks) with little traceability
* Lose transparency into what each column actually means

**AliasDataFrame** turns these practices into a formalized, symbolic layer over your DataFrames:

* 📐 Define all derived quantities as symbolic expressions
* 🔗 Keep relations between DataFrames declarative, index-based, and reusable
* 📊 Visualize dependency structures and broken logic automatically
* 📦 Export the full state of your workflow (including symbolic metadata)

It brings the clarity of a computation graph to structured table analysis — a common but under-supported need in `pandas`, `vaex`, or `polars` workflows.

---

## 🛣 Roadmap Ideas

* [ ] Secure expression parser (no raw `eval`)
* [ ] Aliased column caching / invalidation strategy
* [ ] Inter-subframe join strategies (e.g., key-based, 1\:n)
* [ ] Jupyter widget or CLI tool for alias graph exploration
* [ ] Broadcasting-aware joins or 2D index support

---

## 🧑‍🔬 Designed for...

* Physics workflows (e.g. ALICE clusters ↔ tracks ↔ collisions)
* Symbolic calibration / correction workflows
* Structured data exports with traceable metadata

---

**Author:** \[You]

MIT License
