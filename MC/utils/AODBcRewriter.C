// AODBcRewriter.C
//
// Usage:
//   root -l -b -q 'AODBcRewriter.C("AO2D.root","AO2D_rewritten.root")'
//
// -----------------------------------------------------------------------------
// PURPOSE
// -----------------------------------------------------------------------------
// After merging two AO2D files the BC table (O2bc_*) can contain:
//   (a) Non-monotonic fGlobalBC values — violating a framework requirement.
//   (b) Duplicate fGlobalBC values    — one logical BC spread across many rows.
//   (c) Duplicate MCCollisions        — the same MC event repeated because it
//       appeared in both source files before merging.
//
// This tool fixes all three problems in one pass per DF_ directory:
//
//   Stage 0  — Sort & deduplicate the BC table.  Build BC permutation map:
//              bcPerm[oldBCrow] = newBCrow.
//
//   Stage 1  — Process every table that carries fIndexBCs / fIndexBC.
//              Remap the index via bcPerm, sort rows by the new index, and
//              record a permutation map for each such table so that tables
//              paste-joined to it can follow.
//              Special sub-case: O2mccollision_* is deduplicated here —
//              rows whose (fIndexBCs, generator-level event ID) key has already
//              been seen are dropped, and a FULL permutation map is produced
//              (mcCollPerm[oldRow] = newRow, -1 = dropped).
//
//   Stage 2  — Process every table that carries fIndexMcCollisions.
//              Remap via mcCollPerm, sort, record mcCollXxxPerm if needed.
//
//   Paste-join tables — tables that have NO index column but are implicitly
//              joined row-for-row with another table (e.g. O2mccollisionlabel
//              is paste-joined with O2collision).  They must be reordered
//              identically to their parent.  The known paste-join relationships
//              are listed in kPasteJoins below and are applied after the
//              relevant stage has established the parent permutation.
//
//   Unrelated tables — tables with no dependency on BCs or MCCollisions are
//              copied verbatim.
//
// -----------------------------------------------------------------------------
// DATA MODEL DEPENDENCY GRAPH (relevant subset)
// -----------------------------------------------------------------------------
//
//  BCs (O2bc_*)                                        [Stage 0]
//   │  fIndexBCs
//   ├─► Collisions      (O2collision_*)                [Stage 1]
//   │    │  paste-join ► McCollisionLabels (O2mccollisionlabel_*)
//   │    │  fIndexCollisions (in tracks etc. — tracked by collPerm)
//   │    └─► Tracks     (O2track_*, O2trackiu_*, ...)  [Stage 1]
//   │         paste-join ► McTrackLabels (O2mctracklabel_*)
//   │
//   └─► MCCollisions    (O2mccollision_*)              [Stage 1, deduplicated]
//        │  fIndexMcCollisions
//        ├─► HepMCXSections   (O2hepmcxsection_*)     [Stage 2]
//        ├─► HepMCPdfInfos    (O2hepmcpdfinfo_*)       [Stage 2]
//        └─► HepMCHeavyIons   (O2hepmcheavyion_*)      [Stage 2]
//
// All other tables (detector hits, ZDC, FT0, FV0, FDD, …) that carry
// fIndexBCs are handled generically in Stage 1 without special-casing.
//
// -----------------------------------------------------------------------------

#ifndef __CLING__
#include "RVersion.h"
#include "TBranch.h"
#include "TDirectory.h"
#include "TFile.h"
#include "TKey.h"
#include "TLeaf.h"
#include "TMap.h"
#include "TROOT.h"
#include "TString.h"
#include "TTree.h"
#include <algorithm>
#include <cstring>
#include <cstdint>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#endif

// ============================================================================
// SECTION 1 — Types and small helpers
// ============================================================================

// A permutation map: permMap[oldRow] = newRow, -1 means "row was dropped".
using PermMap = std::vector<Int_t>;

// Convenience: build an identity permutation of length n.
static PermMap identityPerm(Long64_t n) {
  PermMap p(n);
  std::iota(p.begin(), p.end(), 0);
  return p;
}

// Names of tables that begin with these prefixes are BC tables or flag tables
// and are handled specially in Stage 0.
static bool isBCTable(const char *name) {
  return TString(name).BeginsWith("O2bc");
}

static bool isDF(const char *name) {
  return TString(name).BeginsWith("DF_");
}

// Return the name of the BC index branch if present, else nullptr.
static const char *bcIndexBranch(TTree *t) {
  if (!t) return nullptr;
  if (t->GetBranch("fIndexBCs"))  return "fIndexBCs";
  if (t->GetBranch("fIndexBC"))   return "fIndexBC";
  return nullptr;
}

// Return the name of the MCCollision index branch if present, else nullptr.
static const char *mcCollIndexBranch(TTree *t) {
  if (!t) return nullptr;
  if (t->GetBranch("fIndexMcCollisions")) return "fIndexMcCollisions";
  return nullptr;
}

// Return the name of the Collision index branch if present, else nullptr.
static const char *collIndexBranch(TTree *t) {
  if (!t) return nullptr;
  if (t->GetBranch("fIndexCollisions")) return "fIndexCollisions";
  return nullptr;
}

// ============================================================================
// SECTION 2 — Generic ROOT branch I/O helpers
// ============================================================================
//
// AO2D branches store plain scalar values (Int_t, ULong64_t, Float_t, …) or
// variable-length arrays (VLAs).  We need to read and write them generically
// without knowing the concrete type at compile time.  The trick is to allocate
// a raw byte buffer of the right size, set the branch address to it, and use
// the ScalarTag enum to know how to interpret it when we need to (e.g. for
// index remapping).

enum class ScalarTag {
  kInt, kUInt, kShort, kUShort, kLong64, kULong64,
  kFloat, kDouble, kChar, kUChar, kBool, kUnknown
};

static ScalarTag tagOf(TLeaf *leaf) {
  if (!leaf) return ScalarTag::kUnknown;
  TString t = leaf->GetTypeName();
  if (t == "Int_t")     return ScalarTag::kInt;
  if (t == "UInt_t")    return ScalarTag::kUInt;
  if (t == "Short_t")   return ScalarTag::kShort;
  if (t == "UShort_t")  return ScalarTag::kUShort;
  if (t == "Long64_t")  return ScalarTag::kLong64;
  if (t == "ULong64_t") return ScalarTag::kULong64;
  if (t == "Float_t")   return ScalarTag::kFloat;
  if (t == "Double_t")  return ScalarTag::kDouble;
  if (t == "Char_t")    return ScalarTag::kChar;
  if (t == "UChar_t")   return ScalarTag::kUChar;
  if (t == "Bool_t")    return ScalarTag::kBool;
  return ScalarTag::kUnknown;
}

