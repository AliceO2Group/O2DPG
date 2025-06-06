### `AliasDataFrame` – A Lightweight Wrapper for Pandas with Alias Support

`AliasDataFrame` is a small utility that extends `pandas.DataFrame` functionality by enabling:

* **Lazy evaluation of derived columns via named aliases**
* **Automatic dependency resolution across aliases**
* **Persistence via Parquet + JSON or ROOT TTree (via `uproot` + `PyROOT`)**
* **ROOT-compatible TTree export/import including alias metadata**

---

#### 🔧 Example Usage

```python
import pandas as pd
from AliasDataFrame import AliasDataFrame

# Base DataFrame
df = pd.DataFrame({"x": [1, 2], "y": [10, 20]})
adf = AliasDataFrame(df)

# Add aliases (on-demand expressions)
adf.add_alias("z", "x + y")
adf.add_alias("w", "z * 2")

# Materialize evaluated columns
adf.materialize_all()
print(adf.df)
```

---

#### 📦 Persistence

##### Save to Parquet + Aliases JSON:

```python
adf.save("mydata")
```

##### Load from disk:

```python
adf2 = AliasDataFrame.load("mydata")
adf2.describe_aliases()
```

---

#### 🌲 ROOT TTree Support

##### Export to `.root` with aliases:

```python
adf.export_tree("mytree.root", treename="myTree", dropAliasColumns=True)
```

This uses `uproot` for writing columns and `PyROOT` to set alias metadata via `TTree::SetAlias`.

##### Read `.root` file back:

```python
adf2 = adf.read_tree("mytree.root", treename="myTree")
```

---

#### 🔍 Introspection

```python
adf.describe_aliases()
```

Outputs:

* Defined aliases
* Broken/inconsistent aliases
* Dependency graph

---

#### 🧠 Notes

* Dependencies across aliases are auto-resolved via topological sort.
* Cycles in alias definitions are detected and reported.
* Aliases are **not materialized** by default and **not stored** in `.parquet` unless requested.
* `float16` columns are auto-upcast to `float32` for ROOT compatibility.
