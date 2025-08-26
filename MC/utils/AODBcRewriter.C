// AODBcRewriter.C
// Usage: root -l -b -q 'AODBcRewriter.C("AO2D.root","AO2D_rewritten.root")'
// Fixes globalBC ordering and duplication problems in AO2D files; sorts and
// rewrites tables refering to the BC table generic branch code only; No
// knowledge of AOD dataformat used apart from the BC table.

#ifndef __CLING__
#include "RVersion.h"
#include "TBranch.h"
#include "TBufferFile.h"
#include "TClass.h"
#include "TDirectory.h"
#include "TFile.h"
#include "TKey.h"
#include "TLeaf.h"
#include "TList.h"
#include "TMap.h"
#include "TObjString.h"
#include "TROOT.h"
#include "TString.h"
#include "TTree.h"

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <numeric>
#include <set>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#endif

// ----------------- small helpers -----------------
static inline bool isDF(const char *name) {
  return TString(name).BeginsWith("DF_");
}
static inline bool isBCtree(const char *tname) {
  return TString(tname).BeginsWith("O2bc_");
}
static inline bool isFlagsTree(const char *tname) {
  return TString(tname) == "O2bcflag" || TString(tname) == "O2bcflags" ||
         TString(tname).BeginsWith("O2bcflag");
}
static const char *findIndexBranchName(TTree *t) {
  if (!t)
    return nullptr;
  if (t->GetBranch("fIndexBCs"))
    return "fIndexBCs";
  if (t->GetBranch("fIndexBC"))
    return "fIndexBC";
  return nullptr;
}

// Scalar type tag
enum class ScalarTag {
  kInt,
  kUInt,
  kShort,
  kUShort,
  kLong64,
  kULong64,
  kFloat,
  kDouble,
  kChar,
  kUChar,
  kBool,
  kUnknown
};
static ScalarTag leafType(TLeaf *leaf) {
  if (!leaf)
    return ScalarTag::kUnknown;
  TString tn = leaf->GetTypeName();
  if (tn == "Int_t")
    return ScalarTag::kInt;
  if (tn == "UInt_t")
    return ScalarTag::kUInt;
  if (tn == "Short_t")
    return ScalarTag::kShort;
  if (tn == "UShort_t")
    return ScalarTag::kUShort;
  if (tn == "Long64_t")
    return ScalarTag::kLong64;
  if (tn == "ULong64_t")
    return ScalarTag::kULong64;
  if (tn == "Float_t")
    return ScalarTag::kFloat;
  if (tn == "Double_t")
    return ScalarTag::kDouble;
  if (tn == "Char_t")
    return ScalarTag::kChar;
  if (tn == "UChar_t")
    return ScalarTag::kUChar;
  if (tn == "Bool_t")
    return ScalarTag::kBool;
  return ScalarTag::kUnknown;
}
static size_t scalarSize(ScalarTag t) {
  switch (t) {
  case ScalarTag::kInt:
    return sizeof(Int_t);
  case ScalarTag::kUInt:
    return sizeof(UInt_t);
  case ScalarTag::kShort:
    return sizeof(Short_t);
  case ScalarTag::kUShort:
    return sizeof(UShort_t);
  case ScalarTag::kLong64:
    return sizeof(Long64_t);
  case ScalarTag::kULong64:
    return sizeof(ULong64_t);
  case ScalarTag::kFloat:
    return sizeof(Float_t);
  case ScalarTag::kDouble:
    return sizeof(Double_t);
  case ScalarTag::kChar:
    return sizeof(Char_t);
  case ScalarTag::kUChar:
    return sizeof(UChar_t);
  case ScalarTag::kBool:
    return sizeof(Bool_t);
  default:
    return 0;
  }
}

// small Buffer base for lifetime management
struct BufBase {
  virtual ~BufBase() {}
  virtual void *ptr() = 0;
};
template <typename T> struct ScalarBuf : BufBase {
  T v;
  void *ptr() override { return &v; }
};
template <typename T> struct ArrayBuf : BufBase {
  std::vector<T> a;
  void *ptr() override { return a.data(); }
};

