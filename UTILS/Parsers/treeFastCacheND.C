/*
.L $O2DPG/UTILS/Parsers/treeFastCacheND.C
*/
/*
  treeFastCacheND.C

  Multi-dimensional cache system for ROOT TTree lookup with mixed matching modes:
    - Exact match in N-1 dimensions
    - Nearest-neighbor in one dimension (typically time)

  This system complements treeFastCache1D by enabling efficient access to structured ND data.

  Features:
    - Caches values based on N-dimensional keys using a combination of exact and nearest lookups
    - Provides ROOT-friendly interface usable within TTree::Draw
    - Uses full double precision for both exact and nearest match coordinates
    - Works interactively with aliases and supports variadic access

  Author: ChatGPT for Marian
*/

#include <TTree.h>
#include <map>
#include <string>
#include <vector>
#include <tuple>
#include <cmath>
#include <iostream>
#include <functional>
#include <stdexcept>

using namespace std;

/// Generic ND key support
typedef std::map<double, double> NearestMap;  ///< 1D interpolation map (e.g., time → value)
typedef std::vector<double> ExactKey;         ///< Exact match dimensions (e.g., subentry, CRU, etc.)

/// Container of ND maps: outer map = mapID → {ExactKey → NearestMap}
std::map<int, std::map<ExactKey, NearestMap>> ndCaches;
std::map<std::string, int> ndNameToID; ///< Map from user-defined name to hash-based mapID

/// Deterministically hash a name to a map ID
int hashMapNameND(const std::string& name) {
  std::hash<std::string> hasher;
  return static_cast<int>(hasher(name));
}

/// Register an ND lookup map from a TTree
/**
 * @param name       Unique name to identify the map
 * @param tree       Source TTree
 * @param exactDims  List of column names for exact-match dimensions
 * @param nearestDim Name of nearest-search dimension (e.g., "time")
 * @param valueVar   Name of value column
 * @param selection  TTree::Draw-compatible selection expression
 * @return           mapID (generated from name)
 */
int registerMapND(const std::string& name,
                   TTree* tree,
                   const std::vector<std::string>& exactDims,
                   const std::string& nearestDim,
                   const std::string& valueVar,
                   const std::string& selection) {
  if (!tree) throw std::invalid_argument("[registerMapND] Null TTree.");
  int mapID = hashMapNameND(name);
  ndNameToID[name] = mapID;

  std::string expr = valueVar + ":" + nearestDim;
  for (const auto& dim : exactDims) expr += ":" + dim;
  int entries = tree->Draw(expr.c_str(), selection.c_str(), "goff");
  if (entries>=tree->GetEstimate()){
    tree->SetEstimate(entries*2);
    entries = tree->Draw(expr.c_str(), selection.c_str(), "goff");
  }
  if (entries <= 0) {
    std::cerr << "[registerMapND] No entries selected." << std::endl;
    return mapID;
  }

  int dimCount = 2 + exactDims.size();
  std::vector<const double*> buffers(dimCount);
  for (int i = 0; i < dimCount; ++i) {
    buffers[i] = tree->GetVal(i);
    if (!buffers[i]) throw std::runtime_error("[registerMapND] Missing Draw buffer at " + std::to_string(i));
  }

  std::map<ExactKey, NearestMap> newMap;
  for (int i = 0; i < entries; ++i) {
    double val = buffers[0][i];
    double near = buffers[1][i];
    ExactKey key;
    for (size_t j = 0; j < exactDims.size(); ++j) key.push_back(buffers[2 + j][i]);
    newMap[key][near] = val;
  }
  ndCaches[mapID] = std::move(newMap);
  std::cout << "[registerMapND] Registered ND map '" << name << "' with ID=" << mapID << " and " << entries << " entries." << std::endl;
  return mapID;
}

/// Query map using exact + nearest key
/**
 * @param query      Value for nearest-match dimension
 * @param mapID      ID of registered map
 * @param exactKey   Vector of exact-match dimensions (must match registration)
 * @return           Interpolated value or NaN if no match
 */
double getNearestND(double query, int mapID, const ExactKey& exactKey) {
  const auto& map = ndCaches[mapID];
  auto itOuter = map.find(exactKey);
  if (itOuter == map.end()) return NAN;

  const auto& innerMap = itOuter->second;
  if (innerMap.empty()) return NAN;

  auto it = innerMap.lower_bound(query);
  if (it == innerMap.begin()) return it->second;
  if (it == innerMap.end()) return std::prev(it)->second;

  auto prev = std::prev(it);
  return (std::abs(prev->first - query) < std::abs(it->first - query)) ? prev->second : it->second;
}

/// Variadic interface to getNearestND for use with TTree::Draw
/**
 * @tparam Dims      Arbitrary number of scalar dimensions (int or float/double)
 * @param query      Nearest dimension (e.g., time)
 * @param mapID      Map ID registered via registerMapND
 * @param dims...    Dimensions to match exactly
 */
template<typename... Dims>
double getNearestND(double query, int mapID, Dims... dims) {
  ExactKey exactKey{static_cast<double>(dims)...};
  return getNearestND(query, mapID, exactKey);
}

/// Lookup using map name
/**
 * @param query      Nearest-dimension value (e.g., time)
 * @param exactKey   Exact-dimension vector
 * @param mapName    Map name from registration
 */