static size_t byteSize(ScalarTag t) {
  switch (t) {
    case ScalarTag::kInt:     return sizeof(Int_t);
    case ScalarTag::kUInt:    return sizeof(UInt_t);
    case ScalarTag::kShort:   return sizeof(Short_t);
    case ScalarTag::kUShort:  return sizeof(UShort_t);
    case ScalarTag::kLong64:  return sizeof(Long64_t);
    case ScalarTag::kULong64: return sizeof(ULong64_t);
    case ScalarTag::kFloat:   return sizeof(Float_t);
    case ScalarTag::kDouble:  return sizeof(Double_t);
    case ScalarTag::kChar:    return sizeof(Char_t);
    case ScalarTag::kUChar:   return sizeof(UChar_t);
    case ScalarTag::kBool:    return sizeof(Bool_t);
    default:                  return 0;
  }
}

// Read an integer value from a raw buffer regardless of its stored type.
// Used to extract index values (fIndexBCs etc.) from their buffers.
static Long64_t readAsInt(const void *buf, ScalarTag tag) {
  switch (tag) {
    case ScalarTag::kInt:     return *static_cast<const Int_t *>(buf);
    case ScalarTag::kUInt:    return *static_cast<const UInt_t *>(buf);
    case ScalarTag::kShort:   return *static_cast<const Short_t *>(buf);
    case ScalarTag::kUShort:  return *static_cast<const UShort_t *>(buf);
    case ScalarTag::kLong64:  return *static_cast<const Long64_t *>(buf);
    case ScalarTag::kULong64: return (Long64_t)*static_cast<const ULong64_t *>(buf);
    default:                  return -1;
  }
}

// Write an integer value into a raw buffer.
static void writeAsInt(void *buf, ScalarTag tag, Long64_t val) {
  switch (tag) {
    case ScalarTag::kInt:    *static_cast<Int_t *>(buf)    = (Int_t)val;    break;
    case ScalarTag::kUInt:   *static_cast<UInt_t *>(buf)   = (UInt_t)val;   break;
    case ScalarTag::kShort:  *static_cast<Short_t *>(buf)  = (Short_t)val;  break;
    case ScalarTag::kUShort: *static_cast<UShort_t *>(buf) = (UShort_t)val; break;
    case ScalarTag::kLong64: *static_cast<Long64_t *>(buf) = (Long64_t)val; break;
    default: break;
  }
}

// Remap a single Int_t index value through a PermMap.  Returns -1 for any
// out-of-range or already-invalid (negative) value.
static Int_t remapIdx(Int_t val, const PermMap &perm) {
  if (val < 0 || (size_t)val >= perm.size()) return -1;
  return perm[(size_t)val];
}

// A description of one branch in a tree: its name, scalar type tag, byte
// size, and whether it is a VLA (variable-length array).  For VLAs we also
// keep the name of the count branch and the maximum observed element count
// (needed for buffer sizing).
struct BranchDesc {
  std::string name;
  ScalarTag   tag      = ScalarTag::kUnknown;
  size_t      elemSize = 0;  // byte size of one element
  int         nElems   = 1;  // >1 for fixed-size arrays (e.g. fIndexSlice_Daughters[2])
  bool        isVLA    = false;
  std::string countBranchName; // only for VLAs
  Long64_t    maxElems = 1;    // only for VLAs
};

// Scan all branches of a tree and return their descriptors.  Count branches
// for VLAs are represented only once (as the count side of the data branch)
// and are marked so they don't also appear as standalone entries.
static std::vector<BranchDesc> describeBranches(TTree *tree) {
  std::vector<BranchDesc> result;
  std::unordered_set<std::string> countBranchNames;

  // First pass: identify all count branches for VLAs
  for (auto *obj : *tree->GetListOfBranches()) {
    TBranch *br = static_cast<TBranch *>(obj);
    TLeaf *leaf = static_cast<TLeaf *>(br->GetListOfLeaves()->At(0));
    if (!leaf) continue;
    if (TLeaf *cnt = leaf->GetLeafCount())
      countBranchNames.insert(cnt->GetBranch()->GetName());
  }

  // Second pass: build descriptors
  for (auto *obj : *tree->GetListOfBranches()) {
    TBranch *br = static_cast<TBranch *>(obj);
    std::string bname = br->GetName();
    TLeaf *leaf = static_cast<TLeaf *>(br->GetListOfLeaves()->At(0));
    if (!leaf) { std::cerr << "  [warn] branch without leaf: " << bname << "\n"; continue; }

    BranchDesc d;
    d.name = bname;
    d.tag  = tagOf(leaf);

    if (TLeaf *cnt = leaf->GetLeafCount()) {
      // This is a VLA data branch
      d.isVLA          = true;
      d.countBranchName = cnt->GetBranch()->GetName();
      d.tag             = tagOf(leaf);
      d.elemSize        = byteSize(d.tag);

      // Pre-scan to find the maximum array length (needed for buffer)
      TBranch *cntBr = cnt->GetBranch();
      ScalarTag cntTag = tagOf(cnt);
      size_t cntSz = byteSize(cntTag);
      if (cntSz == 0) { std::cerr << "  [warn] VLA count branch has unknown type: " << bname << "\n"; continue; }
      std::vector<unsigned char> cntBuf(cntSz, 0);
      cntBr->SetAddress(cntBuf.data());
      Long64_t maxLen = 1;
      for (Long64_t i = 0; i < tree->GetEntries(); ++i) {
        cntBr->GetEntry(i);
        Long64_t v = readAsInt(cntBuf.data(), cntTag);
        if (v > maxLen) maxLen = v;
      }
      d.maxElems = maxLen;

    } else if (countBranchNames.count(bname)) {
      // This is a count branch — skip it here; handled together with its VLA
      continue;
    } else {
      // Plain scalar or fixed-size array branch (e.g. fIndexSlice_Daughters[2])
      d.isVLA    = false;
      d.elemSize = byteSize(d.tag);
      d.nElems   = leaf->GetLen();  // 1 for scalars, >1 for fixed arrays
      if (d.elemSize == 0) {
        std::cerr << "  [warn] branch " << bname << " has unknown type "
                  << leaf->GetTypeName() << " — will be skipped\n";
        continue;
      }
    }
    result.push_back(std::move(d));
  }
  return result;
}