template <typename T> static std::unique_ptr<BufBase> makeScalarBuf() {
  return std::make_unique<ScalarBuf<T>>();
}
template <typename T> static std::unique_ptr<BufBase> makeArrayBuf(size_t n) {
  auto p = std::make_unique<ArrayBuf<T>>();
  if (n == 0)
    n = 1;
  p->a.resize(n);
  return p;
}

// prescan the count branch to determine max length for a VLA
static Long64_t prescanMaxLen(TTree *src, TBranch *countBr,
                              ScalarTag countTag) {
  if (!countBr)
    return 1;
  // temporary buffer
  std::unique_ptr<BufBase> tmp;
  switch (countTag) {
  case ScalarTag::kInt:
    tmp = makeScalarBuf<Int_t>();
    break;
  case ScalarTag::kUInt:
    tmp = makeScalarBuf<UInt_t>();
    break;
  case ScalarTag::kShort:
    tmp = makeScalarBuf<Short_t>();
    break;
  case ScalarTag::kUShort:
    tmp = makeScalarBuf<UShort_t>();
    break;
  case ScalarTag::kLong64:
    tmp = makeScalarBuf<Long64_t>();
    break;
  case ScalarTag::kULong64:
    tmp = makeScalarBuf<ULong64_t>();
    break;
  default:
    tmp = makeScalarBuf<Int_t>();
    break;
  }
  countBr->SetAddress(tmp->ptr());
  Long64_t maxLen = 0;
  Long64_t nEnt = src->GetEntries();
  for (Long64_t i = 0; i < nEnt; ++i) {
    countBr->GetEntry(i);
    Long64_t v = 0;
    switch (countTag) {
    case ScalarTag::kInt:
      v = *(Int_t *)tmp->ptr();
      break;
    case ScalarTag::kUInt:
      v = *(UInt_t *)tmp->ptr();
      break;
    case ScalarTag::kShort:
      v = *(Short_t *)tmp->ptr();
      break;
    case ScalarTag::kUShort:
      v = *(UShort_t *)tmp->ptr();
      break;
    case ScalarTag::kLong64:
      v = *(Long64_t *)tmp->ptr();
      break;
    case ScalarTag::kULong64:
      v = *(ULong64_t *)tmp->ptr();
      break;
    default:
      v = *(Int_t *)tmp->ptr();
      break;
    }
    if (v > maxLen)
      maxLen = v;
  }
  return maxLen;
}

