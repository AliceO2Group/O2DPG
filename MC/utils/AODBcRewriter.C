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
//   PLAN, THEN WRITE — every stage above only decides row orders and publishes
//              the resulting permutations; processDF writes all tables
//              afterwards.  References are not a DAG: O2fwdtrack points at
//              O2mfttrack (reordered in the same stage) and at itself, so a
//              stage that wrote as it went could not remap them.  It did not,
//              and every global muon in every merged MC AO2D between June and
//              July 2026 got a foreign MFT and MCH leg (O2-7098).
//
//   ONE INDEX REGISTRY — kIndexRefs lists every fIndex* column and the table it
//              points at.  buildRemaps() turns it into a table's remap set, the
//              validator range-checks against it, and any fIndex* column NOT in
//              it is reported loudly.  Do not reintroduce per-stage lists of
//              "indices this stage knows how to remap".
//
//   TESTING — MC/utils/tests/run_aodbcrewriter_tests.sh (ROOT only, seconds).
//              AODBcRewriterCheckLinks(in, out) is the check that sees a
//              mis-remapped index; the output-only checks cannot, because a
//              wrong row number is still a valid one.
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
#include "TGrid.h"
#include <algorithm>
#include <cctype>
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

// ----------------------------------------------------------------------------
// Paste-join relationships (authoritative; derived from AnalysisDataModel.h
// comments such as "Table joined to the collision table containing the MC
// index" and from the SOA EXTENDED_TABLE declarations for cov / extra tables).
//
// A paste-joined CHILD has NO row of its own — its row N corresponds to row N
// of its PARENT.  If the parent is reordered or has rows dropped, the child
// must follow row-for-row to preserve the 1:1 alignment.  Any index columns
// the child carries (e.g. fIndexMcCollisions in O2mccollisionlabel) are then
// remapped *value-wise* via the appropriate parent stage's permutation, but
// rows are NEVER added or dropped on the child's own initiative.
//
// Matching uses TString::BeginsWith on the child name; parent matching uses
// allPerms keys (so versioned names like O2collision_001 resolve via prefix).
// When several parent candidates are listed for the same child, the first one
// found in allPerms wins (this lets us prefer O2track_iu over O2track).
static const std::vector<std::pair<std::string,std::string>> kPasteJoins = {
  // { paste-joined child prefix,    parent prefix }
  { "O2bcflag",            "O2bc"          },  // BCFlags joinable with BCs
  { "O2mccollisionlabel",  "O2collision"   },  // McCollisionLabels  -> Collisions
  { "O2mctracklabel",      "O2track_iu"    },  // McTrackLabels      -> Tracks (prefer _iu)
  { "O2mctracklabel",      "O2track"       },
  { "O2mcfwdtracklabel",   "O2fwdtrack"    },  // McFwdTrackLabels   -> FwdTracks
  { "O2mcmfttracklabel",   "O2mfttrack"    },  // McMFTTrackLabels   -> MFTTracks
  { "O2mccalolabel",       "O2calo"        },  // McCaloLabels       -> Calos
  { "O2trackcov_iu",       "O2track_iu"    },  // TracksCovIU        -> TracksIU (cov)
  { "O2trackextra",        "O2track_iu"    },  // TracksExtra        -> TracksIU
  { "O2fwdtrackcov",       "O2fwdtrack"    },  // FwdTracksCov       -> FwdTracks
  // Note: O2mfttrackcov has its own fIndexMFTTracks column — it is NOT
  //       paste-joined and must NOT be listed here.
};

// True if the given tree name matches any registered paste-join child prefix.
static bool isPasteJoinChild(const std::string &tname) {
  for (auto &kv : kPasteJoins)
    if (TString(tname.c_str()).BeginsWith(kv.first.c_str())) return true;
  return false;
}

// ----------------------------------------------------------------------------
// INDEX-REFERENCE REGISTRY — the single source of truth for "which fIndex*
// column points into which table".
//
// This ONE list drives three things:
//
//   * the rewriter  — buildRemaps() turns it into the complete set of value
//                     remaps for a table, so a reference can no longer be
//                     forgotten.  Forgetting one is the O2-7098 bug class:
//                     Stage 1b reordered O2fwdtrack but nobody remapped its
//                     fIndexMFTTracks / fIndexFwdTracks_MatchMCHTrack, so every
//                     global muon silently got the wrong MFT and MCH leg.  The
//                     values stayed in range, so the range check below passed.
//   * the validator — the generic in-range check.
//   * the drift guard — any fIndex* branch NOT listed here is reported, so a
//                     schema addition breaks the test instead of quietly
//                     producing mis-linked data.
//
// The value is a list of candidate table-name prefixes; the first one that
// resolves in this DF wins (that is how fIndexTracks* prefers O2track_iu over
// O2track).
//
// Referent resolution (isTableNamed): a tree named K is the table named by
// prefix P when K == P or K == P + "_<digits>" (the AO2D schema-version
// suffix).  That deliberately separates O2mfttrack_001 from O2mfttrackcov,
// O2bc_001 from O2bcflag, and O2mccollision_001 from O2mccollisionlabel — a
// plain BeginsWith() would confuse them.
static const std::vector<std::pair<std::string, std::vector<std::string>>> kIndexRefs = {
  { "fIndexBCs",                     { "O2bc" }                  },
  { "fIndexBC",                      { "O2bc" }                  },
  { "fIndexSliceBCs",                { "O2bc" }                  },
  { "fIndexCollisions",              { "O2collision" }           },
  { "fIndexCollision",               { "O2collision" }           },
  { "fIndexMcCollisions",            { "O2mccollision" }         },
  { "fIndexMcParticles",             { "O2mcparticle" }          },
  { "fIndexArrayMcParticles",        { "O2mcparticle" }          },
  // O2mcparticle intra-table links (mother list + [first,last] daughter slice).
  { "fIndexArray_Mothers",           { "O2mcparticle" }          },
  { "fIndexSlice_Daughters",         { "O2mcparticle" }          },
  { "fIndexTracks",                  { "O2track_iu", "O2track" } },
  { "fIndexTracks_0",                { "O2track_iu", "O2track" } },
  { "fIndexTracks_1",                { "O2track_iu", "O2track" } },
  { "fIndexTracks_2",                { "O2track_iu", "O2track" } },
  { "fIndexTracks_Pos",              { "O2track_iu", "O2track" } },
  { "fIndexTracks_Neg",              { "O2track_iu", "O2track" } },
  { "fIndexTracks_Bach",             { "O2track_iu", "O2track" } },
  { "fIndexTracks_ITS",              { "O2track_iu", "O2track" } },
  { "fIndexMFTTracks",               { "O2mfttrack" }            },
  { "fIndexFwdTracks",               { "O2fwdtrack" }            },
  { "fIndexFwdTracks_MatchMCHTrack", { "O2fwdtrack" }            },
  { "fIndexV0s",                     { "O2v0" }                  },
  { "fIndexCascades",                { "O2cascade" }             },
  { "fIndexDecay3Bodys",             { "O2decay3body" }          },
};

// K names the table with prefix P?  See the comment on kIndexRefs.
static bool isTableNamed(const std::string &key, const std::string &prefix) {
  if (key == prefix) return true;
  if (key.size() <= prefix.size() + 1) return false;
  if (key.compare(0, prefix.size(), prefix) != 0) return false;
  if (key[prefix.size()] != '_') return false;
  for (size_t i = prefix.size() + 1; i < key.size(); ++i)
    if (!std::isdigit(static_cast<unsigned char>(key[i]))) return false;
  return true;
}