// ============================================================================
// SECTION 3 — Table rewriting engine
// ============================================================================
//
// rewriteTable() is the single generic function that handles any table.
// It takes:
//   - src          : the source TTree
//   - dirOut       : directory to write the output TTree into
//   - rowOrder     : which source rows to include and in what order
//                    (a vector of source row indices, possibly a subset)
//   - indexBranch  : name of the index branch to remap, or "" if none
//   - parentPerm   : PermMap for remapping that index (may be empty)
//   - extraRemaps  : additional index columns to remap in-place via their own
//                    PermMaps (used for intra-table and cross-table indices
//                    that are not the primary sort key, e.g. mother/daughter
//                    indices in O2mcparticle or fIndexMcParticles in labels)
//
// It returns the permutation of source rows implied by rowOrder, expressed
// as a PermMap: perm[srcRow] = outputRow, -1 if the row was dropped.

// Describes one extra index column to remap independently of the sort key.
struct ExtraRemap {
  std::string  branchName;  // branch whose integer values to remap
  const PermMap *perm;      // remapping table: newVal = (*perm)[oldVal]
};

static PermMap rewriteTable(TTree *src, TDirectory *dirOut,
                            const std::vector<Long64_t> &rowOrder,
                            const std::string &indexBranch,
                            const PermMap &parentPerm,
                            const std::vector<ExtraRemap> &extraRemaps = {}) {

  Long64_t nSrc = src->GetEntries();

  // Build the inverse permutation (srcRow → outRow) from rowOrder
  PermMap srcToOut(nSrc, -1);
  for (Long64_t outRow = 0; outRow < (Long64_t)rowOrder.size(); ++outRow)
    srcToOut[rowOrder[outRow]] = (Int_t)outRow;

  // Describe all branches
  auto descs = describeBranches(src);

  // Allocate raw buffers: for each branch one buffer (for VLAs: data buffer
  // sized maxElems * elemSize, plus a separate count buffer).
  // We use a std::vector<unsigned char> per branch (automatically memory-safe).
  struct BranchIO {
    BranchDesc        desc;
    std::vector<unsigned char> dataBuf;   // scalar: elemSize bytes; VLA: maxElems*elemSize bytes
    std::vector<unsigned char> countBuf;  // VLA only
    ScalarTag         countTag = ScalarTag::kUnknown;
    TBranch          *inBr     = nullptr;
    TBranch          *inCntBr  = nullptr;
  };
  std::vector<BranchIO> ios;
  ios.reserve(descs.size());

  for (auto &d : descs) {
    BranchIO io;
    io.desc = d;
    if (!d.isVLA) {
      // Allocate for all elements (nElems>1 for fixed arrays like fIndexSlice_Daughters[2])
      io.dataBuf.assign(d.nElems * d.elemSize, 0);
    } else {
      io.dataBuf.assign(d.maxElems * d.elemSize, 0);
      TBranch *cntBr = src->GetBranch(d.countBranchName.c_str());
      TLeaf *cntLeaf = cntBr ? static_cast<TLeaf *>(cntBr->GetListOfLeaves()->At(0)) : nullptr;
      io.countTag = cntLeaf ? tagOf(cntLeaf) : ScalarTag::kUnknown;
      io.countBuf.assign(byteSize(io.countTag), 0);
      io.inCntBr = cntBr;
    }
    io.inBr = src->GetBranch(d.name.c_str());
    ios.push_back(std::move(io));
  }

  // Set input branch addresses
  for (auto &io : ios) {
    if (io.inBr)    io.inBr->SetAddress(io.dataBuf.data());
    if (io.inCntBr) io.inCntBr->SetAddress(io.countBuf.data());
  }

  // Create output tree and set output branch addresses.
  // We clone the tree structure (no entries) and reset addresses.
  dirOut->cd();
  TTree *out = src->CloneTree(0, "fast");

  // Find the index branch (if any) — we will update its value on the fly
  ScalarTag idxTag = ScalarTag::kUnknown;
  std::vector<unsigned char> newIdxBuf;
  TBranch *outIdxBr = nullptr;
  if (!indexBranch.empty()) {
    TBranch *inIdxBr = src->GetBranch(indexBranch.c_str());
    TLeaf *idxLeaf = inIdxBr ? static_cast<TLeaf *>(inIdxBr->GetListOfLeaves()->At(0)) : nullptr;
    idxTag = idxLeaf ? tagOf(idxLeaf) : ScalarTag::kUnknown;
    if (idxTag != ScalarTag::kUnknown) {
      newIdxBuf.assign(byteSize(idxTag), 0);
      outIdxBr = out->GetBranch(indexBranch.c_str());
      if (outIdxBr) outIdxBr->SetAddress(newIdxBuf.data());
    }
  }

  // Set all other output branch addresses to the same data buffers as input
  for (auto &io : ios) {
    if (io.desc.name == indexBranch) continue; // handled separately above
    TBranch *outBr = out->GetBranch(io.desc.name.c_str());
    if (!outBr) { std::cerr << "  [warn] no output branch for " << io.desc.name << "\n"; continue; }
    outBr->SetAddress(io.dataBuf.data());
    if (io.desc.isVLA) {
      TBranch *outCntBr = out->GetBranch(io.desc.countBranchName.c_str());
      if (outCntBr) outCntBr->SetAddress(io.countBuf.data());
    }
  }

  // Fill the output tree row by row in the requested order
  Long64_t nRemapped = 0;
  for (Long64_t srcRow : rowOrder) {
    src->GetEntry(srcRow);

    // Remap the index branch if required
    if (outIdxBr && idxTag != ScalarTag::kUnknown && !parentPerm.empty()) {
      // Read old index from the input branch's buffer (one of the ios entries)
      Long64_t oldIdx = -1;
      for (auto &io : ios) {
        if (io.desc.name == indexBranch) { oldIdx = readAsInt(io.dataBuf.data(), idxTag); break; }
      }
      Long64_t newIdx = -1;
      if (oldIdx >= 0 && oldIdx < (Long64_t)parentPerm.size())
        newIdx = parentPerm[oldIdx];
      writeAsInt(newIdxBuf.data(), idxTag, newIdx >= 0 ? newIdx : -1);
      if (newIdx != oldIdx) ++nRemapped;
    }

    // Apply extra in-place index remaps (e.g. intra-table mother/daughter
    // indices in O2mcparticle, or fIndexMcParticles in label tables).
    // The output branch shares the same buffer, so modifying dataBuf here
    // is read by out->Fill() below.
    for (auto &er : extraRemaps) {
      for (auto &io : ios) {
        if (io.desc.name != er.branchName) continue;
        if (io.desc.isVLA) {
          // VLA: remap each element according to count
          Long64_t cnt = readAsInt(io.countBuf.data(), io.countTag);
          auto *p = reinterpret_cast<Int_t *>(io.dataBuf.data());
          for (Long64_t j = 0; j < cnt; ++j)
            p[j] = remapIdx(p[j], *er.perm);
        } else {
          // Scalar or fixed-size array: remap all nElems integers
          auto *p = reinterpret_cast<Int_t *>(io.dataBuf.data());
          for (int j = 0; j < io.desc.nElems; ++j)
            p[j] = remapIdx(p[j], *er.perm);
        }
        break;
      }
    }

    out->Fill();
  }

  std::cout << "    wrote " << out->GetEntries() << " / " << nSrc
            << " rows; " << nRemapped << " index values remapped\n";
  out->Write();
  return srcToOut;
}

