Here's a combined `README.md` that covers both `treeFastCache1D.C` and `treeFastCacheND.C`. It provides an overview of both systems, explains their purpose and usage, and includes examples for each.

---

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

## 🔷 `treeFastCacheND.C`

### ✅ Features

- ND caching with:
    - **Exact match** in N–1 dimensions
    - **Nearest-neighbor** lookup in 1 dimension (e.g. `time`)
- Uses full `double` precision for all keys
- Alias support for `TTree::Draw`
- Registration by name with hashed map ID
- Easy to integrate, extendable to class-based interface

### 🧪 Example: Time Series

```cpp
TTree* tree = ...;
int mapID = registerMapND("dcar_vs_time", tree, {"subentry"}, "time", "mTSITSTPC.mDCAr_A_NTracks_median", "1");
setNearestNDAlias(tree, "dcar_smooth", "dcar_vs_time", "time", {"subentry"});

tree->Draw("mTSITSTPC.mDCAr_A_NTracks_median:dcar_smooth", "indexType==1", "colz", 10000);
```

---

## 🧱 Internal Storage

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

- Use aliases to simplify and standardize plotting
- Pre-register frequently used maps in init scripts
- Use full double precision for input axes to ensure match stability
- Prefer descriptive names for map registration

---

## 📤 Future Ideas

- Optional linear interpolation (vs. nearest)
- Fallback behavior when no exact match is found
- Statistics and diagnostics on caches
- Class-based C++ wrapper with lifecycle management

---

## 📄 License

Intended for use in internal physics analyses. No warranty implied.

---

Let me know if you'd like me to create a markdown file or commit it alongside the `.C` macros.