// Every fIndex* branch of t that is NOT covered by kIndexRefs.  "*_size" count
// branches of VLA index arrays are not references and are excluded.  A non-empty
// result means the schema grew a link the tool does not know how to follow.
static std::vector<std::string> unregisteredIndexBranches(TTree *t) {
  std::vector<std::string> out;
  if (!t) return out;
  for (auto *obj : *t->GetListOfBranches()) {
    std::string bname = static_cast<TBranch *>(obj)->GetName();
    if (bname.rfind("fIndex", 0) != 0) continue;
    if (bname.size() > 5 && bname.compare(bname.size() - 5, 5, "_size") == 0) continue;
    bool known = false;
    for (auto &kv : kIndexRefs) if (kv.first == bname) { known = true; break; }
    if (!known) out.push_back(bname);
  }
  return out;
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
// writeTable() is the single generic function that writes any table.
// It takes:
//   - src      : the source TTree
//   - dirOut   : directory to write the output TTree into
//   - rowOrder : which source rows to include and in what order
//                (a vector of source row indices, possibly a subset)
//   - remaps   : the index columns to remap in-place, each with its own PermMap
//
// There is deliberately NO "primary index" special case.  Every index column —
// the one the table was sorted by as much as an intra-table mother/daughter
// link — goes through the same `remaps` list, which callers obtain from
// buildRemaps() and therefore from the kIndexRefs registry.  The previous
// design had one privileged index plus an optional list of "extra" ones, and
// every stage had to remember to populate the extras; Stage 1b did not, which
// is precisely how O2fwdtrack's match indices were left dangling (O2-7098).

// Describes one index column to remap.
struct IndexRemap {
  std::string    branchName;  // branch whose integer values to remap
  const PermMap *perm;        // remapping table: newVal = (*perm)[oldVal]
};

// The row permutation implied by a rowOrder: perm[srcRow] = outRow, -1 if the
// row is not emitted.
static PermMap permFromRowOrder(Long64_t nSrc,
                                const std::vector<Long64_t> &rowOrder) {
  PermMap perm(nSrc, -1);
  for (Long64_t outRow = 0; outRow < (Long64_t)rowOrder.size(); ++outRow)
    perm[rowOrder[outRow]] = (Int_t)outRow;
  return perm;
}

// Remap n consecutive integers of the given type held in buf.  Out-of-range and
// already-invalid values become -1 (the AO2D "no link" sentinel).
// Returns how many values actually changed.
static Long64_t remapBuffer(void *buf, ScalarTag tag, size_t elemSize, int n,
                            const PermMap &perm) {
  Long64_t changed = 0;
  auto *bytes = static_cast<unsigned char *>(buf);
  for (int j = 0; j < n; ++j) {
    void *slot = bytes + (size_t)j * elemSize;
    Long64_t v  = readAsInt(slot, tag);
    Long64_t nv = (v < 0 || (size_t)v >= perm.size()) ? -1 : perm[(size_t)v];
    if (nv != v) { writeAsInt(slot, tag, nv); ++changed; }
  }
  return changed;
}

static void writeTable(TTree *src, TDirectory *dirOut,
                       const std::vector<Long64_t> &rowOrder,
                       const std::vector<IndexRemap> &remaps = {}) {

  Long64_t nSrc = src->GetEntries();

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

  // Output branches share the input buffers, so an in-place remap below is
  // what out->Fill() sees.
  for (auto &io : ios) {
    TBranch *outBr = out->GetBranch(io.desc.name.c_str());
    if (!outBr) { std::cerr << "  [warn] no output branch for " << io.desc.name << "\n"; continue; }
    outBr->SetAddress(io.dataBuf.data());
    if (io.desc.isVLA) {
      TBranch *outCntBr = out->GetBranch(io.desc.countBranchName.c_str());
      if (outCntBr) outCntBr->SetAddress(io.countBuf.data());
    }
  }

  // Resolve each remap to its BranchIO once, up front, instead of searching the
  // branch list per row (O2mcparticle has millions of rows).
  struct ResolvedRemap { BranchIO *io; const PermMap *perm; };
  std::vector<ResolvedRemap> resolved;
  for (auto &r : remaps) {
    BranchIO *found = nullptr;
    for (auto &io : ios) if (io.desc.name == r.branchName) { found = &io; break; }
    if (!found) continue;   // branch absent (caller probed, so this is unusual)
    // Index columns are signed 32-bit in the AO2D schema.  Refuse to touch
    // anything else rather than write -1 into an unsigned field.
    if (found->desc.tag != ScalarTag::kInt && found->desc.tag != ScalarTag::kShort &&
        found->desc.tag != ScalarTag::kLong64) {
      std::cerr << "  [warn] index branch " << r.branchName
                << " has non-signed-integer type — NOT remapped\n";
      continue;
    }
    resolved.push_back({found, r.perm});
  }

  // Fill the output tree row by row in the requested order
  Long64_t nRemapped = 0;
  for (Long64_t srcRow : rowOrder) {
    src->GetEntry(srcRow);

    for (auto &r : resolved) {
      BranchIO &io = *r.io;
      int n = io.desc.isVLA ? (int)readAsInt(io.countBuf.data(), io.countTag)
                            : io.desc.nElems;
      nRemapped += remapBuffer(io.dataBuf.data(), io.desc.tag, io.desc.elemSize,
                               n, *r.perm);
    }

    out->Fill();
  }

  std::cout << "    wrote " << out->GetEntries() << " / " << nSrc
            << " rows; " << nRemapped << " index values remapped\n";
  out->Write();
}

// Look up the permutation of the table named by the first prefix that resolves.
// Ambiguity (several schema versions of the same table in one DF) is resolved
// deterministically by taking the lexicographically smallest name.
static const PermMap *findPermFor(
    const std::unordered_map<std::string, PermMap> &allPerms,
    const std::vector<std::string> &prefixes,
    std::string *foundName = nullptr) {
  for (auto &prefix : prefixes) {
    const PermMap *best = nullptr;
    std::string bestName;
    for (auto &[name, perm] : allPerms) {
      if (!isTableNamed(name, prefix)) continue;
      if (bestName.empty() || name < bestName) { best = &perm; bestName = name; }
    }
    if (best) { if (foundName) *foundName = bestName; return best; }
  }
  return nullptr;
}

// THE central safety net: derive the complete remap list for a table from the
// kIndexRefs registry.  Every stage writes through this, so an index column can
// only be missed by being absent from kIndexRefs — which
// unregisteredIndexBranches() reports.
static std::vector<IndexRemap> buildRemaps(
    TTree *src, const std::unordered_map<std::string, PermMap> &allPerms) {
  std::vector<IndexRemap> remaps;
  if (!src) return remaps;
  for (auto &[branchName, prefixes] : kIndexRefs) {
    if (!src->GetBranch(branchName.c_str())) continue;
    const PermMap *perm = findPermFor(allPerms, prefixes);
    if (!perm) continue;   // referent table not in this DF — nothing to remap
    remaps.push_back({branchName, perm});
  }
  return remaps;
}

// ============================================================================
// SECTION 3b — Deferred write plan
// ============================================================================
//
// Writing is deferred until every table's row order (and hence its permutation)
// is known, because references can point forwards and sideways: O2fwdtrack
// references O2mfttrack — written later in the same stage — and also itself, via
// fIndexFwdTracks_MatchMCHTrack.  The old code wrote each table as soon as it
// had planned it, so those two permutations simply did not exist yet at write
// time.  That is the mechanism behind O2-7098.
//
// So: every stage now only PLANS (appends a TablePlan, publishes its perm into
// allPerms), and processDF writes all plans afterwards in one pass.
struct TablePlan {
  std::string           name;      // tree name; re-fetched from dirIn at write time
  std::vector<Long64_t> rowOrder;  // source rows to emit, in output order
};

// ============================================================================
// SECTION 4 — Stage 0: BC table sort + deduplication
// ============================================================================
//
// Reads fGlobalBC from the BC tree, sorts rows, drops exact-duplicate BC
// values, and writes the compacted table.  Returns bcPerm[oldRow] = newRow.
//
// IMPORTANT (history — do not "optimize" this back):
// A previous revision replaced this sort with an order-preserving in-place
// dedup that std::abort()ed unless the input BC table was already globalBC-
// sorted.  That directly contradicts this tool's PURPOSE (a) at the top of the
// file — repairing *non-monotonic* fGlobalBC in MERGED AO2Ds — so it aborted on
// exactly the files it exists to fix ("doesn't run to completion").  We sort
// unconditionally instead.
//
// Sorting BCs does imply a reorder cascade: collisions are sorted by their
// remapped fIndexBCs in Stage 1, and the collision-grouped track tables must
// then be re-grouped to follow the new collision order in Stage 1b.  That
// cascade is real and unavoidable for non-monotonic input; it is handled
// explicitly and completely by those stages.  This is the correct fix — keep
// it.  An "assert already sorted" shortcut here is a known dead end.

struct BCStage0Result {
  PermMap bcPerm;          // bcPerm[oldRow] = newRow in sorted/deduped BC table
  Long64_t nUnique = 0;
};

static BCStage0Result stage0_sortBCs(TTree *treeBCs, std::vector<TablePlan> &plans) {
  BCStage0Result res;
  Long64_t n = treeBCs->GetEntries();
  if (n == 0) return res;

  TBranch *brGBC = treeBCs->GetBranch("fGlobalBC");
  if (!brGBC) { std::cerr << "ERROR: O2bc_* tree has no fGlobalBC branch!\n"; return res; }

  ULong64_t gbc = 0;
  brGBC->SetAddress(&gbc);
  std::vector<ULong64_t> gbcs(n);
  for (Long64_t i = 0; i < n; ++i) { treeBCs->GetEntry(i); gbcs[i] = gbc; }

  // Sort row indices by fGlobalBC (stable, so equal-globalBC rows keep their
  // input order before being collapsed below).
  std::vector<Long64_t> order(n);
  std::iota(order.begin(), order.end(), 0);
  std::stable_sort(order.begin(), order.end(),
    [&](Long64_t a, Long64_t b){ return gbcs[a] < gbcs[b]; });

  // Build the deduplicated row list and the permutation: rows sharing a
  // globalBC collapse onto one output row.
  res.bcPerm.assign(n, -1);
  std::vector<Long64_t> rowOrder;  // source rows to keep, in output order
  ULong64_t prev = 0;
  Int_t newRow = -1;
  for (Long64_t srcRow : order) {
    if (newRow < 0 || gbcs[srcRow] != prev) {
      ++newRow;
      prev = gbcs[srcRow];
      rowOrder.push_back(srcRow);
    }
    // All rows with the same globalBC map to the same new row (deduplication)
    res.bcPerm[srcRow] = newRow;
  }
  res.nUnique = rowOrder.size();

  std::cout << "  BC stage: " << n << " rows -> " << res.nUnique << " unique (sorted)\n";

  // The BC table itself carries no index columns.
  plans.push_back({treeBCs->GetName(), std::move(rowOrder)});

  return res;
}

// ============================================================================
// SECTION 5 — Stage 0b: BC flags table (follows BC row order exactly)
// ============================================================================

static void stage0_copyBCFlags(TTree *treeFlags, std::vector<TablePlan> &plans,
                               const PermMap &bcPerm) {
  if (!treeFlags) return;

  // Build rowOrder: for each unique output BC row, pick the first source row
  // that mapped to it
  std::vector<Long64_t> rowOrder;
  std::map<Int_t, Long64_t> first; // newBCrow -> first srcRow
  for (Long64_t i = 0; i < (Long64_t)bcPerm.size(); ++i)
    if (bcPerm[i] >= 0) first.emplace(bcPerm[i], i);  // emplace keeps first
  rowOrder.reserve(first.size());
  for (auto &kv : first) rowOrder.push_back(kv.second);

  plans.push_back({treeFlags->GetName(), std::move(rowOrder)});
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

static void
stage1_BCindexedTables(TDirectory *dirIn, std::vector<TablePlan> &plans,
                       std::unordered_map<std::string, PermMap> &allPerms,
                       const PermMap &bcPerm) {

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

    allPerms[tname] = permFromRowOrder(nSrc, rowOrder);
    plans.push_back({tname, std::move(rowOrder)});
  }
}

// ============================================================================
// SECTION 7 — Stage 2: Tables indexed by MCCollisions
// ============================================================================

static void
stage2_MCCollIndexedTables(TDirectory *dirIn, std::vector<TablePlan> &plans,
                           std::unordered_map<std::string, PermMap> &allPerms,
                           const PermMap &mcCollPerm) {

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

    // A paste-join child (e.g. O2mccollisionlabel) MUST follow its parent's
    // row order and never drop rows on its own.  Defer it to
    // processPasteJoinTables, which will remap any of its own index columns
    // (fIndexMcCollisions, ...) value-wise without touching the row count.
    if (isPasteJoinChild(tname)) {
      std::cout << "  Stage2: deferring paste-join child " << tname
                << " to paste-join handler\n";
      continue;
    }

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

    // O2mcparticle's intra-table mother/daughter links are remapped through this
    // table's OWN permutation.  No special case is needed any more: the perm is
    // published here and buildRemaps() picks it up for fIndexArray_Mothers /
    // fIndexSlice_Daughters at write time, because writing happens after all
    // planning.  The stable sort above preserves within-collision particle
    // order, which keeps fIndexSlice_Daughters contiguous — so remapping
    // [first,last] elementwise is correct.
    allPerms[tname] = permFromRowOrder(nSrc, rowOrder);
    plans.push_back({tname, std::move(rowOrder)});
  }
}