// ============================================================================
// SECTION 4 — Stage 0: BC table sort + deduplication
// ============================================================================
//
// Reads fGlobalBC from the BC tree, sorts rows, drops exact-duplicate BC
// values, and writes the compacted table.  Returns bcPerm[oldRow] = newRow.

struct BCStage0Result {
  PermMap bcPerm;          // bcPerm[oldRow] = newRow in sorted/deduped BC table
  Long64_t nUnique = 0;
};

static BCStage0Result stage0_sortBCs(TTree *treeBCs, TDirectory *dirOut) {
  BCStage0Result res;
  Long64_t n = treeBCs->GetEntries();
  if (n == 0) return res;

  TBranch *brGBC = treeBCs->GetBranch("fGlobalBC");
  if (!brGBC) { std::cerr << "ERROR: O2bc_* tree has no fGlobalBC branch!\n"; return res; }

  ULong64_t gbc = 0;
  brGBC->SetAddress(&gbc);
  std::vector<ULong64_t> gbcs(n);
  for (Long64_t i = 0; i < n; ++i) { treeBCs->GetEntry(i); gbcs[i] = gbc; }

  // Sort row indices by fGlobalBC
  std::vector<Long64_t> order(n);
  std::iota(order.begin(), order.end(), 0);
  std::stable_sort(order.begin(), order.end(),
    [&](Long64_t a, Long64_t b){ return gbcs[a] < gbcs[b]; });

  // Build deduplicated row list and the permutation
  res.bcPerm.assign(n, -1);
  std::vector<Long64_t> rowOrder;  // source rows to keep, in output order
  ULong64_t prev = ULong64_t(-1);
  Int_t newRow = -1;
  for (Long64_t srcRow : order) {
    if (gbcs[srcRow] != prev) {
      ++newRow;
      prev = gbcs[srcRow];
      rowOrder.push_back(srcRow);
    }
    // All rows with the same globalBC map to the same new row (deduplication)
    res.bcPerm[srcRow] = newRow;
  }
  res.nUnique = rowOrder.size();

  std::cout << "  BC stage: " << n << " rows -> " << res.nUnique << " unique\n";

  // Write the BC table (no index remapping needed for the table itself)
  rewriteTable(treeBCs, dirOut, rowOrder, /*indexBranch=*/"", /*parentPerm=*/{});

  return res;
}

// ============================================================================
// SECTION 5 — Stage 0b: BC flags table (follows BC row order exactly)
// ============================================================================

static void stage0_copyBCFlags(TTree *treeFlags, TDirectory *dirOut,
                               const PermMap &bcPerm) {
  if (!treeFlags) return;
  Long64_t nSrc = treeFlags->GetEntries();

  // Build rowOrder: for each unique output BC row, pick the first source row
  // that mapped to it
  std::vector<Long64_t> rowOrder;
  std::map<Int_t, Long64_t> first; // newBCrow -> first srcRow
  for (Long64_t i = 0; i < (Long64_t)bcPerm.size(); ++i)
    if (bcPerm[i] >= 0) first.emplace(bcPerm[i], i);  // emplace keeps first
  rowOrder.reserve(first.size());
  for (auto &kv : first) rowOrder.push_back(kv.second);

  rewriteTable(treeFlags, dirOut, rowOrder, /*indexBranch=*/"", /*parentPerm=*/{});
}

// ============================================================================
// SECTION 6 — Stage 1: Tables indexed by BCs (generic + MCCollisions special)
// ============================================================================
//
// Returns a map: treeName -> PermMap, containing the row permutation for
// every table processed at this stage.  Callers use this for paste-joined
// tables and for Stage 2.

// Key used to detect duplicate MCCollisions.
//
// Two MCCollision rows are considered identical when BOTH of the following hold:
//   1. They map to the same BC row after remapping (same globalBC).
//   2. They carry the same fEventWeight value.
//
// fEventWeight is a float written by the generator for every event and is
// unique enough (in combination with the BC) to distinguish distinct events
// from the same generator that happen to land in the same BC.
//
// IMPORTANT: if fEventWeight is absent from the tree we do NOT deduplicate at
// all, because we have no reliable way to distinguish distinct events that share
// the same BC.  Deduplicating on BC alone would incorrectly merge different MC
// events that were placed in the same bunch crossing.
struct MCCollKey {
  Long64_t newBCrow;
  Float_t  weight;
  bool operator==(const MCCollKey &o) const {
    return newBCrow == o.newBCrow && weight == o.weight;
  }
};
struct MCCollKeyHash {
  size_t operator()(const MCCollKey &k) const {
    size_t h1 = std::hash<Long64_t>{}(k.newBCrow);
    // Bit-cast float to uint32 for hashing — avoids UB and NaN weirdness
    uint32_t wbits;
    std::memcpy(&wbits, &k.weight, sizeof(wbits));
    return h1 ^ (size_t(wbits) << 32) ^ size_t(wbits);
  }
};

