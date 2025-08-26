// Scans DF_* folders, finds trees with an Int-like "fIndexBCs" branch,
// and reports those where fIndexBCs is not monotonically non-decreasing.
// Negative values (e.g. -1) are ignored for the monotonicity check.

#ifndef __CLING__
#include "TBranch.h"
#include "TDirectory.h"
#include "TFile.h"
#include "TKey.h"
#include "TLeaf.h"
#include "TString.h"
#include "TTree.h"
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
#endif

struct MonotonicReport {
  bool hasBranch = false; // tree has fIndexBCs
  bool monotonic = true;  // true if non-decreasing
  Long64_t entries = 0;
  Long64_t firstViolationEntry = -1; // entry index of first backward step
  Long64_t nViolations = 0;          // count of backward steps
  Long64_t maxBackwardJump = 0;      // biggest (prevValid - curr) observed
  std::vector<std::pair<Long64_t, std::pair<Long64_t, Long64_t>>>
      samples; // (entry, (prev, curr))
};

/// Try to bind a branch named "fIndexBCs" with an integral buffer.
/// Supports common integer POD types (Int_t, UInt_t, Long64_t, ULong64_t).
/// Returns: pointer to bound buffer as int64_t-compatible view (value is
/// copied), and sets branch address appropriately.
class FIndexBinder {
public:
  TBranch *br = nullptr;
  std::string type;
  // One of these will be used based on the branch's leaf type:
  Int_t buf_i = 0;
  UInt_t buf_ui = 0;
  Long64_t buf_l = 0;
  ULong64_t buf_ul = 0;

  // which is active
  enum Kind { KNone, KInt, KUInt, KLong64, KULong64 } kind = KNone;

  bool bind(TTree *t, const char *name = "fIndexBCs") {
    br = t->GetBranch(name);
    if (!br)
      return false;
    if (br->GetListOfLeaves()->GetEntries() <= 0)
      return false;
    TLeaf *leaf = (TLeaf *)br->GetListOfLeaves()->At(0);
    type = leaf->GetTypeName();

    if (type == "Int_t") {
      kind = KInt;
      br->SetAddress(&buf_i);
    } else if (type == "UInt_t") {
      kind = KUInt;
      br->SetAddress(&buf_ui);
    } else if (type == "Long64_t") {
      kind = KLong64;
      br->SetAddress(&buf_l);
    } else if (type == "ULong64_t") {
      kind = KULong64;
      br->SetAddress(&buf_ul);
    } else {
      // not an integer POD we handle
      kind = KNone;
      br = nullptr;
      return false;
    }
    return true;
  }

  // Read the current value as signed 64-bit (for comparisons).
  // For unsigned, cast safely to signed domain if within range; otherwise
  // clamp.
  Long64_t valueAsI64() const {
    switch (kind) {
    case KInt:
      return (Long64_t)buf_i;
    case KUInt:
      return (buf_ui <= (UInt_t)std::numeric_limits<Long64_t>::max()
                  ? (Long64_t)buf_ui
                  : (Long64_t)std::numeric_limits<Long64_t>::max());
    case KLong64:
      return buf_l;
    case KULong64:
      return (buf_ul <= (ULong64_t)std::numeric_limits<Long64_t>::max()
                  ? (Long64_t)buf_ul
                  : (Long64_t)std::numeric_limits<Long64_t>::max());
    default:
      return 0;
    }
  }
};