// ============================================================================
// SECTION 8 — Paste-join table handling
// ============================================================================
//
// A paste-joined CHILD has no row of its own — its row N corresponds to row N
// of its PARENT table.  When the parent is reordered, the child must follow
// row-for-row to preserve the 1:1 alignment.  Paste-join children may still
// carry their own index columns; those values are remapped in-place via the
// appropriate parent-stage permutation.
//
// The list of paste-join pairs is in kPasteJoins (Section 1).
//
// This stage no longer enumerates which index columns it knows how to remap:
// buildRemaps() derives them from kIndexRefs at write time, for every table
// alike.  The old hand-maintained enumeration here is what let O2fwdtrack slip
// through — the table was never routed to this function in the first place.
//
// When the named parent is not in allPerms (e.g. tracks aren't reordered in
// this build), the child is processed with identity row order so the
// value-wise remaps still apply but the row order is unchanged.

// ============================================================================
// SECTION 9b — Stage 1b: Collision-grouped track tables
// ============================================================================
//
// The primary track tables (O2track_iu, O2mfttrack_*, O2fwdtrack) are GROUPED
// by collision.  O2's slicing cache (ArrowTableSlicingCache::validateOrder)
// requires every fIndexCollisions group — including the "-1" ambiguous group —
// to be a single contiguous run; otherwise it aborts with
//   "Table ... index fIndexCollisions has a group with index -1 that is split".
//
// When several MC sub-timeframes are merged into one DF_ folder (data-embedding
// anchoring, which stores MC timeframes under the same DF_ as the parent data
// file), each sub-frame contributes its own [collision-grouped][-1 ambiguous]
// block.  Concatenating them splits the -1 group into N runs, so the table is
// no longer sliceable.  Stage 1 only reorders BC-indexed tables, and tracks are
// otherwise written in input row order, so the split survives into the output.
//
// This stage re-establishes the grouping: it reorders each collision-grouped
// track table by its remapped fIndexCollisions (stable, with -1 sinking to the
// end so the ambiguous group is one contiguous run — matching the Stage 1
// convention) and publishes the resulting row permutation.  Downstream:
//   * paste-join children (O2trackextra, O2trackcov_iu, O2mctracklabel, ...)
//     follow the published parent permutation;
//   * every fIndexTracks* / fIndexMFTTracks / fIndexFwdTracks reference is
//     remapped through it — including the ones the track tables hold on EACH
//     OTHER.  O2fwdtrack points at O2mfttrack (fIndexMFTTracks) and at itself
//     (fIndexFwdTracks_MatchMCHTrack), so its remap needs permutations that are
//     only established later in this very stage.  That is why this function
//     PLANS all tables first and lets processDF write them afterwards; writing
//     inline (as it used to) meant those two columns kept pre-reorder row
//     numbers — in range, so no validator complained, but every global muon
//     ended up with a foreign MFT and MCH leg.  See O2-7098.
static bool isCollGroupedTrackTable(const std::string &tname) {
  static const char *kPrefixes[] = {"O2track_iu", "O2track",
                                     "O2mfttrack", "O2fwdtrack"};
  for (auto *p : kPrefixes)
    if (TString(tname.c_str()).BeginsWith(p)) return true;
  return false;
}