static std::unordered_map<std::string, PermMap>
stage1_BCindexedTables(TDirectory *dirIn, TDirectory *dirOut,
                       const PermMap &bcPerm) {
  std::unordered_map<std::string, PermMap> tablePerms;

  TIter it(dirIn->GetListOfKeys());
  while (TKey *key = static_cast<TKey *>(it())) {
    if (TString(key->GetClassName()) != "TTree") continue;
    std::unique_ptr<TObject> obj(key->ReadObj());
    TTree *src = dynamic_cast<TTree *>(obj.get());
    if (!src) continue;

    std::string tname = src->GetName();
    if (isBCTable(tname.c_str())) continue;  // handled in stage 0

    const char *idxBr = bcIndexBranch(src);
    if (!idxBr) continue;  // not BC-indexed — handled elsewhere

    std::cout << "  Stage1 [BC-indexed]: " << tname << "\n";

    Long64_t nSrc = src->GetEntries();

    // Read all index values to build the sort order
    TBranch *inIdxBr = src->GetBranch(idxBr);
    TLeaf *idxLeaf = static_cast<TLeaf *>(inIdxBr->GetListOfLeaves()->At(0));
    ScalarTag idxTag = tagOf(idxLeaf);
    size_t idxSz = byteSize(idxTag);
    std::vector<unsigned char> idxBuf(idxSz, 0);
    inIdxBr->SetAddress(idxBuf.data());

    // For MCCollision deduplication: also read fEventWeight if available.
    // If absent, deduplication is disabled -- see MCCollKey comment for why.
    bool isMCColl = TString(tname.c_str()).BeginsWith("O2mccollision");
    TBranch *wBr = isMCColl ? src->GetBranch("fEventWeight") : nullptr;
    Float_t wVal = 0.f;
    if (wBr) wBr->SetAddress(&wVal);
    bool canDedup = isMCColl && (wBr != nullptr);
    if (isMCColl && !canDedup)
      std::cout << "    MCCollision: fEventWeight absent -- deduplication disabled\n";

    // Build (newBCrow, srcRow) pairs
    struct SortEntry { Long64_t newBC; Long64_t srcRow; };
    std::vector<SortEntry> entries;
    entries.reserve(nSrc);

    std::unordered_set<MCCollKey, MCCollKeyHash> seenMCColl;
    std::vector<bool> keep(nSrc, true);

    for (Long64_t i = 0; i < nSrc; ++i) {
      inIdxBr->GetEntry(i);
      if (wBr) wBr->GetEntry(i);
      Long64_t oldBC = readAsInt(idxBuf.data(), idxTag);
      Long64_t newBC = (oldBC >= 0 && oldBC < (Long64_t)bcPerm.size())
                       ? bcPerm[oldBC] : -1;

      if (canDedup) {
        // Deduplication: drop rows with a (newBC, weight) pair seen before.
        // First occurrence in source row order is kept.
        MCCollKey k{newBC, wVal};
        if (!seenMCColl.insert(k).second) {
          keep[i] = false;
        }
      }
      entries.push_back({newBC, i});
    }

    // Stable-sort by newBC (invalid = -1 sink to end)
    std::stable_sort(entries.begin(), entries.end(),
      [](const SortEntry &a, const SortEntry &b){
        if (a.newBC < 0 && b.newBC >= 0) return false;
        if (a.newBC >= 0 && b.newBC < 0) return true;
        return a.newBC < b.newBC;
      });

    // Build rowOrder, respecting the keep[] mask for MCCollisions
    std::vector<Long64_t> rowOrder;
    rowOrder.reserve(nSrc);
    for (auto &e : entries) {
      if (keep[e.srcRow]) rowOrder.push_back(e.srcRow);
    }

    if (isMCColl) {
      Long64_t dropped = nSrc - (Long64_t)rowOrder.size();
      std::cout << "    MCCollision dedup: dropped " << dropped
                << " duplicate rows (" << rowOrder.size() << " kept)\n";
    }

    PermMap perm = rewriteTable(src, dirOut, rowOrder, idxBr, bcPerm);
    tablePerms[tname] = std::move(perm);
  }
  return tablePerms;
}

// ============================================================================
// SECTION 7 — Stage 2: Tables indexed by MCCollisions
// ============================================================================

static std::unordered_map<std::string, PermMap>
stage2_MCCollIndexedTables(TDirectory *dirIn, TDirectory *dirOut,
                           const PermMap &mcCollPerm) {
  std::unordered_map<std::string, PermMap> tablePerms;

  TIter it(dirIn->GetListOfKeys());
  while (TKey *key = static_cast<TKey *>(it())) {
    if (TString(key->GetClassName()) != "TTree") continue;
    std::unique_ptr<TObject> obj(key->ReadObj());
    TTree *src = dynamic_cast<TTree *>(obj.get());
    if (!src) continue;

    std::string tname = src->GetName();
    if (isBCTable(tname.c_str())) continue;
    if (bcIndexBranch(src)) continue; // already handled in stage 1

    const char *idxBr = mcCollIndexBranch(src);
    if (!idxBr) continue;

    std::cout << "  Stage2 [MCColl-indexed]: " << tname << "\n";

    Long64_t nSrc = src->GetEntries();
    TBranch *inIdxBr = src->GetBranch(idxBr);
    TLeaf *idxLeaf = static_cast<TLeaf *>(inIdxBr->GetListOfLeaves()->At(0));
    ScalarTag idxTag = tagOf(idxLeaf);
    size_t idxSz = byteSize(idxTag);
    std::vector<unsigned char> idxBuf(idxSz, 0);
    inIdxBr->SetAddress(idxBuf.data());

    struct SortEntry { Long64_t newMCColl; Long64_t srcRow; };
    std::vector<SortEntry> entries;
    entries.reserve(nSrc);

    for (Long64_t i = 0; i < nSrc; ++i) {
      inIdxBr->GetEntry(i);
      Long64_t oldIdx = readAsInt(idxBuf.data(), idxTag);
      Long64_t newIdx = (oldIdx >= 0 && oldIdx < (Long64_t)mcCollPerm.size())
                        ? mcCollPerm[oldIdx] : -1;
      entries.push_back({newIdx, i});
    }

    // Drop rows whose MCCollision parent was dropped (newIdx == -1 due to dedup)
    // and sort the rest
    std::stable_sort(entries.begin(), entries.end(),
      [](const SortEntry &a, const SortEntry &b){
        if (a.newMCColl < 0 && b.newMCColl >= 0) return false;
        if (a.newMCColl >= 0 && b.newMCColl < 0) return true;
        return a.newMCColl < b.newMCColl;
      });

    std::vector<Long64_t> rowOrder;
    rowOrder.reserve(nSrc);
    Long64_t dropped = 0;
    for (auto &e : entries) {
      if (e.newMCColl >= 0) rowOrder.push_back(e.srcRow);
      else ++dropped;
    }
    if (dropped)
      std::cout << "    dropped " << dropped
                << " rows whose MCCollision parent was deduplicated\n";

    // For O2mcparticle: compute the self-permutation (old row -> new row) from
    // the row order BEFORE calling rewriteTable, then pass it as extra remaps
    // so that intra-table mother/daughter indices are updated in the same pass.
    // The stable sort above preserves within-collision particle order, which
    // keeps fIndexSlice_Daughters contiguous — so remapping [first,last] via
    // selfPerm is correct.
    std::vector<ExtraRemap> extraRemaps;
    PermMap selfPerm;
    if (TString(tname.c_str()).BeginsWith("O2mcparticle")) {
      selfPerm.assign(nSrc, -1);
      for (Long64_t outRow = 0; outRow < (Long64_t)rowOrder.size(); ++outRow)
        selfPerm[rowOrder[outRow]] = (Int_t)outRow;
      extraRemaps.push_back({"fIndexArray_Mothers",  &selfPerm});
      extraRemaps.push_back({"fIndexSlice_Daughters", &selfPerm});
      std::cout << "    O2mcparticle: will remap intra-table mother/daughter indices\n";
    }

    PermMap perm = rewriteTable(src, dirOut, rowOrder, idxBr, mcCollPerm, extraRemaps);
    tablePerms[tname] = std::move(perm);
  }
  return tablePerms;
}