double getNearestNDByName(double query, const ExactKey& exactKey, const std::string& mapName) {
  auto itID = ndNameToID.find(mapName);
  if (itID == ndNameToID.end()) return NAN;
  return getNearestND(query, itID->second, exactKey);
}

/// Register alias in tree for use in interactive Draw
/**
 * @param tree            TTree pointer
 * @param aliasName       Alias to create
 * @param mapName         Name of registered ND map
 * @param nearestCoordExpr Expression for nearest dimension (e.g., "time")
 * @param exactCoordExprs  Expressions for exact dimensions (e.g., {"subentry"})
 */
void setNearestNDAlias(TTree* tree, const std::string& aliasName, const std::string& mapName, const std::string& nearestCoordExpr, const std::vector<std::string>& exactCoordExprs) {
  auto it = ndNameToID.find(mapName);
  if (it == ndNameToID.end()) {
    std::cerr << "[setNearestNDAlias] Map not found: " << mapName << std::endl;
    return;
  }
  int mapID = it->second;

  std::string expr = "getNearestND(" + nearestCoordExpr + "," + std::to_string(mapID);
  for (const auto& ex : exactCoordExprs) expr += "," + ex;
  expr += ")";
  tree->SetAlias(aliasName.c_str(), expr.c_str());
}

/// Example usage for ND map creation - for very High voltage queries for distertion calibration
void exampleND() {
  TTree* tree = new TTree("tree", "demo");
  int mapID = registerMapND("test_map", tree, {"CRU", "iTF"}, "time", "val", "subentry==127");
  setNearestNDAlias(tree, "val_interp", "test_map", "time", {"CRU", "iTF"});
  tree->Draw("val:val_interp", "val!=0", "colz");
}

/// Example usage for time series ND lookup
void exampleTimeSeries() {
  TFile *f = TFile::Open("timeSeries10000_apass5.root");
  TTree *tree = (TTree*)f->Get("timeSeries");
  int mapID = registerMapND("dcar_vs_time", tree, {"subentry"}, "time", "mTSITSTPC.mDCAr_A_NTracks_median", "1");
  setNearestNDAlias(tree, "mDCAr_A_NTracks_median_interp", "dcar_vs_time", "time", {"subentry"});
  tree->Draw("mTSITSTPC.mDCAr_A_NTracks_median:mDCAr_A_NTracks_median_interp", "indexType==1", "", 10000);
}

/// Example usage for time series ND lookup
void test_exampleTimeSeries() {
  TFile *f5 = TFile::Open("timeSeries10000_LHC23zzx_apass5.root");
  TTree *tree5 = (TTree*)f5->Get("timeSeries");
  TFile *f4 = TFile::Open("timeSeries10000_LHC23zz_combo_apass4.root");
  TTree *tree4 = (TTree*)f4->Get("timeSeries");
  int mapID5A = registerMapND("mDCAr_A_Median_median5", tree5, {"subentry"}, "time", "mTSITSTPC.mDCAr_A_Median_median", "1");
  int mapID5C = registerMapND("mDCAr_C_Median_median5", tree5, {"subentry"}, "time", "mTSITSTPC.mDCAr_C_Median_median", "1");
  int mapID4A = registerMapND("mDCAr_A_Median_median4", tree4, {"subentry"}, "time", "mTSITSTPC.mDCAr_A_Median_median", "1");
  int mapID4C = registerMapND("mDCAr_C_Median_median4", tree4, {"subentry"}, "time", "mTSITSTPC.mDCAr_C_Median_median", "1");
  //
  setNearestNDAlias(tree5, "mDCAr_A_Median_median_interp5", "mDCAr_A_Median_median5", "time", {"subentry"});
  setNearestNDAlias(tree5, "mDCAr_C_Median_median_interp5", "mDCAr_C_Median_median5", "time", {"subentry"});
  setNearestNDAlias(tree4, "mDCAr_C_Median_median_interp5", "mDCAr_A_Median_median5", "time", {"subentry"});
  //
  setNearestNDAlias(tree5, "mDCAr_A_Median_median_interp4", "mDCAr_A_Median_median4", "time", {"subentry"});
  setNearestNDAlias(tree4, "mDCAr_A_Median_median_interp4", "mDCAr_A_Median_median4", "time", {"subentry"});

  tree5->Draw("mTSITSTPC.mDCAr_A_Median_median:mDCAr_A_Median_median_interp4", "indexType==1", "", 10000);
  // make unit test -RMS should be 0
  int val5=tree5->Draw("mTSITSTPC.mDCAr_A_Median_median==mDCAr_A_Median_median_interp5", "indexType==1", "");
  float rms5=tree5->GetHistogram()->GetRMS();
  float mean5=tree5->GetHistogram()->GetMean();
  //make unit test like output  rms5==0, mean5==1
  int va4l=tree4->Draw("mTSITSTPC.mDCAr_A_Median_median==mDCAr_A_Median_median_interp4", "indexType==1", "");
  float rms4=tree4->GetHistogram()->GetRMS();
  float mean4=tree4->GetHistogram()->GetMean();
  //make unit test like output  rms5==0, mean5==1
  if ( std::abs(rms4) < 1e-5 && std::abs(mean4 - 1.0) < 1e-5) {
    std::cout << "[UnitTest] OK - Interpolation match for apass4 is exact." << std::endl;
  } else {
    std::cerr << "[UnitTest] ERROR - Interpolation mismatch for apass4. RMS=" << rms4 << ", Mean=" << mean4 << std::endl;
  }
}