static void stage1b_reorderTrackTables(
    TDirectory *dirIn, std::vector<TablePlan> &plans,
    std::unordered_map<std::string, PermMap> &allPerms,
    std::unordered_set<std::string> &planned) {

  const PermMap *collPermP = findPermFor(allPerms, {"O2collision"});
  if (!collPermP) return;  // no collisions present — nothing to regroup against

  TIter it(dirIn->GetListOfKeys());
  while (TKey *key = static_cast<TKey *>(it())) {
    if (TString(key->GetClassName()) != "TTree") continue;
    std::unique_ptr<TObject> obj(key->ReadObj());
    TTree *src = dynamic_cast<TTree *>(obj.get());
    if (!src) continue;

    std::string tname = src->GetName();
    if (planned.count(tname)) continue;       // BC-indexed tracks etc. already done
    if (!isCollGroupedTrackTable(tname)) continue;
    if (isPasteJoinChild(tname)) continue;    // children follow their parent below
    if (!src->GetBranch("fIndexCollisions")) continue;

    std::cout << "  Stage1b [coll-grouped]: " << tname << "\n";

    Long64_t nSrc = src->GetEntries();
    TBranch *inIdxBr = src->GetBranch("fIndexCollisions");
    TLeaf *idxLeaf = static_cast<TLeaf *>(inIdxBr->GetListOfLeaves()->At(0));
    ScalarTag idxTag = tagOf(idxLeaf);
    std::vector<unsigned char> idxBuf(byteSize(idxTag), 0);
    inIdxBr->SetAddress(idxBuf.data());

    struct SortEntry { Long64_t newColl; Long64_t srcRow; };
    std::vector<SortEntry> entries;
    entries.reserve(nSrc);
    for (Long64_t i = 0; i < nSrc; ++i) {
      inIdxBr->GetEntry(i);
      Long64_t oldColl = readAsInt(idxBuf.data(), idxTag);
      Long64_t newColl = (oldColl >= 0 && oldColl < (Long64_t)collPermP->size())
                         ? (*collPermP)[oldColl] : -1;
      entries.push_back({newColl, i});
    }
    // Stable-sort by remapped collision; the ambiguous group (-1) sinks to the
    // end as a single contiguous run.  Stable keeps the within-collision order.
    std::stable_sort(entries.begin(), entries.end(),
      [](const SortEntry &a, const SortEntry &b){
        if (a.newColl < 0 && b.newColl >= 0) return false;
        if (a.newColl >= 0 && b.newColl < 0) return true;
        return a.newColl < b.newColl;
      });
    std::vector<Long64_t> rowOrder;
    rowOrder.reserve(nSrc);
    for (auto &e : entries) rowOrder.push_back(e.srcRow);

    // Publish the permutation now; the actual write (with the full set of
    // remaps, this table's own included) happens in processDF once every
    // permutation in the DF is known.
    allPerms[tname] = permFromRowOrder(nSrc, rowOrder);
    plans.push_back({tname, std::move(rowOrder)});
    planned.insert(tname);
  }
}

// ----------------------------------------------------------------------------
// Re-sorting tables that are STORED SORTED BY a reference
//
// Stage 1b exists because a track table grouped by fIndexCollisions stops being
// sliceable once the collision table is reordered.  Exactly the same is true of
// every other table stored sorted by a reference into a table this tool
// reorders — O2v0_002 and O2cascade_001 by fIndexCollisions, O2fwdtrkcl by
// fIndexFwdTracks, O2ambiguoustrack and O2trackqa_003 by fIndexTracks.
// Remapping their values while leaving their rows in place turns a sorted
// column into an unsorted one, which is the same defect that produced
//   "Table ... index fIndexCollisions has a group with index -1 that is split".
//
// Rather than hardcode which tables are grouped by what — the enumeration habit
// that caused O2-7098 — the decision is derived from the data: IF a column is
// non-decreasing in the input, THEN it is an ordering the file carries and the
// output must preserve it.  That is self-maintaining across schema changes, and
// it correctly leaves O2mfttrackcov alone: its fIndexMFTTracks is not sorted in
// the input, so there is no ordering to preserve.

struct ResortCandidate {
  size_t                   planIdx = 0;
  std::string              tableName;
  std::string              keyBranch;
  std::vector<Long64_t>    keyValues;    // raw input values of keyBranch
  std::vector<std::string> refPrefixes;  // referent of keyBranch, from kIndexRefs
};

// Read a scalar Int_t-like index column.  Returns false for VLA / fixed-array
// columns, which are not row orderings.
static bool readScalarIndexColumn(TTree *t, const char *branch,
                                  std::vector<Long64_t> &out) {
  TBranch *br = t->GetBranch(branch);
  if (!br) return false;
  TLeaf *leaf = static_cast<TLeaf *>(br->GetListOfLeaves()->At(0));
  if (!leaf || leaf->GetLeafCount() || leaf->GetLen() != 1) return false;
  ScalarTag tag = tagOf(leaf);
  size_t sz = byteSize(tag);
  if (sz == 0) return false;
  std::vector<unsigned char> buf(sz, 0);
  br->SetAddress(buf.data());
  out.clear();
  out.reserve(t->GetEntries());
  for (Long64_t i = 0; i < t->GetEntries(); ++i) {
    br->GetEntry(i);
    out.push_back(readAsInt(buf.data(), tag));
  }
  br->ResetAddress();
  return true;
}

// The convention this tool writes (and Stage 1b establishes): valid values
// ascending, the -1 "ambiguous" group as one contiguous run at the end.
static bool isOrderedWithNullsLast(const std::vector<Long64_t> &v) {
  Long64_t prev = -1;
  bool seenNull = false;
  for (auto x : v) {
    if (x < 0) { seenNull = true; continue; }
    if (seenNull) return false;   // a valid value after a null: not this convention
    if (x < prev) return false;
    prev = x;
  }
  return true;
}

// Pick the column a table is stored sorted by, if any.  fIndexCollisions wins
// when several qualify, since that is the grouping O2's slicing cache checks.
static bool findGroupingColumn(TTree *src, std::string &keyBranch,
                               std::vector<Long64_t> &keyValues,
                               std::vector<std::string> &refPrefixes) {
  if (!src || src->GetEntries() < 2) return false;
  bool found = false;
  for (auto &[branchName, prefixes] : kIndexRefs) {
    std::vector<Long64_t> vals;
    if (!readScalarIndexColumn(src, branchName.c_str(), vals)) continue;
    if (!isOrderedWithNullsLast(vals)) continue;
    bool preferred = (branchName == "fIndexCollisions");
    if (found && !preferred) continue;
    keyBranch   = branchName;
    keyValues   = std::move(vals);
    refPrefixes = prefixes;
    found = true;
    if (preferred) break;
  }
  return found;
}

// Re-sort each candidate by its remapped grouping column.  Iterated to a fixed
// point because these tables reference each other: O2cascade_001 is sorted by
// fIndexV0s, and O2v0_002 may itself have just been re-sorted.
static void resortByGroupingColumn(
    std::vector<TablePlan> &plans,
    std::unordered_map<std::string, PermMap> &allPerms,
    const std::vector<ResortCandidate> &candidates) {

  const int kMaxPasses = 8;
  int pass = 0;
  for (; pass < kMaxPasses; ++pass) {
    bool changed = false;
    for (auto &cand : candidates) {
      const PermMap *refPerm = findPermFor(allPerms, cand.refPrefixes);
      if (!refPerm) continue;   // referent absent from this DF

      Long64_t n = (Long64_t)cand.keyValues.size();
      struct SortEntry { Long64_t key; Long64_t srcRow; };
      std::vector<SortEntry> entries;
      entries.reserve(n);
      for (Long64_t i = 0; i < n; ++i) {
        Long64_t old = cand.keyValues[i];
        Long64_t nw  = (old >= 0 && old < (Long64_t)refPerm->size()) ? (*refPerm)[old] : -1;
        entries.push_back({nw, i});
      }
      // Same ordering convention as Stage 1: -1 sinks to a contiguous tail.
      std::stable_sort(entries.begin(), entries.end(),
        [](const SortEntry &a, const SortEntry &b) {
          if (a.key < 0 && b.key >= 0) return false;
          if (a.key >= 0 && b.key < 0) return true;
          return a.key < b.key;
        });
      std::vector<Long64_t> rowOrder;
      rowOrder.reserve(n);
      for (auto &e : entries) rowOrder.push_back(e.srcRow);

      if (rowOrder == plans[cand.planIdx].rowOrder) continue;
      plans[cand.planIdx].rowOrder = rowOrder;
      allPerms[cand.tableName]     = permFromRowOrder(n, rowOrder);
      changed = true;
      std::cout << "  Re-sort: " << cand.tableName << " by remapped "
                << cand.keyBranch << " (was sorted by it on input)\n";
    }
    if (!changed) break;
  }
  if (pass == kMaxPasses)
    std::cerr << "  [warn] re-sort did not reach a fixed point after "
              << kMaxPasses << " passes — check for a reference cycle\n";
}