static MonotonicReport checkTreeMonotonic(TTree *t, bool verbose = false) {
  MonotonicReport r;
  if (!t)
    return r;

  // Speed up: only read the target branch
  t->SetBranchStatus("*", 0);
  if (t->GetBranch("fIndexBCs"))
    t->SetBranchStatus("fIndexBCs", 1);

  FIndexBinder binder;
  if (!binder.bind(t, "fIndexBCs")) {
    r.hasBranch = false;
    // Re-enable all for safety if user continues using the tree later
    t->SetBranchStatus("*", 1);
    return r;
  }
  r.hasBranch = true;

  r.entries = t->GetEntries();
  if (r.entries <= 1) {
    r.monotonic = true;
    t->SetBranchStatus("*", 1);
    return r;
  }

  bool havePrev = false;
  Long64_t prevValid = 0;

  for (Long64_t i = 0; i < r.entries; ++i) {
    t->GetEntry(i);
    Long64_t v = binder.valueAsI64();

    // Ignore negatives (e.g. -1 sentinel values)
    if (v < 0)
      continue;

    if (!havePrev) {
      prevValid = v;
      havePrev = true;
      continue;
    }

    if (v < prevValid) {
      // backward step
      if (r.firstViolationEntry < 0)
        r.firstViolationEntry = i;
      ++r.nViolations;
      r.monotonic = false;
      Long64_t jump = prevValid - v;
      if (jump > r.maxBackwardJump)
        r.maxBackwardJump = jump;
      if (r.samples.size() < 5)
        r.samples.push_back({i, {prevValid, v}});
      // Do not update prevValid here; we keep comparing to last valid
      // non-decreasing reference
      continue;
    }

    // normal non-decreasing step
    prevValid = v;
  }

  // Restore statuses
  t->SetBranchStatus("*", 1);
  return r;
}

void AOD_detect_unsorted_fIndexBCs(const char *inFileName = "AO2D.root",
                                   bool verbosePerTree = false) {
  std::cout << "Opening file: " << inFileName << std::endl;
  TFile *f = TFile::Open(inFileName, "READ");
  if (!f || f->IsZombie()) {
    std::cerr << "ERROR: cannot open input file.\n";
    return;
  }

  Long64_t totalTreesChecked = 0;
  Long64_t totalWithBranch = 0;
  Long64_t totalViolations = 0;

  std::cout << "Scanning top-level for DF_* folders...\n";

  // Iterate top-level keys
  TIter kIt(f->GetListOfKeys());
  while (TKey *k = (TKey *)kIt()) {
    TString kname = k->GetName();
    TObject *obj = k->ReadObj();

    if (!obj->InheritsFrom(TDirectory::Class()) || !kname.BeginsWith("DF_")) {
      continue;
    }

    auto *dir = (TDirectory *)obj;
    std::cout << "\n====================================================\n";
    std::cout << "DF folder: " << dir->GetName() << "\n";

    // Iterate all keys in this DF directory
    TIter dIt(dir->GetListOfKeys());
    while (TKey *dk = (TKey *)dIt()) {
      TObject *tobj = dir->Get(dk->GetName());
      if (!tobj->InheritsFrom(TTree::Class())) {
        continue; // only trees are relevant
      }

      TTree *t = (TTree *)tobj;
      ++totalTreesChecked;

      // Only consider trees that *have* fIndexBCs
      if (!t->GetBranch("fIndexBCs")) {
        if (verbosePerTree) {
          std::cout << "  [skip] " << t->GetName() << " (no fIndexBCs)\n";
        }
        continue;
      }
      ++totalWithBranch;

      MonotonicReport r = checkTreeMonotonic(t, verbosePerTree);

      if (!r.hasBranch) {
        // Shouldn't happen due to prior check, but keep robust
        if (verbosePerTree) {
          std::cout << "  [skip] " << t->GetName()
                    << " (failed to bind branch)\n";
        }
        continue;
      }

      if (r.monotonic) {
        if (verbosePerTree) {
          std::cout << "  [ OK ] " << t->GetName()
                    << " — entries: " << r.entries << " (non-decreasing)\n";
        }
      } else {
        ++totalViolations;
        std::cout << "  [BAD] " << t->GetName() << " — entries: " << r.entries
                  << ", first violation at entry " << r.firstViolationEntry
                  << ", total backward steps: " << r.nViolations
                  << ", max backward jump: " << r.maxBackwardJump << "\n";

        // Print a few examples of (prev, curr) causing violation
        if (!r.samples.empty()) {
          std::cout << "        sample backward steps (entry: prev -> curr):\n";
          for (auto &s : r.samples) {
            std::cout << "          " << s.first << ": " << s.second.first
                      << " -> " << s.second.second << "\n";
          }
        }
      }
    }
  }

  std::cout << "\n==================== SUMMARY ====================\n";
  std::cout << "Trees visited:         " << totalTreesChecked << "\n";
  std::cout << "Trees with fIndexBCs:  " << totalWithBranch << "\n";
  std::cout << "Trees NOT monotonic:   " << totalViolations << "\n";
  std::cout << "=================================================\n";

  f->Close();
}