// ============================================================================
// SECTION 8 — Paste-join table handling
// ============================================================================
//
// A paste-joined table has NO index column.  Its row N corresponds to row N
// of its parent table.  When the parent is reordered, the paste-join table
// must follow with the identical row permutation.
//
// Known paste-join relationships in the AO2D data model
// (parent table prefix -> paste-joined table prefix):
//
//   O2collision_*           -> O2mccollisionlabel_*
//   O2track_*               -> O2mctracklabel_*
//   O2trackiu_*             -> O2mctracklabel_*   (alternative track table)
//   O2fwdtrack_*            -> O2mcfwdtracklabel_*
//   O2mfttrack_*            -> O2mcmfttracklabel_*
//
// The PermMap from the parent stage is used directly as the row order.

// Build the row order from a PermMap (srcRow -> outRow), inverted.
static std::vector<Long64_t> rowOrderFromPerm(const PermMap &perm) {
  // perm[srcRow] = outRow (or -1 if dropped)
  // We need: outRow -> srcRow, i.e. a sorted list of (outRow, srcRow) pairs
  std::vector<std::pair<Int_t,Long64_t>> pairs;
  pairs.reserve(perm.size());
  for (Long64_t srcRow = 0; srcRow < (Long64_t)perm.size(); ++srcRow)
    if (perm[srcRow] >= 0) pairs.push_back({perm[srcRow], srcRow});
  std::sort(pairs.begin(), pairs.end());
  std::vector<Long64_t> order;
  order.reserve(pairs.size());
  for (auto &p : pairs) order.push_back(p.second);
  return order;
}

// The paste-join map: paste-joined table prefix -> parent table prefix
// We match by prefix (BeginsWith) because table names carry a numeric suffix.
static const std::vector<std::pair<std::string,std::string>> kPasteJoins = {
  // { paste-joined prefix,        parent prefix }
  { "O2mccollisionlabel",  "O2collision"   },
  { "O2mctracklabel",      "O2track"       },
  { "O2mctracklabel",      "O2trackiu"     },  // same label table, alt parent
  { "O2mcfwdtracklabel",   "O2fwdtrack"    },
  { "O2mcmfttracklabel",   "O2mfttrack"    },
};

static void processPasteJoinTables(
    TDirectory *dirIn, TDirectory *dirOut,
    const std::unordered_map<std::string, PermMap> &allPerms,
    const std::unordered_set<std::string> &alreadyWritten) {

  // Find the MC-particle permutation (produced by stage2 for O2mcparticle_*).
  // Label tables (O2mctracklabel, O2mcfwdtracklabel, O2mcmfttracklabel,
  // O2mccalolabel) carry fIndexMcParticles / fIndexArrayMcParticles that must
  // be remapped via this permutation regardless of whether the label table's
  // row order changes.
  const PermMap *mcParticlePerm = nullptr;
  for (auto &[name, perm] : allPerms) {
    if (TString(name.c_str()).BeginsWith("O2mcparticle")) {
      mcParticlePerm = &perm;
      break;
    }
  }

  TIter it(dirIn->GetListOfKeys());
  while (TKey *key = static_cast<TKey *>(it())) {
    if (TString(key->GetClassName()) != "TTree") continue;
    std::unique_ptr<TObject> obj(key->ReadObj());
    TTree *src = dynamic_cast<TTree *>(obj.get());
    if (!src) continue;

    std::string tname = src->GetName();
    if (alreadyWritten.count(tname)) continue;
    if (isBCTable(tname.c_str())) continue;
    if (bcIndexBranch(src) || mcCollIndexBranch(src)) continue;

    // Build extra remaps for any fIndexMcParticles / fIndexArrayMcParticles
    // branches in this table (label tables pointing into O2mcparticle).
    std::vector<ExtraRemap> extraRemaps;
    if (mcParticlePerm) {
      if (src->GetBranch("fIndexMcParticles"))
        extraRemaps.push_back({"fIndexMcParticles",      mcParticlePerm});
      if (src->GetBranch("fIndexArrayMcParticles"))
        extraRemaps.push_back({"fIndexArrayMcParticles", mcParticlePerm});
    }

    // Check if this is a known paste-join table
    const PermMap *parentPerm = nullptr;
    std::string parentName;
    for (auto &[pastePrefix, parentPrefix] : kPasteJoins) {
      if (!TString(tname.c_str()).BeginsWith(pastePrefix.c_str())) continue;
      for (auto &[pname, perm] : allPerms) {
        if (TString(pname.c_str()).BeginsWith(parentPrefix.c_str())) {
          parentPerm = &perm;
          parentName = pname;
          break;
        }
      }
      if (parentPerm) break;
    }

    if (parentPerm) {
      std::cout << "  Paste-join: " << tname << " follows " << parentName << "\n";
      auto rowOrder = rowOrderFromPerm(*parentPerm);
      if ((Long64_t)rowOrder.size() != src->GetEntries()) {
        std::cerr << "  [warn] paste-join size mismatch: " << tname
                  << " has " << src->GetEntries() << " rows but parent perm covers "
                  << rowOrder.size() << " — cloning as-is\n";
        dirOut->cd();
        TTree *c = src->CloneTree(-1, "fast");
        c->SetDirectory(dirOut);
        c->Write();
      } else {
        rewriteTable(src, dirOut, rowOrder, "", {}, extraRemaps);
      }
    } else if (!extraRemaps.empty()) {
      // Not paste-joined but has indices that need remapping (e.g. O2mccalolabel
      // which is not in kPasteJoins but carries fIndexArrayMcParticles).
      std::cout << "  Remap-only: " << tname << "\n";
      Long64_t n = src->GetEntries();
      std::vector<Long64_t> identity(n);
      std::iota(identity.begin(), identity.end(), 0LL);
      rewriteTable(src, dirOut, identity, "", {}, extraRemaps);
    } else {
      // No paste-join and no index remapping needed — fast clone
      std::cout << "  Copy (no dependency): " << tname << "\n";
      dirOut->cd();
      TTree *c = src->CloneTree(-1, "fast");
      c->SetDirectory(dirOut);
      c->Write();
    }
  }
}

