// Scans all DF_* folders for O2bc_001 TTrees and checks that the
// fGlobalBC branch (ULong64_t) is monotonically non-decreasing.

#ifndef __CLING__
#include "TBranch.h"
#include "TDirectory.h"
#include "TFile.h"
#include "TKey.h"
#include "TLeaf.h"
#include "TTree.h"
#include <iostream>
#include <limits>
#include <vector>
#endif

struct BCReport {
  bool hasBranch = false;
  bool monotonic = true;
  Long64_t entries = 0;
  Long64_t firstViolationEntry = -1;
  Long64_t nViolations = 0;
  ULong64_t maxBackwardJump = 0;
  std::vector<std::pair<Long64_t, std::pair<ULong64_t, ULong64_t>>> samples;
};

static BCReport checkO2bcTree(TTree *t) {
  BCReport r;
  if (!t)
    return r;

  TBranch *br = t->GetBranch("fGlobalBC");
  if (!br)
    return r;
  r.hasBranch = true;

  ULong64_t buf = 0;
  br->SetAddress(&buf);

  r.entries = t->GetEntries();
  if (r.entries <= 1)
    return r;

  bool havePrev = false;
  ULong64_t prevVal = 0;

  for (Long64_t i = 0; i < r.entries; ++i) {
    t->GetEntry(i);
    ULong64_t v = buf;

    if (!havePrev) {
      prevVal = v;
      havePrev = true;
      continue;
    }

    if (v < prevVal) {
      if (r.firstViolationEntry < 0)
        r.firstViolationEntry = i;
      ++r.nViolations;
      r.monotonic = false;
      ULong64_t jump = prevVal - v;
      if (jump > r.maxBackwardJump)
        r.maxBackwardJump = jump;
      if (r.samples.size() < 5)
        r.samples.push_back({i, {prevVal, v}});
    }

    prevVal = v;
  }

  return r;
}

void AOD_check_globalBC_monotonic(const char *inFileName = "AO2D.root") {
  std::string inFileStr(inFileName);
  if (inFileStr.find("alien:") != std::string::npos) {
    TGrid::Connect("alien");
  }

  std::cout << "Opening file: " << inFileName << std::endl;
  TFile *f = TFile::Open(inFileName, "READ");
  if (!f || f->IsZombie()) {
    std::cerr << "ERROR: cannot open input file.\n";
    return;
  }

  Long64_t totalTrees = 0;
  Long64_t totalWithBranch = 0;
  Long64_t totalViolations = 0;

  TIter topKeys(f->GetListOfKeys());
  while (TKey *k = (TKey *)topKeys()) {
    TObject *obj = k->ReadObj();
    if (!obj->InheritsFrom(TDirectory::Class()))
      continue;

    TDirectory *dir = (TDirectory *)obj;
    TString dname = dir->GetName();
    if (!dname.BeginsWith("DF_"))
      continue;

    TTree *t = (TTree *)dir->Get("O2bc_001");
    if (!t)
      continue;
    ++totalTrees;

    BCReport r = checkO2bcTree(t);

    if (!r.hasBranch) {
      std::cout << "[skip] " << dir->GetName()
                << "/O2bc_001 has no fGlobalBC\n";
      continue;
    }
    ++totalWithBranch;

    if (r.monotonic) {
      std::cout << "[ OK ] " << dir->GetName() << "/O2bc_001 — " << r.entries
                << " entries, monotonic\n";
    } else {
      ++totalViolations;
      std::cout << "[BAD] " << dir->GetName() << "/O2bc_001 — " << r.entries
                << " entries, first violation at entry "
                << r.firstViolationEntry
                << ", total violations: " << r.nViolations
                << ", max backward jump: " << r.maxBackwardJump << "\n";

      for (auto &s : r.samples) {
        std::cout << "       entry " << s.first << ": " << s.second.first
                  << " -> " << s.second.second << "\n";
      }
    }
  }

  std::cout << "\n==================== SUMMARY ====================\n";
  std::cout << "O2bc_001 trees checked: " << totalTrees << "\n";
  std::cout << "With fGlobalBC branch:  " << totalWithBranch << "\n";
  std::cout << "Trees NOT monotonic:    " << totalViolations << "\n";
  std::cout << "=================================================\n";

  f->Close();
}