// bind scalar branch (in and out share same buffer)
static std::unique_ptr<BufBase> bindScalarBranch(TBranch *inBr, TBranch *outBr,
                                                 ScalarTag tag) {
  switch (tag) {
  case ScalarTag::kInt: {
    auto b = makeScalarBuf<Int_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kUInt: {
    auto b = makeScalarBuf<UInt_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kShort: {
    auto b = makeScalarBuf<Short_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kUShort: {
    auto b = makeScalarBuf<UShort_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kLong64: {
    auto b = makeScalarBuf<Long64_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kULong64: {
    auto b = makeScalarBuf<ULong64_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kFloat: {
    auto b = makeScalarBuf<Float_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kDouble: {
    auto b = makeScalarBuf<Double_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kChar: {
    auto b = makeScalarBuf<Char_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  case ScalarTag::kUChar: {
    auto b = makeScalarBuf<UChar_t>();
    inBr->SetAddress(b->ptr());
    outBr->SetAddress(b->ptr());
    return b;
  }
  default:
    return nullptr;
  }
}

// bind VLA typed: returns data buffer and outputs count buffer (via
// outCountBuf)
template <typename T>
static std::unique_ptr<BufBase>
bindArrayTyped(TBranch *inData, TBranch *outData, TBranch *inCount,
               TBranch *outCount, ScalarTag countTag, Long64_t maxLen,
               std::unique_ptr<BufBase> &outCountBuf) {
  // create count buffer
  std::unique_ptr<BufBase> countBuf;
  switch (countTag) {
  case ScalarTag::kInt:
    countBuf = makeScalarBuf<Int_t>();
    break;
  case ScalarTag::kUInt:
    countBuf = makeScalarBuf<UInt_t>();
    break;
  case ScalarTag::kShort:
    countBuf = makeScalarBuf<Short_t>();
    break;
  case ScalarTag::kUShort:
    countBuf = makeScalarBuf<UShort_t>();
    break;
  case ScalarTag::kLong64:
    countBuf = makeScalarBuf<Long64_t>();
    break;
  case ScalarTag::kULong64:
    countBuf = makeScalarBuf<ULong64_t>();
    break;
  default:
    countBuf = makeScalarBuf<Int_t>();
    break;
  }
  // data buffer (allocate maxLen)
  auto dataBuf = makeArrayBuf<T>((size_t)std::max<Long64_t>(1, maxLen));

  inCount->SetAddress(countBuf->ptr());
  outCount->SetAddress(countBuf->ptr());
  inData->SetAddress(dataBuf->ptr());
  outData->SetAddress(dataBuf->ptr());

  outCountBuf = std::move(countBuf);
  return dataBuf;
}

// ----------------- BC maps builder -----------------
struct BCMaps {
  std::vector<ULong64_t> originalBCs;
  std::vector<Int_t> indexMap;
  std::vector<ULong64_t> uniqueBCs;
  std::unordered_map<size_t, std::vector<size_t>> newIndexOrigins;
};

static BCMaps buildBCMaps(TTree *treeBCs) {
  BCMaps maps;
  if (!treeBCs)
    return maps;
  TBranch *br = treeBCs->GetBranch("fGlobalBC");
  if (!br) {
    std::cerr << "ERROR: no fGlobalBC\n";
    return maps;
  }
  ULong64_t v = 0;
  br->SetAddress(&v);
  Long64_t n = treeBCs->GetEntries();
  maps.originalBCs.reserve(n);
  for (Long64_t i = 0; i < n; ++i) {
    treeBCs->GetEntry(i);
    maps.originalBCs.push_back(v);
  }

  std::vector<size_t> order(n);
  std::iota(order.begin(), order.end(), 0);
  std::sort(order.begin(), order.end(), [&](size_t a, size_t b) {
    return maps.originalBCs[a] < maps.originalBCs[b];
  });

  maps.indexMap.assign(n, -1);
  Int_t newIdx = -1;
  ULong64_t prev = ULong64_t(-1);
  for (auto oldIdx : order) {
    ULong64_t val = maps.originalBCs[oldIdx];
    if (newIdx < 0 || val != prev) {
      ++newIdx;
      prev = val;
      maps.uniqueBCs.push_back(val);
    }
    maps.indexMap[oldIdx] = newIdx;
    maps.newIndexOrigins[newIdx].push_back(oldIdx);
  }
  std::cout << "    BCMaps: oldEntries=" << n
            << " unique=" << maps.uniqueBCs.size() << "\n";
  return maps;
}

// ----------------- small helper used for BC/flags copy -----------------
/*
  copyTreeSimple:
   - inTree: input tree (assumed POD-only of types Int_t, ULong64_t, UChar_t)
   - entryMap: list of input-entry indices to use, in desired output order;
  (size_t)-1 entries are skipped
   - outName: name for the output tree
*/
static TTree *copyTreeSimple(TTree *inTree, const std::vector<size_t> &entryMap,
                             const char *outName = nullptr) {
  if (!inTree)
    return nullptr;
  TString tname = outName ? outName : inTree->GetName();
  TTree *outTree = new TTree(tname, "rebuilt tree");

  std::vector<void *> inBufs, outBufs;
  std::vector<TBranch *> inBranches;
  std::vector<TString> types;
  std::vector<TString> leafCodes;
  std::vector<TString> bnames;

  for (auto brObj : *inTree->GetListOfBranches()) {
    TBranch *br = (TBranch *)brObj;
    TString bname = br->GetName();
    TLeaf *leaf = (TLeaf *)br->GetListOfLeaves()->At(0);
    if (!leaf)
      continue;
    TString type = leaf->GetTypeName();

    void *inBuf = nullptr;
    void *outBuf = nullptr;
    TString leafCode;

    if (type == "Int_t") {
      inBuf = new Int_t;
      outBuf = new Int_t;
      leafCode = "I";
    } else if (type == "ULong64_t") {
      inBuf = new ULong64_t;
      outBuf = new ULong64_t;
      leafCode = "l";
    } else if (type == "UChar_t") {
      inBuf = new UChar_t;
      outBuf = new UChar_t;
      leafCode = "b";
    } else {
      std::cerr << "Unsupported branch type " << type << " in "
                << inTree->GetName() << " branch " << bname << " — skipping\n";
      continue;
    }

    br->SetAddress(inBuf);
    outTree->Branch(bname, outBuf, bname + "/" + leafCode);

    inBufs.push_back(inBuf);
    outBufs.push_back(outBuf);
    inBranches.push_back(br);
    types.push_back(type);
    leafCodes.push_back(leafCode);
    bnames.push_back(bname);
  }

  // fill using entryMap (representative input indices)
  for (size_t idx : entryMap) {
    if (idx == (size_t)-1)
      continue;
    inTree->GetEntry((Long64_t)idx);
    for (size_t ib = 0; ib < inBranches.size(); ++ib) {
      if (types[ib] == "Int_t")
        *(Int_t *)outBufs[ib] = *(Int_t *)inBufs[ib];
      else if (types[ib] == "ULong64_t")
        *(ULong64_t *)outBufs[ib] = *(ULong64_t *)inBufs[ib];
      else if (types[ib] == "UChar_t")
        *(UChar_t *)outBufs[ib] = *(UChar_t *)inBufs[ib];
    }
    outTree->Fill();
  }

  return outTree;
}

// ----------------- Rebuild BCs and Flags (refactored) -----------------
void rebuildBCsAndFlags(TDirectory *dirIn, TDirectory *dirOut, TTree *&outBCs,
                        BCMaps &maps) {
  std::cout << "------------------------------------------------\n";
  std::cout << "Rebuild BCs+flags in " << dirIn->GetName() << "\n";

  // find O2bc_* (pick first matching) and O2bcflag
  TTree *treeBCs = nullptr;
  TTree *treeFlags = nullptr;

  for (auto keyObj : *dirIn->GetListOfKeys()) {
    TKey *key = (TKey *)keyObj;
    TObject *obj = dirIn->Get(key->GetName());
    if (!obj)
      continue;
    if (!obj->InheritsFrom(TTree::Class()))
      continue;
    TTree *t = (TTree *)obj;
    if (isBCtree(t->GetName())) {
      treeBCs = t;
    } else if (isFlagsTree(t->GetName())) {
      treeFlags = t;
    }
  }

  if (!treeBCs) {
    std::cerr << "  No BCs tree found in " << dirIn->GetName()
              << " — skipping\n";
    outBCs = nullptr;
    return;
  }

  // build maps (dedupe/sort)
  maps = buildBCMaps(treeBCs);

  // build representative entryMap: one input entry per new BC index (use first
  // contributor)
  std::vector<size_t> entryMap(maps.uniqueBCs.size(), (size_t)-1);
  for (size_t newIdx = 0; newIdx < maps.uniqueBCs.size(); ++newIdx) {
    const auto &vec = maps.newIndexOrigins.at(newIdx);
    if (!vec.empty())
      entryMap[newIdx] = vec.front();
  }

  dirOut->cd();
  // copy BCs tree using representative entries
  outBCs = copyTreeSimple(treeBCs, entryMap, treeBCs->GetName());
  if (outBCs) {
    outBCs->SetDirectory(dirOut);
    outBCs->Write();
    std::cout << "   Wrote " << outBCs->GetName() << " with "
              << outBCs->GetEntries() << " entries\n";
  }

  // copy flags if present
  if (treeFlags) {
    TTree *outFlags = copyTreeSimple(treeFlags, entryMap, treeFlags->GetName());
    if (outFlags) {
      outFlags->SetDirectory(dirOut);
      outFlags->Write();
      std::cout << "   Wrote " << outFlags->GetName() << " with "
                << outFlags->GetEntries() << " entries\n";
    }
  }
}

// ----------------- payload rewriting with VLA support -----------------
struct SortKey {
  Long64_t entry;
  Long64_t newBC;
};

static bool isVLA(TBranch *br) {
  if (!br)
    return false;
  TLeaf *leaf = (TLeaf *)br->GetListOfLeaves()->At(0);
  return leaf && leaf->GetLeafCount();
}

// This is the VLA-aware rewritePayloadSorted implementation (keeps previous
// tested behavior)
static void rewritePayloadSorted(TDirectory *dirIn, TDirectory *dirOut,
                                 const BCMaps &maps) {
  std::unordered_set<std::string> skipNames; // for count branches
  TIter it(dirIn->GetListOfKeys());
  while (TKey *k = (TKey *)it()) {
    if (TString(k->GetClassName()) != "TTree")
      continue;
    std::unique_ptr<TObject> holder(k->ReadObj()); // keep alive
    TTree *src = dynamic_cast<TTree *>(holder.get());
    if (!src)
      continue;
    const char *tname = src->GetName();

    if (isBCtree(tname) || isFlagsTree(tname)) {
      std::cout << "    skipping BC/flag tree " << tname << "\n";
      continue;
    }

    const char *idxName = findIndexBranchName(src);
    if (!idxName) {
      dirOut->cd();
      std::cout << "    [copy] " << tname << " (no index) -> cloning\n";
      TTree *c = src->CloneTree(-1, "fast");
      c->SetDirectory(dirOut);
      c->Write();
      continue;
    }

    std::cout << "    [proc] reindex+SORT " << tname << " (index=" << idxName
              << ")\n";
    // detect index type and bind input buffer
    TBranch *inIdxBr = src->GetBranch(idxName);
    if (!inIdxBr) {
      std::cerr << "      ERR no index branch found\n";
      continue;
    }
    TLeaf *idxLeaf = (TLeaf *)inIdxBr->GetListOfLeaves()->At(0);
    TString idxType = idxLeaf->GetTypeName();

    enum class IdKind { kI, kUi, kS, kUs, kUnknown };
    IdKind idk = IdKind::kUnknown;
    Int_t oldI = 0, newI = 0;
    UInt_t oldUi = 0, newUi = 0;
    Short_t oldS = 0, newS = 0;
    UShort_t oldUs = 0, newUs = 0;

    if (idxType == "Int_t") {
      idk = IdKind::kI;
      inIdxBr->SetAddress(&oldI);
    } else if (idxType == "UInt_t") {
      idk = IdKind::kUi;
      inIdxBr->SetAddress(&oldUi);
    } else if (idxType == "Short_t") {
      idk = IdKind::kS;
      inIdxBr->SetAddress(&oldS);
    } else if (idxType == "UShort_t") {
      idk = IdKind::kUs;
      inIdxBr->SetAddress(&oldUs);
    } else {
      std::cerr << "      unsupported index type " << idxType
                << " -> cloning as-is\n";
      dirOut->cd();
      auto *c = src->CloneTree(-1, "fast");
      c->SetDirectory(dirOut);
      c->Write();
      continue;
    }

    // build keys vector
    Long64_t nEnt = src->GetEntries();
    std::vector<SortKey> keys;
    keys.reserve(nEnt);
    for (Long64_t i = 0; i < nEnt; ++i) {
      inIdxBr->GetEntry(i);
      Long64_t oldIdx = 0;
      switch (idk) {
      case IdKind::kI:
        oldIdx = oldI;
        break;
      case IdKind::kUi:
        oldIdx = oldUi;
        break;
      case IdKind::kS:
        oldIdx = oldS;
        break;
      case IdKind::kUs:
        oldIdx = oldUs;
        break;
      default:
        break;
      }
      Long64_t newBC = -1;
      if (oldIdx >= 0 && (size_t)oldIdx < maps.indexMap.size())
        newBC = maps.indexMap[(size_t)oldIdx];
      keys.push_back({i, newBC});
    }

    std::stable_sort(keys.begin(), keys.end(),
                     [](const SortKey &a, const SortKey &b) {
                       bool ai = (a.newBC < 0), bi = (b.newBC < 0);
                       if (ai != bi)
                         return !ai && bi; // valid first
                       if (a.newBC != b.newBC)
                         return a.newBC < b.newBC;
                       return a.entry < b.entry;
                     });

    // prepare output tree
    dirOut->cd();
    TTree *out = src->CloneTree(0, "fast");
    // map branches
    std::unordered_map<std::string, TBranch *> inBranches, outBranches;
    for (auto *bobj : *src->GetListOfBranches())
      inBranches[((TBranch *)bobj)->GetName()] = (TBranch *)bobj;
    for (auto *bobj : *out->GetListOfBranches())
      outBranches[((TBranch *)bobj)->GetName()] = (TBranch *)bobj;

    // allocate buffers and bind: scalars & VLAs
    std::vector<std::unique_ptr<BufBase>> scalarBuffers; // shared in/out
    std::vector<std::unique_ptr<BufBase>> vlaDataBuffers;
    std::vector<std::unique_ptr<BufBase>> vlaCountBuffers;
    std::vector<Long64_t> vlaMaxLens;
    std::vector<ScalarTag> vlaCountTags;
    // bind index branch in output to new variable
    TBranch *outIdxBr = out->GetBranch(idxName);
    switch (idk) {
    case IdKind::kI:
      outIdxBr->SetAddress(&newI);
      break;
    case IdKind::kUi:
      outIdxBr->SetAddress(&newUi);
      break;
    case IdKind::kS:
      outIdxBr->SetAddress(&newS);
      break;
    case IdKind::kUs:
      outIdxBr->SetAddress(&newUs);
      break;
    default:
      break;
    }
    skipNames.clear();
    skipNames.insert(idxName);

    // loop inBranches and bind
    for (auto &kv : inBranches) {
      const std::string bname = kv.first;
      if (skipNames.count(bname))
        continue;
      TBranch *inBr = kv.second;
      TBranch *ouBr = outBranches.count(bname) ? outBranches[bname] : nullptr;
      if (!ouBr) {
        std::cerr << "      [warn] no out branch for " << bname << " -> skip\n";
        continue;
      }
      TLeaf *leaf = (TLeaf *)inBr->GetListOfLeaves()->At(0);
      if (!leaf) {
        std::cerr << "      [warn] branch w/o leaf " << bname << "\n";
        continue;
      }

      if (!isVLA(inBr)) {
        // scalar
        ScalarTag tag = leafType(leaf);
        if (tag == ScalarTag::kUnknown) {
          std::cerr << "      [warn] unknown scalar type "
                    << leaf->GetTypeName() << " for " << bname << "\n";
          continue;
        }
        auto sb = bindScalarBranch(inBr, ouBr, tag);
        if (sb)
          scalarBuffers.emplace_back(std::move(sb));
      } else {
        // VLA -> find count leaf & branch
        TLeaf *cntLeaf = leaf->GetLeafCount();
        if (!cntLeaf) {
          std::cerr << "      [warn] VLA " << bname
                    << " has no count leaf -> skip\n";
          continue;
        }
        TBranch *inCnt = cntLeaf->GetBranch();
        TBranch *outCnt = outBranches.count(inCnt->GetName())
                              ? outBranches[inCnt->GetName()]
                              : nullptr;
        if (!outCnt) {
          std::cerr << "      [warn] missing out count branch "
                    << inCnt->GetName() << " for VLA " << bname << "\n";
          continue;
        }
        // avoid double-binding count branch as scalar later
        skipNames.insert(inCnt->GetName());
        // detect tags
        ScalarTag dataTag = leafType(leaf);
        ScalarTag cntTag = leafType(cntLeaf);
        if (dataTag == ScalarTag::kUnknown || cntTag == ScalarTag::kUnknown) {
          std::cerr << "      [warn] unsupported VLA types for " << bname
                    << "\n";
          continue;
        }
        // prescan max len
        Long64_t maxLen = prescanMaxLen(src, inCnt, cntTag);
        if (maxLen <= 0)
          maxLen = leaf->GetMaximum();
        if (maxLen <= 0)
          maxLen = 1;
        // bind typed
        std::unique_ptr<BufBase> countBufLocal;
        std::unique_ptr<BufBase> dataBufLocal;
        switch (dataTag) {
        case ScalarTag::kInt:
          dataBufLocal = bindArrayTyped<Int_t>(inBr, ouBr, inCnt, outCnt,
                                               cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kUInt:
          dataBufLocal = bindArrayTyped<UInt_t>(inBr, ouBr, inCnt, outCnt,
                                                cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kShort:
          dataBufLocal = bindArrayTyped<Short_t>(inBr, ouBr, inCnt, outCnt,
                                                 cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kUShort:
          dataBufLocal = bindArrayTyped<UShort_t>(
              inBr, ouBr, inCnt, outCnt, cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kLong64:
          dataBufLocal = bindArrayTyped<Long64_t>(
              inBr, ouBr, inCnt, outCnt, cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kULong64:
          dataBufLocal = bindArrayTyped<ULong64_t>(
              inBr, ouBr, inCnt, outCnt, cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kFloat:
          dataBufLocal = bindArrayTyped<Float_t>(inBr, ouBr, inCnt, outCnt,
                                                 cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kDouble:
          dataBufLocal = bindArrayTyped<Double_t>(
              inBr, ouBr, inCnt, outCnt, cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kChar:
          dataBufLocal = bindArrayTyped<Char_t>(inBr, ouBr, inCnt, outCnt,
                                                cntTag, maxLen, countBufLocal);
          break;
        case ScalarTag::kUChar:
          dataBufLocal = bindArrayTyped<UChar_t>(inBr, ouBr, inCnt, outCnt,
                                                 cntTag, maxLen, countBufLocal);
          break;
        default:
          break;
        }
        if (dataBufLocal)
          vlaDataBuffers.emplace_back(std::move(dataBufLocal));
        if (countBufLocal) {
          vlaCountBuffers.emplace_back(std::move(countBufLocal));
          vlaMaxLens.push_back(maxLen);
          vlaCountTags.push_back(cntTag);
        }
      }
    } // end for branches

    // Now fill out in sorted order. For each key: src->GetEntry(entry) -> clamp
    // counts -> set new index -> out->Fill()
    Long64_t changed = 0;
    for (const auto &sk : keys) {
      src->GetEntry(sk.entry);

      // clamp count buffers before fill
      for (size_t ic = 0; ic < vlaCountBuffers.size(); ++ic) {
        void *p = vlaCountBuffers[ic]->ptr();
        Long64_t cnt = 0;
        switch (vlaCountTags[ic]) {
        case ScalarTag::kInt:
          cnt = *(Int_t *)p;
          break;
        case ScalarTag::kUInt:
          cnt = *(UInt_t *)p;
          break;
        case ScalarTag::kShort:
          cnt = *(Short_t *)p;
          break;
        case ScalarTag::kUShort:
          cnt = *(UShort_t *)p;
          break;
        case ScalarTag::kLong64:
          cnt = *(Long64_t *)p;
          break;
        case ScalarTag::kULong64:
          cnt = *(ULong64_t *)p;
          break;
        default:
          cnt = *(Int_t *)p;
          break;
        }
        if (cnt < 0)
          cnt = 0;
        if (cnt > vlaMaxLens[ic]) {
          std::cerr << "WARNING: clamping VLA count " << cnt << " to max "
                    << vlaMaxLens[ic] << " for tree " << tname << "\n";
          // write back
          if (vlaMaxLens[ic] <= std::numeric_limits<int>::max()) {
            *(Int_t *)p = (Int_t)vlaMaxLens[ic];
          } else {
            *(Long64_t *)p = (Long64_t)vlaMaxLens[ic];
          }
        }
      }

      // set new index value in out buffer
      switch (idk) {
      case IdKind::kI: {
        Int_t prev = oldI;
        newI = (sk.newBC >= 0 ? (Int_t)sk.newBC : -1);
        if (newI != prev)
          ++changed;
      } break;
      case IdKind::kUi: {
        UInt_t prev = oldUi;
        newUi = (sk.newBC >= 0 ? (UInt_t)sk.newBC : 0u);
        if (newUi != prev)
          ++changed;
      } break;
      case IdKind::kS: {
        Short_t prev = oldS;
        newS = (sk.newBC >= 0 ? (Short_t)sk.newBC : (Short_t)-1);
        if (newS != prev)
          ++changed;
      } break;
      case IdKind::kUs: {
        UShort_t prev = oldUs;
        newUs = (sk.newBC >= 0 ? (UShort_t)sk.newBC : (UShort_t)0);
        if (newUs != prev)
          ++changed;
      } break;
      default:
        break;
      }

      out->Fill();
    }

    std::cout << "      wrote " << out->GetEntries() << " rows; remapped "
              << changed << " index values; sorted\n";
    out->Write();
  } // end while keys in dir

  // non-tree objects: copy as-is (but for TMap use WriteTObject to preserve
  // class)
  it.Reset();
  while (TKey *k = (TKey *)it()) {
    if (TString(k->GetClassName()) == "TTree")
      continue;
    TObject *obj = k->ReadObj();
    dirOut->cd();
    if (obj->IsA()->InheritsFrom(TMap::Class())) {
      std::cout << "    Copying TMap " << k->GetName() << " as a whole\n";
      dirOut->WriteTObject(obj, k->GetName(), "Overwrite");
    } else {
      obj->Write(k->GetName(), TObject::kOverwrite);
    }
  }
}

// ----------------- per-DF driver -----------------
static void processDF(TDirectory *dIn, TDirectory *dOut) {
  std::cout << "------------------------------------------------\n";
  std::cout << "Processing DF: " << dIn->GetName() << "\n";

  // 1) rebuild BCs & flags -> maps
  TTree *bcOut = nullptr;
  BCMaps maps;
  rebuildBCsAndFlags(dIn, dOut, bcOut, maps);

  if (!bcOut) {
    std::cout << "  No BCs -> deep copying directory\n";
    TIter it(dIn->GetListOfKeys());
    while (TKey *k = (TKey *)it()) {
      TObject *obj = k->ReadObj();
      dOut->cd();
      if (obj->InheritsFrom(TTree::Class())) {
        TTree *t = (TTree *)obj;
        TTree *c = t->CloneTree(-1, "fast");
        c->SetDirectory(dOut);
        c->Write();
      } else {
        if (obj->IsA()->InheritsFrom(TMap::Class())) {
          dOut->WriteTObject(obj, k->GetName(), "Overwrite");
        } else {
          obj->Write(k->GetName(), TObject::kOverwrite);
        }
      }
    }
    return;
  }

  // 2) rewrite payload tables (reindex+sort)
  rewritePayloadSorted(dIn, dOut, maps);

  std::cout << "Finished DF: " << dIn->GetName() << "\n";
}

// ----------------- top-level driver -----------------
void AODBcRewriter(const char *inFileName = "AO2D.root",
                   const char *outFileName = "AO2D_rewritten.root") {
  std::cout << "Opening input file: " << inFileName << "\n";
  std::unique_ptr<TFile> fin(TFile::Open(inFileName, "READ"));
  if (!fin || fin->IsZombie()) {
    std::cerr << "ERROR opening input\n";
    return;
  }

  int algo = fin->GetCompressionAlgorithm();
  int lvl = fin->GetCompressionLevel();
  std::cout << "Input compression: algo=" << algo << " level=" << lvl << "\n";

  // create output applying same compression level when available
#if ROOT_VERSION_CODE >= ROOT_VERSION(6, 30, 0)
  std::unique_ptr<TFile> fout(TFile::Open(outFileName, "RECREATE", "", lvl));
#else
  std::unique_ptr<TFile> fout(TFile::Open(outFileName, "RECREATE"));
#endif
  if (!fout || fout->IsZombie()) {
    std::cerr << "ERROR creating output\n";
    return;
  }
  fout->SetCompressionAlgorithm(algo);
  fout->SetCompressionLevel(lvl);

  // top-level keys
  TIter top(fin->GetListOfKeys());
  while (TKey *key = (TKey *)top()) {
    TString name = key->GetName();
    TObject *obj = key->ReadObj();
    if (obj->InheritsFrom(TDirectory::Class()) && isDF(name)) {
      std::cout << "Found DF folder: " << name << "\n";
      TDirectory *din = (TDirectory *)obj;
      TDirectory *dout = fout->mkdir(name);
      processDF(din, dout);
    } else {
      fout->cd();
      if (obj->IsA()->InheritsFrom(TMap::Class())) {
        std::cout << "Copying top-level TMap: " << name << "\n";
        fout->WriteTObject(obj, name, "Overwrite");
      } else {
        std::cout << "Copying top-level object: " << name << " ["
                  << obj->ClassName() << "]\n";
        obj->Write(name, TObject::kOverwrite);
      }
    }
  }

  fout->Write("", TObject::kOverwrite);
  fout->Close();
  fin->Close();
  std::cout << "All done. Output written to " << outFileName << "\n";
}