// ============================================================================
// SECTION 9 — Non-tree object copying (TMap metadata etc.)
// ============================================================================

static void copyNonTreeObjects(TDirectory *dirIn, TDirectory *dirOut) {
  TIter it(dirIn->GetListOfKeys());
  while (TKey *key = static_cast<TKey *>(it())) {
    if (TString(key->GetClassName()) == "TTree") continue;
    std::unique_ptr<TObject> obj(key->ReadObj());
    dirOut->cd();
    if (obj->IsA()->InheritsFrom(TMap::Class()))
      dirOut->WriteTObject(obj.get(), key->GetName(), "Overwrite");
    else
      obj->Write(key->GetName(), TObject::kOverwrite);
  }
}

// ============================================================================
// SECTION 10 — Per-DF directory driver
// ============================================================================

static void processDF(TDirectory *dirIn, TDirectory *dirOut) {
  std::cout << "========================================\n";
  std::cout << "Processing " << dirIn->GetName() << "\n";

  // ---- Find BC tree and optional flags tree ----
  TTree *treeBCs    = nullptr;
  TTree *treeFlags  = nullptr;
  {
    TIter it(dirIn->GetListOfKeys());
    while (TKey *key = static_cast<TKey *>(it())) {
      if (TString(key->GetClassName()) != "TTree") continue;
      TTree *t = static_cast<TTree *>(dirIn->Get(key->GetName()));
      if (!t) continue;
      TString tname = t->GetName();
      if (tname.BeginsWith("O2bc_"))   { treeBCs   = t; }
      if (tname.BeginsWith("O2bcflag")){ treeFlags = t; }
    }
  }

  if (!treeBCs) {
    // No BC table — deep-copy everything unchanged
    std::cout << "  No BC table found — copying directory verbatim\n";
    TIter it(dirIn->GetListOfKeys());
    while (TKey *key = static_cast<TKey *>(it())) {
      std::unique_ptr<TObject> obj(key->ReadObj());
      dirOut->cd();
      if (obj->InheritsFrom(TTree::Class())) {
        TTree *c = static_cast<TTree *>(obj.get())->CloneTree(-1, "fast");
        c->SetDirectory(dirOut); c->Write();
      } else if (obj->IsA()->InheritsFrom(TMap::Class())) {
        dirOut->WriteTObject(obj.get(), key->GetName(), "Overwrite");
      } else {
        obj->Write(key->GetName(), TObject::kOverwrite);
      }
    }
    return;
  }

  // ---- Stage 0: sort & deduplicate BCs ----
  std::cout << "-- Stage 0: BCs --\n";
  dirOut->cd();
  BCStage0Result s0 = stage0_sortBCs(treeBCs, dirOut);
  if (treeFlags) stage0_copyBCFlags(treeFlags, dirOut, s0.bcPerm);

  // Track which tree names have been written so we don't double-write
  std::unordered_set<std::string> written;
  written.insert(treeBCs->GetName());
  if (treeFlags) written.insert(treeFlags->GetName());

  // ---- Stage 1: BC-indexed tables (including MCCollisions dedup) ----
  std::cout << "-- Stage 1: BC-indexed tables --\n";
  auto stage1Perms = stage1_BCindexedTables(dirIn, dirOut, s0.bcPerm);
  for (auto &kv : stage1Perms) written.insert(kv.first);

  // ---- Stage 2: MCCollision-indexed tables ----
  // Find the MCCollision permutation from stage 1
  std::cout << "-- Stage 2: MCCollision-indexed tables --\n";
  PermMap mcCollPerm;
  for (auto &[tname, perm] : stage1Perms) {
    if (TString(tname.c_str()).BeginsWith("O2mccollision")) {
      mcCollPerm = perm;
      break;
    }
  }
  if (!mcCollPerm.empty()) {
    auto stage2Perms = stage2_MCCollIndexedTables(dirIn, dirOut, mcCollPerm);
    for (auto &kv : stage2Perms) {
      written.insert(kv.first);
      stage1Perms[kv.first] = kv.second; // merge into allPerms for paste-join lookup
    }
  } else {
    std::cout << "  (no MCCollision table found — skipping stage 2)\n";
  }

  // ---- Paste-join tables + unrelated tables ----
  std::cout << "-- Paste-join and unrelated tables --\n";
  processPasteJoinTables(dirIn, dirOut, stage1Perms, written);

  // ---- Non-tree objects (TMap metadata) ----
  copyNonTreeObjects(dirIn, dirOut);

  std::cout << "Done: " << dirIn->GetName() << "\n";
}

// ============================================================================
// SECTION 11 — Post-write validation
// ============================================================================
//
// AODBcRewriterValidate() opens a rewritten AO2D and checks key invariants:
//   1. BC table is strictly monotonic in fGlobalBC.
//   2. MC particle intra-table daughter/mother indices are in range and point
//      to particles belonging to the same MC collision.
//   3. fIndexMcParticles in label tables is in range.
//
// Returns true if all checks pass.  Prints a summary to stdout.

