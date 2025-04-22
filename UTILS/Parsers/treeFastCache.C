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
/* ------------------------------------------------------------------
   Statistics extension (non‑breaking) -------------------------------
   Added without changing previous API.

   New options:
     • Enum‑based interface for better ROOT compatibility
         enum StatKind { kMean=0, kMedian=1, kStd=2 };
         float getStat(double x,int mapID,StatKind kind,double dx);

     • Convenience thin wrappers for ROOT aliases
         getMean1D , getMedian1D , getStd1D

     • cacheStat unchanged (uses strings internally)

   ------------------------------------------------------------------*/

#include <vector>
#include <algorithm>
#include <numeric>

// --- enum for faster numeric calls --------------------------------
enum StatKind { kMean=0, kMedian=1, kStd=2 };

// Cache: stat → mapID → dx → (x → value)
static std::map<int, std::map<double, std::map<double,float>>> cacheMean;
static std::map<int, std::map<double, std::map<double,float>>> cacheMedian;
static std::map<int, std::map<double, std::map<double,float>>> cacheStd;

static float _mean(const std::vector<float>& v){ return v.empty()?NAN:std::accumulate(v.begin(),v.end(),0.0f)/v.size(); }
static float _median(std::vector<float> v){ if(v.empty()) return NAN; size_t n=v.size()/2; std::nth_element(v.begin(),v.begin()+n,v.end()); return v[n]; }
static float _std(const std::vector<float>& v){ if(v.size()<2) return NAN; float m=_mean(v); double s2=0; for(float e:v){ double d=e-m; s2+=d*d;} return std::sqrt(s2/(v.size()-1)); }

//--------------------------------------------------------------------
static float _computeStat(double x,int mapID,double dx,StatKind k){
  const auto itM=registeredMaps.find(mapID);
  if(itM==registeredMaps.end()||itM->second.empty()) return NAN;
  const auto &mp=itM->second;
  std::vector<float> buf;
  for(auto it=mp.lower_bound(x-dx); it!=mp.end()&&it->first<=x+dx; ++it) buf.push_back(it->second);
  if(buf.empty()) return NAN;
  switch(k){
    case kMean:   return _mean(buf);
    case kMedian: return _median(buf);
    case kStd:    return _std(buf);
  }
  return NAN;
}

//--------------------------------------------------------------------
/**
 * @brief   Return a local statistic (mean / median / std) around a query point.
 *
 * This version is preferred inside **TTree::Draw** because it uses an enum
 * instead of a string literal.
 *
 * @param x      Center of the window (same coordinate used in the cache)
 * @param mapID  ID returned by registerMap1D / registerMap1DByName
 * @param kind   kMean (0), kMedian (1) or kStd (2)
 * @param dx     Half‑window size: the statistic is computed from all points
 *               with X in [x − dx, x + dx]
 *
 * Internally the first request builds (and caches) a map  x → stat(x)
 * for the given (mapID, dx, kind). Subsequent calls are O(log N).
 */
// Fast numeric interface (enum) ------------------------------------
float getStat(double x,int mapID,StatKind kind,double dx){
  auto *pcache = (kind==kMean? &cacheMean : (kind==kMedian? &cacheMedian : &cacheStd));
  auto &byMap  = (*pcache)[mapID];
  auto &byDx   = byMap[dx];
  if(byDx.empty()){
    // build lazily for this dx
    const auto itM=registeredMaps.find(mapID);
    if(itM==registeredMaps.end()) return NAN;
    for(const auto &kv: itM->second){ double cx=kv.first; byDx[cx]=_computeStat(cx,mapID,dx,kind);}  }
  const auto &statMap = byDx;
  auto it=statMap.lower_bound(x);
  if(it==statMap.begin()) return it->second;
  if(it==statMap.end())   return std::prev(it)->second;
  auto prev=std::prev(it);
  return (fabs(prev->first-x)<fabs(it->first-x)?prev->second:it->second);
}

// String interface kept for backward compat.
float getStat(double x,int mapID,const char* st,double dx){
  std::string s(st);
  if(s=="mean")   return getStat(x,mapID,kMean  ,dx);
  if(s=="median") return getStat(x,mapID,kMedian,dx);
  if(s=="std"||s=="sigma") return getStat(x,mapID,kStd,dx);
  std::cerr<<"[getStat] Unknown statType="<<s<<std::endl; return NAN;
}

//--------------------------------------------------------------------
// Convenience wrappers for ROOT Draw / numeric helpers -----------------
inline float getMean1D  (double x,int id,double dx){ return getStat(x,id,kMean  ,dx);}  // mean
inline float getMedian1D(double x,int id,double dx){ return getStat(x,id,kMedian,dx);}  // median
inline float getStd1D   (double x,int id,double dx){ return getStat(x,id,kStd   ,dx);}  // stddev

// Integer overload for ROOT (fix #2)  --------------------------------
inline float getStat(double x,int id,int kind,double dx){
  return getStat(x,id,static_cast<StatKind>(kind),dx);
}

//--------------------------------------------------------------------
// Pre‑cache requested stats (by enum) ------------------------------- (by enum) -------------------------------
bool cacheStat(int mapID,const std::vector<std::string>& stats,double dx){
  for(const std::string &s:stats){
    if(s=="mean")   getStat(0,mapID,kMean  ,dx);    // lazy build
    else if(s=="median") getStat(0,mapID,kMedian,dx);
    else if(s=="std"||s=="sigma") getStat(0,mapID,kStd,dx);
  }
  return true;
}

//--------------------------------------------------------------------
/// Example: statistics with enum wrappers
void exampleStat1D(){
  TFile *f=TFile::Open("timeSeries10000_apass5.root");
  TTree *t=(TTree*)f->Get("timeSeries");
  int id = registerMap1DByName("dcar_time_stat","time","mTSITSTPC.mDCAr_A_NTracks_median",t,"subentry==127");

  // Pre‑cache mean & std for ±200 window
  cacheStat(id,{"mean","std"},200);

      // Use integer selector (0 = mean, 2 = std). This avoids any ROOT
  // overload ambiguity and works in TTree::Draw directly.
  t->SetAlias("dcar_mean",  Form("getStat(time,%d,0,200)", id)); // 0 → kMean
  t->SetAlias("dcar_sigma", Form("getStat(time,%d,2,200)", id)); // 2 → kStd

  t->Draw("mTSITSTPC.mDCAr_A_NTracks_median:dcar_mean","indexType==1","colz",10000);
  t->Draw("getStat(time,591487517, 0 ,10000+0):getStat(time,591487517, 1 ,10000+0)","indexType==1","colz",100000);
}