// Plan every table not yet claimed by an earlier stage: paste-join children
// follow their parent's row order, everything else keeps its own — unless it is
// stored sorted by a reference, in which case resortByGroupingColumn() below
// re-establishes that ordering.  The index columns these tables carry are NOT
// enumerated here — buildRemaps() derives them from kIndexRefs when processDF
// writes.
static void planRemainingTables(
    TDirectory *dirIn, std::vector<TablePlan> &plans,
    std::unordered_map<std::string, PermMap> &allPerms,
    std::unordered_set<std::string> &planned) {

  std::vector<ResortCandidate> resortCandidates;

  TIter it(dirIn->GetListOfKeys());
  while (TKey *key = static_cast<TKey *>(it())) {
    if (TString(key->GetClassName()) != "TTree") continue;
    std::unique_ptr<TObject> obj(key->ReadObj());
    TTree *src = dynamic_cast<TTree *>(obj.get());
    if (!src) continue;

    std::string tname = src->GetName();
    if (planned.count(tname)) continue;
    if (isBCTable(tname.c_str())) continue;
    // Stage-1 BC-indexed and Stage-2 MCColl-indexed non-paste-join tables are
    // already planned.  A paste-join child carrying its own MCColl index
    // (e.g. O2mccollisionlabel) was deferred from stage2 and lands here.
    if (bcIndexBranch(src)) continue;
    if (mcCollIndexBranch(src) && !isPasteJoinChild(tname)) continue;

    Long64_t nSrc = src->GetEntries();

    // Find a paste-join parent for this table (kPasteJoins lookup).
    const PermMap *parentPerm = nullptr;
    std::string parentName;
    for (auto &[pastePrefix, parentPrefix] : kPasteJoins) {
      if (!TString(tname.c_str()).BeginsWith(pastePrefix.c_str())) continue;
      parentPerm = findPermFor(allPerms, {parentPrefix}, &parentName);
      if (parentPerm) break;
    }

    std::vector<Long64_t> rowOrder;
    if (parentPerm) {
      // perm[srcRow] = outRow (-1 = dropped); invert it into an output order.
      std::vector<std::pair<Int_t, Long64_t>> pairs;
      pairs.reserve(parentPerm->size());
      for (Long64_t srcRow = 0; srcRow < (Long64_t)parentPerm->size(); ++srcRow)
        if ((*parentPerm)[srcRow] >= 0) pairs.push_back({(*parentPerm)[srcRow], srcRow});
      std::sort(pairs.begin(), pairs.end());
      rowOrder.reserve(pairs.size());
      for (auto &p : pairs) rowOrder.push_back(p.second);
    }

    if (parentPerm && (Long64_t)rowOrder.size() == nSrc) {
      std::cout << "  Paste-join: " << tname << " follows " << parentName << "\n";
    } else {
      if (parentPerm) {
        // Schema drift: the child cannot be aligned to its parent.  Keep its own
        // row order (the index remaps still get applied at write time, so at
        // least no value is left dangling) and shout — the validator's
        // paste-join parity check will fail on the output.
        std::cerr << "  [warn] paste-join size mismatch: " << tname
                  << " has " << nSrc << " rows but parent perm covers "
                  << rowOrder.size() << " — keeping own row order\n";
      }
      rowOrder.resize(nSrc);
      std::iota(rowOrder.begin(), rowOrder.end(), 0LL);
    }

    // A table that arrives here with its own row order may still be STORED
    // SORTED BY one of its index columns; if that column's referent gets
    // reordered, the sortedness has to be re-established.  Record what is
    // needed for that; the decision is made below, once every table in this
    // stage has a permutation.
    if (!parentPerm) {
      ResortCandidate cand;
      if (findGroupingColumn(src, cand.keyBranch, cand.keyValues, cand.refPrefixes)) {
        cand.planIdx   = plans.size();
        cand.tableName = tname;
        resortCandidates.push_back(std::move(cand));
      }
    }

    allPerms[tname] = permFromRowOrder(nSrc, rowOrder);
    plans.push_back({tname, std::move(rowOrder)});
    planned.insert(tname);
  }

  resortByGroupingColumn(plans, allPerms, resortCandidates);
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

  // ==========================================================================
  // PLAN PHASE — every stage only decides row orders and publishes the
  // resulting permutations.  Nothing is written yet, because a table's index
  // columns may point at tables planned later in the same or a later stage
  // (O2fwdtrack -> O2mfttrack, and O2fwdtrack -> itself).
  // ==========================================================================
  std::vector<TablePlan> plans;
  std::unordered_map<std::string, PermMap> allPerms;
  std::unordered_set<std::string> planned;

  // ---- Stage 0: sort & deduplicate BCs ----
  std::cout << "-- Stage 0: BCs --\n";
  BCStage0Result s0 = stage0_sortBCs(treeBCs, plans);
  if (treeFlags) stage0_copyBCFlags(treeFlags, plans, s0.bcPerm);
  planned.insert(treeBCs->GetName());
  if (treeFlags) planned.insert(treeFlags->GetName());
  // bcPerm is a dedup map (several old rows collapse onto one new row), not a
  // plain row permutation — which is exactly the mapping references into the BC
  // table need.  Publishing it under the BC tree's real name lets buildRemaps()
  // resolve fIndexBCs / fIndexBC / fIndexSliceBCs like any other reference.
  allPerms[treeBCs->GetName()] = s0.bcPerm;

  // ---- Stage 1: BC-indexed tables (including MCCollisions dedup) ----
  std::cout << "-- Stage 1: BC-indexed tables --\n";
  stage1_BCindexedTables(dirIn, plans, allPerms, s0.bcPerm);
  for (auto &kv : allPerms) planned.insert(kv.first);

  // ---- Stage 2: MCCollision-indexed tables ----
  std::cout << "-- Stage 2: MCCollision-indexed tables --\n";
  const PermMap *mcCollPermP = findPermFor(allPerms, {"O2mccollision"});
  if (mcCollPermP) {
    PermMap mcCollPerm = *mcCollPermP;   // copy: allPerms grows below
    stage2_MCCollIndexedTables(dirIn, plans, allPerms, mcCollPerm);
    for (auto &kv : allPerms) planned.insert(kv.first);
  } else {
    std::cout << "  (no MCCollision table found — skipping stage 2)\n";
  }

  // ---- Stage 1b: regroup collision-grouped track tables ----
  // Must run after Stage 1 (needs the collision permutation).
  std::cout << "-- Stage 1b: collision-grouped track tables --\n";
  stage1b_reorderTrackTables(dirIn, plans, allPerms, planned);

  // ---- Paste-join tables + unrelated tables ----
  std::cout << "-- Paste-join and unrelated tables --\n";
  planRemainingTables(dirIn, plans, allPerms, planned);

  // ==========================================================================
  // WRITE PHASE — all permutations are known, so every table can now have
  // ALL of its index columns remapped, whichever table they point at.
  // ==========================================================================
  std::cout << "-- Writing " << plans.size() << " tables --\n";
  for (auto &plan : plans) {
    TTree *src = dynamic_cast<TTree *>(dirIn->Get(plan.name.c_str()));
    if (!src) { std::cerr << "  [warn] lost tree " << plan.name << " before write\n"; continue; }

    // Drift guard: a link the registry does not know about cannot be remapped,
    // so say so loudly here as well as in the validator.
    for (auto &b : unregisteredIndexBranches(src))
      std::cerr << "  [warn] " << plan.name << "." << b
                << " is not in kIndexRefs — it will NOT be remapped\n";

    auto remaps = buildRemaps(src, allPerms);

    bool identity = ((Long64_t)plan.rowOrder.size() == src->GetEntries());
    for (Long64_t i = 0; identity && i < (Long64_t)plan.rowOrder.size(); ++i)
      if (plan.rowOrder[i] != i) identity = false;

    if (identity && remaps.empty()) {
      std::cout << "  Copy (no dependency): " << plan.name << "\n";
      dirOut->cd();
      TTree *c = src->CloneTree(-1, "fast");
      c->SetDirectory(dirOut);
      c->Write();
      continue;
    }

    std::cout << "  Write: " << plan.name << " (" << remaps.size() << " index column(s))\n";
    writeTable(src, dirOut, plan.rowOrder, remaps);
  }

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
//   3. Every paste-joined child table has the same row count as its parent
//      (e.g. O2mccollisionlabel matches O2collision).
//   4. Every fIndex* value across the DF is in range w.r.t. its referent
//      table (value -1 is always permitted as the "no link" sentinel).
//   5. Every fIndex* branch present is covered by kIndexRefs — an unknown link
//      is a link nothing remapped.
//
// Returns true if all checks pass.  Prints [FAIL] lines for each violation.
//
// NOTE on what these checks can and cannot see: they are all *structural*.  The
// O2-7098 corruption was in-range and structurally perfect — the row numbers
// were simply the wrong ones.  Catching that needs the input file too; see
// AODBcRewriterCheckLinks() at the end of this section.

// Find a tree in d whose name matches the given table prefix (see isTableNamed).
// Returns the number of entries, or -1 if not found.
static Long64_t treeEntriesByPrefix(TDirectory *d, const char *prefix) {
  TIter it(d->GetListOfKeys());
  TKey *k;
  while ((k = (TKey*)it())) {
    if (!isTableNamed(k->GetName(), prefix)) continue;
    TObject *obj = d->Get(k->GetName());
    if (!obj || !obj->InheritsFrom(TTree::Class())) continue;
    return ((TTree*)obj)->GetEntries();
  }
  return -1;
}

// Entries of the table a given index branch refers to (first prefix that
// resolves wins), or -1 if the referent is not in this DF.
static Long64_t referentEntries(TDirectory *d,
                                const std::vector<std::string> &prefixes) {
  for (auto &p : prefixes) {
    Long64_t n = treeEntriesByPrefix(d, p.c_str());
    if (n >= 0) return n;
  }
  return -1;
}

// Generic in-range check for every fIndex* branch listed above.  Reads the
// branch's leaf (scalar, fixed-array, or VLA), iterates all entries, and
// counts how many values are outside [-1, nReferent).
static Long64_t checkIndexRange(TTree *t, const char *branchName,
                                Long64_t nReferent) {
  TBranch *br = t->GetBranch(branchName);
  if (!br) return 0;
  TLeaf *leaf = (TLeaf*)br->GetListOfLeaves()->At(0);
  if (!leaf) return 0;
  if (TString(leaf->GetTypeName()) != "Int_t") return 0; // only Int_t indices

  TLeaf *cntLeaf = leaf->GetLeafCount();   // VLA?
  int    fixedN = leaf->GetLen();          // 1 for scalar, >1 for fixed array

  // Allocate worst-case buffer.  For a VLA we need a prescan to size it.
  Long64_t maxLen = fixedN;
  if (cntLeaf) {
    // simple prescan
    Int_t cnt = 0;
    TBranch *cntBr = cntLeaf->GetBranch();
    cntBr->SetAddress(&cnt);
    for (Long64_t i = 0; i < t->GetEntries(); ++i) {
      cntBr->GetEntry(i);
      if (cnt > maxLen) maxLen = cnt;
    }
  }
  std::vector<Int_t> buf(std::max<Long64_t>(1, maxLen), 0);
  Int_t  cnt = fixedN;
  TBranch *cntBr = cntLeaf ? cntLeaf->GetBranch() : nullptr;
  br->SetAddress(buf.data());
  if (cntBr) cntBr->SetAddress(&cnt);

  Long64_t bad = 0;
  for (Long64_t i = 0; i < t->GetEntries(); ++i) {
    br->GetEntry(i);
    if (cntBr) cntBr->GetEntry(i);
    int n = cntBr ? (int)cnt : fixedN;
    for (int j = 0; j < n; ++j) {
      Int_t v = buf[j];
      if (v < -1)            { ++bad; continue; }
      if (v >= (Int_t)nReferent) { ++bad; continue; }
    }
  }
  br->ResetAddress();
  if (cntBr) cntBr->ResetAddress();
  return bad;
}

// Verify the collision-grouping invariant that O2's ArrowTableSlicingCache
// (validateOrder) enforces on the consumer side: in a table grouped by
// fIndexCollisions, every distinct index value — including the -1 "ambiguous"
// group — must occupy a single contiguous run of rows.  A split group is
// exactly the failure that crashed event-selection downstream
// ("Table ... index fIndexCollisions has a group with index -1 that is split
// by N").  This is the post-write counterpart to Stage 1b's regrouping.
// Returns the number of groups found split into >1 run (0 = OK).
static Long64_t checkCollisionGroupContiguity(TTree *t) {
  TBranch *br = t->GetBranch("fIndexCollisions");
  if (!br) return 0;
  TLeaf *leaf = (TLeaf*)br->GetListOfLeaves()->At(0);
  if (!leaf || TString(leaf->GetTypeName()) != "Int_t") return 0;
  if (leaf->GetLen() != 1 || leaf->GetLeafCount()) return 0;  // scalar only

  Int_t idx = 0;
  br->SetAddress(&idx);
  std::unordered_set<Int_t> closed;   // groups whose run has already ended
  Int_t cur = 0; bool have = false;
  Long64_t split = 0;
  for (Long64_t i = 0; i < t->GetEntries(); ++i) {
    br->GetEntry(i);
    if (have && idx == cur) continue;   // current run continues
    if (have) closed.insert(cur);       // previous run just ended
    if (closed.count(idx)) ++split;     // re-opening a group seen earlier
    cur = idx; have = true;
  }
  br->ResetAddress();
  return split;
}

static bool validateDF(TDirectory *d) {
  bool ok = true;

  // ---- discover key trees ----
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

  // ---- Paste-join row-count parity ----
  // For every (child, parent) pair in kPasteJoins, if both are present in the
  // DF their row counts must be identical.  This catches the class of bugs
  // where a child was sorted/dropped on its own index (e.g. a previous
  // version dropped O2mccollisionlabel rows on MC-collision dedup while
  // leaving O2collision_001 intact, producing an off-by-N mismatch).
  for (auto &[childPrefix, parentPrefix] : kPasteJoins) {
    Long64_t nChild  = treeEntriesByPrefix(d, childPrefix.c_str());
    Long64_t nParent = treeEntriesByPrefix(d, parentPrefix.c_str());
    if (nChild < 0 || nParent < 0) continue;  // pair not both present
    if (nChild != nParent) {
      std::cerr << "  [FAIL] paste-join size mismatch: " << childPrefix << "*"
                << " has " << nChild << " rows but parent " << parentPrefix << "*"
                << " has " << nParent << "\n";
      ok = false;
    }
  }

  // ---- Generic fIndex* range check + registry drift guard ----
  // For each table in the DF, scan all fIndex* branches and confirm every
  // value lies in [-1, nReferent).  This catches stale pointers across
  // tables (cross-table index drift) which a per-DF-tree-only check misses.
  //
  // Any fIndex* branch that is NOT in kIndexRefs is a hard failure: the
  // rewriter cannot have remapped it, so if the referent table was reordered
  // the column is now silently wrong.  Adding the entry to kIndexRefs is the
  // fix — that is the whole point of having one registry.
  TIter it2(d->GetListOfKeys());
  TKey *k2;
  while ((k2 = (TKey*)it2())) {
    TObject *obj = d->Get(k2->GetName());
    if (!obj || !obj->InheritsFrom(TTree::Class())) continue;
    TTree *t = (TTree*)obj;
    for (auto &b : unregisteredIndexBranches(t)) {
      std::cerr << "  [FAIL] " << t->GetName() << "." << b
                << " is not registered in kIndexRefs — nothing remaps it\n";
      ok = false;
    }
    for (auto &[branchName, referentPrefixes] : kIndexRefs) {
      if (!t->GetBranch(branchName.c_str())) continue;
      Long64_t nRef = referentEntries(d, referentPrefixes);
      if (nRef < 0) continue;   // referent not in this DF; skip silently
      Long64_t bad = checkIndexRange(t, branchName.c_str(), nRef);
      if (bad > 0) {
        std::cerr << "  [FAIL] " << t->GetName() << "." << branchName
                  << ": " << bad << " value(s) out of range [-1, " << nRef << ")\n";
        ok = false;
      }
    }
  }

  // ---- Collision-group contiguity (slicing invariant) ----
  // O2's slicing cache requires each fIndexCollisions group (incl. -1) to be a
  // single contiguous run.  This is the exact invariant whose violation crashed
  // event-selection; it is what Stage 1b re-establishes.  Check every
  // collision-grouped track table (paste-join children follow their parent's
  // row order, so checking the parent suffices).
  TIter it3(d->GetListOfKeys());
  TKey *k3;
  while ((k3 = (TKey*)it3())) {
    TObject *obj = d->Get(k3->GetName());
    if (!obj || !obj->InheritsFrom(TTree::Class())) continue;
    TTree *t = (TTree*)obj;
    if (!isCollGroupedTrackTable(t->GetName())) continue;
    if (isPasteJoinChild(t->GetName())) continue;
    Long64_t split = checkCollisionGroupContiguity(t);
    if (split > 0) {
      std::cerr << "  [FAIL] " << t->GetName()
                << ": fIndexCollisions has " << split
                << " group(s) split into non-contiguous runs (slicing will abort)\n";
      ok = false;
    }
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
// SECTION 11b — Link preservation check (input vs output)
// ============================================================================
//
// WHY THIS EXISTS
//
// Everything in Section 11 is a *structural* check of the output alone: are the
// BCs monotonic, are the paste-join row counts equal, is every index value in
// range.  O2-7098 passed all of them.  Stage 1b reordered O2fwdtrack without
// remapping fIndexMFTTracks / fIndexFwdTracks_MatchMCHTrack, so every global
// muon pointed at a perfectly valid, perfectly in-range, completely unrelated
// MFT track.  No structural check can see that — you have to compare against
// the input.
//
// THE INVARIANT
//
// The rewriter permutes rows and drops duplicates.  It must never change what a
// row *is* or what it *points at*.  So for every table, the multiset of tuples
//
//     ( payload fingerprint of the row,
//       payload fingerprint of the row each index column points at, ... )
//
// must be the same before and after — up to rows that were legitimately
// dropped.  Row identity comes from the payload fingerprint (a hash of every
// non-fIndex* branch), so no permutation map, no synthetic tagging and no
// assumption about ordering is needed.  It runs on real production AO2Ds.
//
// Dedup is handled by canonicalising the INPUT side: if a referenced input row
// has no counterpart in the output (it was dropped), the link is rewritten to
// the "no link" sentinel first, which is exactly what the rewriter does.  A
// tuple that exists in the output but in no input row is then always a bug.

static const ULong64_t kFnvOffset = 14695981039346656037ULL;
static const ULong64_t kFnvPrime  = 1099511628211ULL;
static const ULong64_t kNullFp    = 0ULL;   // reserved: "points at nothing"

static ULong64_t fnv1a(ULong64_t h, const void *data, size_t n) {
  const unsigned char *p = static_cast<const unsigned char *>(data);
  for (size_t i = 0; i < n; ++i) { h ^= p[i]; h *= kFnvPrime; }
  return h;
}

// Per-row hash of every non-index branch.  Two rows with the same fingerprint
// are interchangeable as far as this check is concerned, which is the right
// semantics: identical rows may be freely permuted among themselves.
//
// `onlyBranch`, when given, restricts the hash to that single branch.  It is
// used for the BC table, and only for it: Stage 0 deduplicates BCs by
// fGlobalBC and *redirects* references onto the surviving row rather than
// nulling them, so two BC rows that share a fGlobalBC have to be treated as one
// identity here.  Every other dedup in this tool drops rows and nulls the
// references, which the survivor canonicalisation below handles.
static std::vector<ULong64_t> payloadFingerprints(TTree *t,
                                                  const char *onlyBranch = nullptr) {
  std::vector<ULong64_t> fps;
  if (!t) return fps;
  Long64_t n = t->GetEntries();
  fps.resize(n, kFnvOffset);

  auto descs = describeBranches(t);
  struct IO {
    BranchDesc desc;
    std::vector<unsigned char> dataBuf, countBuf;
    ScalarTag countTag = ScalarTag::kUnknown;
    TBranch *br = nullptr, *cntBr = nullptr;
  };
  std::vector<IO> ios;
  for (auto &d : descs) {
    if (onlyBranch) { if (d.name != onlyBranch) continue; }
    else if (d.name.rfind("fIndex", 0) == 0) continue;  // index columns are not payload
    IO io; io.desc = d;
    io.dataBuf.assign((d.isVLA ? d.maxElems : d.nElems) * d.elemSize, 0);
    io.br = t->GetBranch(d.name.c_str());
    if (d.isVLA) {
      io.cntBr = t->GetBranch(d.countBranchName.c_str());
      TLeaf *cl = io.cntBr ? static_cast<TLeaf *>(io.cntBr->GetListOfLeaves()->At(0)) : nullptr;
      io.countTag = cl ? tagOf(cl) : ScalarTag::kUnknown;
      io.countBuf.assign(byteSize(io.countTag), 0);
    }
    ios.push_back(std::move(io));
  }
  for (auto &io : ios) {
    if (io.br)    io.br->SetAddress(io.dataBuf.data());
    if (io.cntBr) io.cntBr->SetAddress(io.countBuf.data());
  }

  for (Long64_t i = 0; i < n; ++i) {
    ULong64_t h = kFnvOffset;
    for (auto &io : ios) {
      if (io.br)    io.br->GetEntry(i);
      if (io.cntBr) io.cntBr->GetEntry(i);
      if (io.desc.isVLA) {
        Long64_t cnt = readAsInt(io.countBuf.data(), io.countTag);
        h = fnv1a(h, &cnt, sizeof(cnt));
        h = fnv1a(h, io.dataBuf.data(), (size_t)std::max<Long64_t>(0, cnt) * io.desc.elemSize);
      } else {
        h = fnv1a(h, io.dataBuf.data(), (size_t)io.desc.nElems * io.desc.elemSize);
      }
    }
    fps[i] = (h == kNullFp) ? 1ULL : h;   // never collide with the NULL sentinel
  }
  t->ResetBranchAddresses();
  return fps;
}

// One index column of a table, resolved to the referent's fingerprint table.
struct LinkColumn {
  std::string                   branchName;
  const std::vector<ULong64_t> *refFp = nullptr;  // referent fingerprints, same file
  const std::unordered_set<ULong64_t> *survivors = nullptr;  // input side only
};

// Multiset (as a count map) of the per-row tuples described at the top of this
// section, hashed down to a single 64-bit key.
static std::map<ULong64_t, Long64_t> linkTupleCounts(
    TTree *t, const std::vector<ULong64_t> &ownFp,
    const std::vector<LinkColumn> &links) {

  std::map<ULong64_t, Long64_t> counts;
  Long64_t n = t->GetEntries();

  struct IO {
    BranchDesc desc;
    std::vector<unsigned char> dataBuf, countBuf;
    ScalarTag countTag = ScalarTag::kUnknown;
    TBranch *br = nullptr, *cntBr = nullptr;
    const LinkColumn *link = nullptr;
  };
  auto descs = describeBranches(t);
  std::vector<IO> ios;
  for (auto &lk : links) {
    for (auto &d : descs) {
      if (d.name != lk.branchName) continue;
      IO io; io.desc = d; io.link = &lk;
      io.dataBuf.assign((d.isVLA ? d.maxElems : d.nElems) * d.elemSize, 0);
      io.br = t->GetBranch(d.name.c_str());
      if (d.isVLA) {
        io.cntBr = t->GetBranch(d.countBranchName.c_str());
        TLeaf *cl = io.cntBr ? static_cast<TLeaf *>(io.cntBr->GetListOfLeaves()->At(0)) : nullptr;
        io.countTag = cl ? tagOf(cl) : ScalarTag::kUnknown;
        io.countBuf.assign(byteSize(io.countTag), 0);
      }
      ios.push_back(std::move(io));
      break;
    }
  }
  for (auto &io : ios) {
    if (io.br)    io.br->SetAddress(io.dataBuf.data());
    if (io.cntBr) io.cntBr->SetAddress(io.countBuf.data());
  }

  for (Long64_t i = 0; i < n; ++i) {
    ULong64_t h = fnv1a(kFnvOffset, &ownFp[i], sizeof(ULong64_t));
    for (auto &io : ios) {
      if (io.br)    io.br->GetEntry(i);
      if (io.cntBr) io.cntBr->GetEntry(i);
      int cnt = io.desc.isVLA ? (int)readAsInt(io.countBuf.data(), io.countTag)
                              : io.desc.nElems;
      for (int j = 0; j < cnt; ++j) {
        Long64_t v = readAsInt(io.dataBuf.data() + (size_t)j * io.desc.elemSize,
                               io.desc.tag);
        ULong64_t fp = kNullFp;
        if (v >= 0 && v < (Long64_t)io.link->refFp->size()) {
          fp = (*io.link->refFp)[v];
          // Input side: a referent row that did not survive into the output is
          // expected to become a null link, so canonicalise it to one here.
          if (io.link->survivors && !io.link->survivors->count(fp)) fp = kNullFp;
        }
        h = fnv1a(h, &fp, sizeof(fp));
      }
    }
    ++counts[h];
  }
  t->ResetBranchAddresses();
  return counts;
}

static bool checkLinksDF(TDirectory *din, TDirectory *dout, const char *dfName) {
  bool ok = true;

  // Collect the tables present in both files.
  std::vector<std::string> tables;
  TIter it(din->GetListOfKeys());
  while (TKey *k = static_cast<TKey *>(it())) {
    if (TString(k->GetClassName()) != "TTree") continue;
    std::string tn = k->GetName();
    if (!dout->Get(tn.c_str())) {
      std::cerr << "  [FAIL] " << dfName << ": table " << tn << " missing from output\n";
      ok = false;
      continue;
    }
    tables.push_back(tn);
  }

  // Fingerprint every table in both files once — referents are looked up by name.
  std::unordered_map<std::string, std::vector<ULong64_t>> fpIn, fpOut;
  std::unordered_map<std::string, std::unordered_set<ULong64_t>> survivors;
  for (auto &tn : tables) {
    const char *only = isTableNamed(tn, "O2bc") ? "fGlobalBC" : nullptr;
    fpIn[tn]  = payloadFingerprints(dynamic_cast<TTree *>(din->Get(tn.c_str())),  only);
    fpOut[tn] = payloadFingerprints(dynamic_cast<TTree *>(dout->Get(tn.c_str())), only);
    survivors[tn].insert(fpOut[tn].begin(), fpOut[tn].end());
  }

  for (auto &tn : tables) {
    TTree *tIn  = dynamic_cast<TTree *>(din->Get(tn.c_str()));
    TTree *tOut = dynamic_cast<TTree *>(dout->Get(tn.c_str()));
    if (!tIn || !tOut) continue;

    if (tOut->GetEntries() > tIn->GetEntries()) {
      std::cerr << "  [FAIL] " << dfName << ": " << tn << " grew from "
                << tIn->GetEntries() << " to " << tOut->GetEntries() << " rows\n";
      ok = false;
    }

    // Resolve this table's index columns to their referent fingerprint tables.
    std::vector<LinkColumn> linksIn, linksOut;
    for (auto &[branchName, prefixes] : kIndexRefs) {
      if (!tIn->GetBranch(branchName.c_str())) continue;
      std::string refName;
      for (auto &p : prefixes) {
        for (auto &cand : tables) if (isTableNamed(cand, p)) { refName = cand; break; }
        if (!refName.empty()) break;
      }
      if (refName.empty()) continue;   // referent not in this DF
      linksIn.push_back({branchName, &fpIn[refName], &survivors[refName]});
      linksOut.push_back({branchName, &fpOut[refName], nullptr});
    }

    // Ordering preservation: a column that is sorted on input describes a
    // grouping the file carries, and O2's slicing cache relies on it.  Remapping
    // the values while leaving the rows in place silently destroys it — the same
    // defect as the split "-1" group, just in a different table.
    for (auto &[branchName, prefixes] : kIndexRefs) {
      std::vector<Long64_t> vIn, vOut;
      if (!readScalarIndexColumn(tIn, branchName.c_str(), vIn)) continue;
      if (!isOrderedWithNullsLast(vIn)) continue;   // no ordering to preserve
      if (!readScalarIndexColumn(tOut, branchName.c_str(), vOut)) continue;
      if (!isOrderedWithNullsLast(vOut)) {
        std::cerr << "  [FAIL] " << dfName << ": " << tn << "." << branchName
                  << " was sorted on input but is not on output"
                     " (grouping destroyed — slicing will misbehave)\n";
        ok = false;
      }
    }

    auto cIn  = linkTupleCounts(tIn,  fpIn[tn],  linksIn);
    auto cOut = linkTupleCounts(tOut, fpOut[tn], linksOut);

    // Every output tuple must be accounted for by an input tuple.  The reverse
    // is not required: dedup legitimately removes rows.
    Long64_t unexplained = 0;
    for (auto &[key, nOut] : cOut) {
      auto found = cIn.find(key);
      Long64_t nIn = (found == cIn.end()) ? 0 : found->second;
      if (nOut > nIn) unexplained += nOut - nIn;
    }
    if (unexplained > 0) {
      std::cerr << "  [FAIL] " << dfName << ": " << tn << " — " << unexplained
                << " of " << tOut->GetEntries()
                << " output row(s) have a payload/link combination that no input"
                   " row had (rows or references were mis-permuted)\n";
      ok = false;
    }
  }
  return ok;
}

// Compare a rewritten AO2D against the file it was produced from and verify
// that no row changed what it points at.  This is the check that catches the
// O2-7098 bug class; run it whenever AODBcRewriter.C is touched.
bool AODBcRewriterCheckLinks(const char *inFileName  = "AO2D_pre.root",
                             const char *outFileName = "AO2D_rewritten.root") {
  std::cout << "Checking link preservation: " << inFileName
            << " -> " << outFileName << "\n";
  if (TString(inFileName).BeginsWith("alien:") ||
      TString(outFileName).BeginsWith("alien:")) TGrid::Connect("alien");
  std::unique_ptr<TFile> fin(TFile::Open(inFileName, "READ"));
  std::unique_ptr<TFile> fout(TFile::Open(outFileName, "READ"));
  if (!fin || fin->IsZombie())   { std::cerr << "Cannot open " << inFileName << "\n";  return false; }
  if (!fout || fout->IsZombie()) { std::cerr << "Cannot open " << outFileName << "\n"; return false; }

  bool allOk = true;
  int nDF = 0;
  TIter top(fin->GetListOfKeys());
  while (TKey *k = static_cast<TKey *>(top())) {
    if (!isDF(k->GetName())) continue;
    TDirectory *din  = dynamic_cast<TDirectory *>(fin->Get(k->GetName()));
    TDirectory *dout = dynamic_cast<TDirectory *>(fout->Get(k->GetName()));
    if (!din) continue;
    if (!dout) {
      std::cerr << "  [FAIL] " << k->GetName() << " missing from output\n";
      allOk = false;
      continue;
    }
    allOk = checkLinksDF(din, dout, k->GetName()) && allOk;
    ++nDF;
  }
  fin->Close();
  fout->Close();
  if (allOk) std::cout << "LINK CHECK PASSED (" << nDF << " DFs checked)\n";
  else       std::cout << "LINK CHECK FAILED — see [FAIL] lines above\n";
  return allOk;
}

// ============================================================================
// SECTION 12 — Top-level entry point
// ============================================================================

void AODBcRewriter(const char *inFileName  = "AO2D.root",
                   const char *outFileName = "AO2D_rewritten.root") {

  std::cout << "AODBcRewriter: input=" << inFileName
            << " output=" << outFileName << "\n";
  if (TString(inFileName).BeginsWith("alien:")) {
    TGrid::Connect("alien");
  }
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