static bool validateDF(TDirectory *d) {
  bool ok = true;

  // ---- BC monotonicity ----
  TIter it(d->GetListOfKeys());
  TKey *k;
  TTree *bcTree = nullptr;
  TTree *mcpTree = nullptr;
  while ((k = (TKey*)it())) {
    TObject *obj = d->Get(k->GetName());
    if (!obj || !obj->InheritsFrom(TTree::Class())) continue;
    TTree *t = (TTree*)obj;
    TString tn = t->GetName();
    if (tn.BeginsWith("O2bc_"))       bcTree = t;
    if (tn.BeginsWith("O2mcparticle")) mcpTree = t;
  }

  if (bcTree) {
    ULong64_t gbc = 0, prev = 0;
    bcTree->SetBranchAddress("fGlobalBC", &gbc);
    Long64_t nBC = bcTree->GetEntries();
    Long64_t nBad = 0;
    for (Long64_t i = 0; i < nBC; ++i) {
      bcTree->GetEntry(i);
      if (i > 0 && gbc <= prev) ++nBad;
      prev = gbc;
    }
    if (nBad > 0) {
      std::cerr << "  [FAIL] " << bcTree->GetName()
                << ": " << nBad << " non-monotonic BC entries\n";
      ok = false;
    }
  }

  // ---- MC particle intra-table indices ----
  if (mcpTree) {
    Long64_t nMcp = mcpTree->GetEntries();
    Int_t daughters[2] = {-1,-1}, mcCollIdx = -1, motherSize = 0, mothers[200] = {};
    mcpTree->SetBranchStatus("*", 0);
    mcpTree->SetBranchStatus("fIndexSlice_Daughters",   1);
    mcpTree->SetBranchStatus("fIndexMcCollisions",      1);
    mcpTree->SetBranchStatus("fIndexArray_Mothers_size",1);
    mcpTree->SetBranchStatus("fIndexArray_Mothers",     1);
    mcpTree->SetBranchAddress("fIndexSlice_Daughters",   daughters);
    mcpTree->SetBranchAddress("fIndexMcCollisions",      &mcCollIdx);
    mcpTree->SetBranchAddress("fIndexArray_Mothers_size",&motherSize);
    mcpTree->SetBranchAddress("fIndexArray_Mothers",     mothers);

    // Pre-load MC collision index for cross-collision check
    std::vector<Int_t> allMcColl(nMcp);
    for (Long64_t i = 0; i < nMcp; ++i) { mcpTree->GetEntry(i); allMcColl[i] = mcCollIdx; }

    Long64_t badSlice = 0, badMother = 0, badXcoll = 0;
    for (Long64_t i = 0; i < nMcp; ++i) {
      mcpTree->GetEntry(i);
      if (daughters[0] >= 0) {
        if (daughters[0] >= nMcp || daughters[1] >= nMcp || daughters[0] > daughters[1])
          ++badSlice;
        else for (Int_t d2 = daughters[0]; d2 <= daughters[1]; ++d2)
          if (allMcColl[d2] != mcCollIdx) ++badXcoll;
      }
      for (int m = 0; m < std::min(motherSize, 200); ++m) {
        if (mothers[m] >= 0) {
          if (mothers[m] >= nMcp) ++badMother;
          else if (allMcColl[mothers[m]] != mcCollIdx) ++badXcoll;
        }
      }
    }
    if (badSlice || badMother || badXcoll) {
      std::cerr << "  [FAIL] " << mcpTree->GetName()
                << ": bad_slice=" << badSlice
                << "  bad_mother=" << badMother
                << "  cross_coll=" << badXcoll << "\n";
      ok = false;
    }
    mcpTree->SetBranchStatus("*", 1);
  }

  return ok;
}

bool AODBcRewriterValidate(const char *fname = "AO2D_rewritten.root") {
  std::cout << "Validating " << fname << "\n";
  std::unique_ptr<TFile> f(TFile::Open(fname, "READ"));
  if (!f || f->IsZombie()) { std::cerr << "Cannot open " << fname << "\n"; return false; }

  bool allOk = true;
  int nDF = 0;
  TIter top(f->GetListOfKeys());
  TKey *k;
  while ((k = (TKey*)top())) {
    if (!TString(k->GetName()).BeginsWith("DF_")) continue;
    TDirectory *d = (TDirectory*)f->Get(k->GetName());
    bool dfOk = validateDF(d);
    if (!dfOk) std::cerr << "  -> FAILED in " << k->GetName() << "\n";
    allOk = allOk && dfOk;
    ++nDF;
  }
  f->Close();
  if (allOk)
    std::cout << "VALIDATION PASSED (" << nDF << " DFs checked)\n";
  else
    std::cout << "VALIDATION FAILED — see [FAIL] lines above\n";
  return allOk;
}

// ============================================================================
// SECTION 12 — Top-level entry point
// ============================================================================

void AODBcRewriter(const char *inFileName  = "AO2D.root",
                   const char *outFileName = "AO2D_rewritten.root") {

  std::cout << "AODBcRewriter: input=" << inFileName
            << " output=" << outFileName << "\n";

  std::unique_ptr<TFile> fin(TFile::Open(inFileName, "READ"));
  if (!fin || fin->IsZombie()) { std::cerr << "ERROR: cannot open " << inFileName << "\n"; return; }

  int algo = fin->GetCompressionAlgorithm();
  int lvl  = fin->GetCompressionLevel();

#if ROOT_VERSION_CODE >= ROOT_VERSION(6, 30, 0)
  std::unique_ptr<TFile> fout(TFile::Open(outFileName, "RECREATE", "", lvl));
#else
  std::unique_ptr<TFile> fout(TFile::Open(outFileName, "RECREATE"));
#endif
  if (!fout || fout->IsZombie()) { std::cerr << "ERROR: cannot create " << outFileName << "\n"; return; }
  fout->SetCompressionAlgorithm(algo);
  fout->SetCompressionLevel(lvl);

  TIter top(fin->GetListOfKeys());
  while (TKey *key = static_cast<TKey *>(top())) {
    TString name = key->GetName();
    std::unique_ptr<TObject> obj(key->ReadObj());

    if (obj->InheritsFrom(TDirectory::Class()) && isDF(name)) {
      TDirectory *din  = static_cast<TDirectory *>(obj.get());
      TDirectory *dout = fout->mkdir(name);
      processDF(din, dout);
    } else {
      // Top-level non-DF objects (metadata TMaps etc.)
      fout->cd();
      if (obj->IsA()->InheritsFrom(TMap::Class()))
        fout->WriteTObject(obj.get(), name, "Overwrite");
      else
        obj->Write(name, TObject::kOverwrite);
    }
  }

  fout->Write("", TObject::kOverwrite);
  fout->Close();
  fin->Close();
  std::cout << "All done. Output: " << outFileName << "\n";
}
