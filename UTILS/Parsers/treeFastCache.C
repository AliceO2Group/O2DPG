/*
.L $O2DPG/UTILS/Parsers/treeFastCache.C
*/

/*
  treeFastCache.C
  Simple caching system for fast lookup of 1D values from a TTree, using nearest-neighbor interpolation.
  This utility allows registration of (X, Y) pairs from a TTree into a std::map,
  indexed by a user-defined mapID or map name. The lookup function `getNearest1D(x, mapID)`
  retrieves the Y value for the X closest to the query.
  Features:
    - Register maps via string name or numeric ID
    - Query nearest-neighbor value for any X
    - Graceful error handling and range checking
    - Base for future ND extension
*/

#include <TTree.h>
#include <TTreeFormula.h>
#include <map>
#include <string>
#include <cmath>
#include <iostream>
#include <functional>

using namespace std;

// Map: mapID -> map<X, Y>
std::map<int, std::map<double, float>> registeredMaps;
std::map<std::string, int> nameToMapID;

/// Hash a string to create a deterministic mapID
int hashMapName(const std::string& name) {
  std::hash<std::string> hasher;
  return static_cast<int>(hasher(name));
}

/// Register a 1D lookup map from TTree (X -> Y)
/// @param valX   Name of the X-axis variable (lookup key)
/// @param valY   Name of the Y-axis variable (value to retrieve)
/// @param tree   Pointer to TTree to extract data from
/// @param selection  Selection string (TTree::Draw-compatible)
/// @param mapID  Integer ID to associate with this map
void registerMap1D(const std::string& valX, const std::string& valY, TTree* tree, const std::string& selection, int mapID) {
  if (!tree) {
    std::cerr << "[registerMap1D] Null TTree pointer." << std::endl;
    return;
  }

  int entries = tree->Draw((valY + ":" + valX).c_str(), selection.c_str(), "goff");
  if (entries <= 0) {
    std::cerr << "[registerMap1D] No entries matched for mapID=" << mapID << std::endl;
    return;
  }

  if (!tree->GetV1() || !tree->GetV2()) {
    std::cerr << "[registerMap1D] Internal Draw buffer pointers are null." << std::endl;
    return;
  }

  std::map<double, float> newMap;
  for (int i = 0; i < entries; ++i) {
    if (i >= tree->GetSelectedRows()) {
      std::cerr << "[registerMap1D] Index out of range at i=" << i << std::endl;
      break;
    }
    double x = tree->GetV2()[i];  // valX
    float y  = tree->GetV1()[i];  // valY
    newMap[x] = y;
  }

  registeredMaps[mapID] = std::move(newMap);
  std::cout << "[registerMap1D] Registered map " << mapID << " with " << entries << " entries." << std::endl;
}

/// Register by name; returns mapID computed from name
int registerMap1DByName(const std::string& mapName, const std::string& valX, const std::string& valY, TTree* tree, const std::string& selection) {
  int mapID = hashMapName(mapName);
  nameToMapID[mapName] = mapID;
  registerMap1D(valX, valY, tree, selection, mapID);
  return mapID;
}

/// Get the nearest Y for a given X from the map registered with mapID
/// @param x       Query value along X axis
/// @param mapID   Map identifier used in registration
/// @return        Y value corresponding to nearest X in the map
float getNearest1D(float x, int mapID) {
  const auto itMap = registeredMaps.find(mapID);
  if (itMap == registeredMaps.end()) {
    std::cerr << "[getNearest1D] Map ID " << mapID << " not found." << std::endl;
    return NAN;
  }

  const auto& map = itMap->second;
  if (map.empty()) {
    std::cerr << "[getNearest1D] Map ID " << mapID << " is empty." << std::endl;
    return NAN;
  }

  auto it = map.lower_bound(x);
  if (it == map.begin()) return it->second;
  if (it == map.end()) return std::prev(it)->second;

  auto prev = std::prev(it);
  return (std::abs(prev->first - x) < std::abs(it->first - x)) ? prev->second : it->second;
}

/// Convenience version: lookup by name
float getNearest1DByName(float x, const std::string& mapName) {
  auto it = nameToMapID.find(mapName);
  if (it == nameToMapID.end()) {
    std::cerr << "[getNearest1DByName] Map name \"" << mapName << "\" not found." << std::endl;
    return NAN;
  }
  return getNearest1D(x, it->second);
}

/// Example usage
void example1D() {
  TFile *f = TFile::Open("timeSeries10000_apass5.root");
  TTree * tree0=(TTree*)f->Get("timeSeries");
  // Fill tree here or load from file
  int mapID = registerMap1DByName("dcar_vs_time", "time", "mTSITSTPC.mDCAr_A_NTracks_median", tree0, "subentry==127");
  tree0->SetAlias("mDCAr_A_NTracks_median_All" ,("getNearest1D(time, " + std::to_string(mapID) + ")").data());
  tree0->Draw("mTSITSTPC.mDCAr_A_NTracks_median:mDCAr_A_NTracks_median_All","indexType==1","",10000);
}
