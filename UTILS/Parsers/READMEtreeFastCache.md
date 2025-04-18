# 📦 ROOT Tree Fast Cache System

This repository contains ROOT macros for fast lookup and interpolation of values from TTrees, using:

- `treeFastCache1D.C`: 1D cache with nearest-neighbor lookup
- `treeFastCacheND.C`: ND cache with exact match in N–1 dimensions and nearest-neighbor in 1 dimension

They are designed for interactive analysis with `TTree::Draw`, e.g., QA plots, calibration overlays, or smoothed time series.

---

## 🔹 `treeFastCache1D.C`

### ✅ Features

- Register 1D lookup maps from TTrees
- Nearest-neighbor lookup from `std::map<double, float>`
- Can register by ID or string name
- Fast evaluation inside `TTree::Draw`
- Alias integration for interactive sessions

### 🧪 Example

```cpp
TTree* tree = ...;
int mapID = registerMap1DByName("dcar_vs_time", "time", "dcar_value", tree, "subentry==127");

tree->SetAlias("dcar_smooth", ("getNearest1D(time," + std::to_string(mapID) + ")").c_str());
tree->Draw("dcar_value:dcar_smooth", "indexType==1", "colz", 10000);
```

---

## 🔸 `treeFastCacheND.C`

### ✅ Features

- ND caching with:
  - **Exact match** in N–1 dimensions
  - **Nearest-neighbor** lookup in 1 dimension (e.g. `time`)
- Uses full `double` precision for all keys
- Alias support for `TTree::Draw`
- Registration by name with hashed map ID
- Variadic interface for direct use

### 🧪 Example: Time Series

```cpp
TTree* tree = ...;
int mapID = registerMapND("dcar_vs_time", tree, {"subentry"}, "time", "mTSITSTPC.mDCAr_A_NTracks_median", "1");
setNearestNDAlias(tree, "dcar_smooth", "dcar_vs_time", "time", {"subentry"});

tree->Draw("mTSITSTPC.mDCAr_A_NTracks_median:dcar_smooth", "indexType==1", "colz", 10000);
```

### 🖊️ Parameters for `registerMapND`
```cpp
int registerMapND(
  const std::string& name,       // Unique name of the map
  TTree* tree,                   // Source TTree
  const std::vector<std::string>& exactDims, // Exact-match coordinate names
  const std::string& nearestDim,             // Nearest-match dimension (e.g. time)
  const std::string& valueVar,               // Variable to interpolate
  const std::string& selection               // TTree selection
);
```

### 🖊️ Parameters for `setNearestNDAlias`
```cpp
void setNearestNDAlias(
  TTree* tree,                          // Target tree
  const std::string& aliasName,        // Alias to create
  const std::string& mapName,          // Name used in registration
  const std::string& nearestCoordExpr, // Nearest-match expression
  const std::vector<std::string>& exactCoordExprs // Exact match expressions
);
```

### ⚡️ Alternative: Direct expression
```cpp
tree->Draw("val:getNearestND(time,mapID,subentry)", ...);
```

---

## 📊 Internal Storage

### 1D:
```cpp
std::map<int, std::map<double, float>> registeredMaps;
std::map<std::string, int> nameToMapID;
```

### ND:
```cpp
std::map<int, std::map<std::vector<double>, std::map<double, double>>> ndCaches;
std::map<std::string, int> ndNameToID;
```

---

## 📌 Best Practices

- Use aliases to simplify `TTree::Draw` expressions
- Use double precision for stability in nearest search
- Store maps by string name to simplify re-registration
- Prefer `setNearestNDAlias()` over manual `getNearestND(...)` for readability

---

## 📤 Future Ideas

- Optional interpolation (linear, spline)
- Graceful handling of unmatched keys
- Caching diagnostics and summary statistics
- C++ class wrapper for lifecycle + reusability

---

## 📜 License

Intended for use in internal physics analyses. No warranty implied.

---

For more details, see comments and examples inside `treeFastCache1D.C` and `treeFastCacheND.C`.
