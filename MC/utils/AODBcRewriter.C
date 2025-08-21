// A utility to remove duplicate bunch crossing entries
// from the O2bc_ table/TTree and to adjust all tables refering
// to fIndexBC.
// Situations of duplicate BCs can arise in O2DPG MC and are harder to avoid
// directly in the AO2D creation. This tool provides a convenient
// post-processing step to rectify the situation.
// The tool might need adjustment whenever the AO2D data format changes, for
// instance when new tables are added which are directly joinable to the BC
// table.

// started by sandro.wenzel@cern.ch August 2025

// Usage: root -l -b -q 'AODBcRewriter.C("input.root","output.root")'

#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "TBranch.h"
#include "TDirectory.h"
#include "TFile.h"
#include "TKey.h"
#include "TLeaf.h"
#include "TString.h"
#include "TTree.h"

#include <algorithm>
#include <iostream>
#include <memory>
#include <numeric>
#include <unordered_map>
#include <vector>
#endif

/// Helper to manage branch buffers and copying
struct BranchHandler {
  std::string name;
  std::string type;
  void *inBuf = nullptr;
  void *outBuf = nullptr;
  TBranch *inBranch = nullptr;
  TBranch *outBranch = nullptr;

  BranchHandler(TBranch *br, TTree *outTree = nullptr) {
    inBranch = br;
    name = br->GetName();
    TLeaf *leaf = (TLeaf *)br->GetListOfLeaves()->At(0);
    type = leaf->GetTypeName();

    if (type == "Int_t") {
      inBuf = new Int_t;
      if (outTree) {
        outBuf = new Int_t;
        outBranch = outTree->Branch(name.c_str(), (Int_t *)outBuf);
      }
    } else if (type == "ULong64_t") {
      inBuf = new ULong64_t;
      if (outTree) {
        outBuf = new ULong64_t;
        outBranch = outTree->Branch(name.c_str(), (ULong64_t *)outBuf);
      }
    } else if (type == "UChar_t") {
      inBuf = new UChar_t;
      if (outTree) {
        outBuf = new UChar_t;
        outBranch = outTree->Branch(name.c_str(), (UChar_t *)outBuf);
      }
    } else {
      std::cerr << "Unsupported type " << type << " for branch " << name
                << std::endl;
    }
    if (inBuf)
      inBranch->SetAddress(inBuf);
  }

  void copyValue() {
    if (inBuf && outBuf) {
      TLeaf *leaf = (TLeaf *)inBranch->GetListOfLeaves()->At(0);
      size_t sz = leaf->GetLenType();
      memcpy(outBuf, inBuf, sz);
    }
  }

  ~BranchHandler() { deleteBuffer(); }

  void deleteBuffer() {
    if (type == "Int_t") {
      delete (Int_t *)inBuf;
      delete (Int_t *)outBuf;
    } else if (type == "ULong64_t") {
      delete (ULong64_t *)inBuf;
      delete (ULong64_t *)outBuf;
    } else if (type == "UChar_t") {
      delete (UChar_t *)inBuf;
      delete (UChar_t *)outBuf;
    }
    inBuf = outBuf = nullptr;
  }
};

/// Copy any TObject (tree or dir handled recursively)
void copyObject(TObject *obj, TDirectory *outDir) {
  if (!obj || !outDir)
    return;
  outDir->cd();
  if (obj->InheritsFrom("TDirectory")) {
    TDirectory *srcDir = (TDirectory *)obj;
    std::cout << "  Copying directory: " << srcDir->GetName() << std::endl;
    TDirectory *newDir = outDir->mkdir(srcDir->GetName());
    TIter nextKey(srcDir->GetListOfKeys());
    TKey *key;
    while ((key = (TKey *)nextKey())) {
      TObject *subObj = key->ReadObj();
      copyObject(subObj, newDir);
    }
  } else if (obj->InheritsFrom("TTree")) {
    TTree *t = (TTree *)obj;
    std::cout << "  Copying untouched TTree: " << t->GetName() << std::endl;
    TTree *tnew = t->CloneTree(-1, "fast");
    tnew->SetDirectory(outDir);
    tnew->Write();
  } else {
    std::cout << "  Copying object: " << obj->GetName() << " ["
              << obj->ClassName() << "]" << std::endl;
    obj->Write();
  }
}

/// Process one DF_* directory
void processDF(TDirectory *dirIn, TDirectory *dirOut) {
  std::cout << "\n===================================================="
            << std::endl;
  std::cout << "▶ Processing DF folder: " << dirIn->GetName() << std::endl;

  TTree *treeBCs = nullptr;
  TTree *treeFlags = nullptr;
  std::vector<TTree *> treesWithBCid;
  std::vector<TObject *> otherObjects;

  // Inspect folder contents
  for (auto subkeyObj : *(dirIn->GetListOfKeys())) {
    TKey *subkey = (TKey *)subkeyObj;
    TObject *obj = dirIn->Get(subkey->GetName());
    if (obj->InheritsFrom(TTree::Class())) {
      TTree *tree = (TTree *)obj;
      TString tname = tree->GetName();
      if (tname.BeginsWith("O2bc_")) {
        treeBCs = tree;
        std::cout << "   Found O2bc: " << tname << std::endl;
      } else if (tname == "O2bcflag") {
        // this is a special table as it is directly joinable to O2bc
        // according to the datamodel
        treeFlags = tree;
        std::cout << "   Found O2bcflag" << std::endl;
      } else if (tree->GetBranch("fIndexBCs")) {
        treesWithBCid.push_back(tree);
        std::cout << "   Needs reindex: " << tname << std::endl;
      } else {
        otherObjects.push_back(tree);
        std::cout << "   Unaffected TTree: " << tname << std::endl;
      }
    } else {
      otherObjects.push_back(obj);
    }
  }

  if (!treeBCs) {
    std::cout << "⚠ No O2bc found in " << dirIn->GetName()
              << " → just copying objects" << std::endl;
    for (auto obj : otherObjects) {
      copyObject(obj, dirOut);
    }
    return;
  }

  // Read fGlobalBC values
  ULong64_t fGlobalBC;
  treeBCs->SetBranchAddress("fGlobalBC", &fGlobalBC);
  std::vector<ULong64_t> originalBCs(treeBCs->GetEntries());
  for (Long64_t i = 0; i < treeBCs->GetEntries(); i++) {
    treeBCs->GetEntry(i);
    originalBCs[i] = fGlobalBC;
  }

  std::cout << "   O2bc entries: " << originalBCs.size() << std::endl;

  // Build mapping
  std::vector<Int_t> indexMap(originalBCs.size(), -1);
  std::vector<ULong64_t> uniqueBCs;
  std::vector<size_t> order(originalBCs.size());
  std::iota(order.begin(), order.end(), 0);
  std::sort(order.begin(), order.end(), [&](size_t a, size_t b) {
    return originalBCs[a] < originalBCs[b];
  });
  Int_t newIdx = -1;
  ULong64_t prevVal = -1;
  std::unordered_map<size_t, std::vector<size_t>> newIndexOrigins;
  for (auto oldIdx : order) {
    ULong64_t val = originalBCs[oldIdx];
    if (newIdx < 0 || val != prevVal) {
      ++newIdx;
      prevVal = val;
      uniqueBCs.push_back(val);
    }
    indexMap[oldIdx] = newIdx;
    newIndexOrigins[newIdx].push_back(oldIdx);
  }
  std::cout << "   Unique BCs after deduplication: " << uniqueBCs.size()
            << std::endl;

  // --- Rewrite O2bc ---
  dirOut->cd();
  TTree *treeBCsOut = new TTree(treeBCs->GetName(), "fixed O2bc tree");
  std::vector<std::unique_ptr<BranchHandler>> bcBranches;
  for (auto brObj : *treeBCs->GetListOfBranches()) {
    TBranch *br = (TBranch *)brObj;
    if (TString(br->GetName()) == "fGlobalBC")
      continue;
    bcBranches.emplace_back(std::make_unique<BranchHandler>(br, treeBCsOut));
  }
  ULong64_t outBC;
  treeBCsOut->Branch("fGlobalBC", &outBC, "fGlobalBC/l");

  for (int newIdx = 0; newIdx < uniqueBCs.size(); newIdx++) {
    auto &oldIndices = newIndexOrigins[newIdx];
    if (oldIndices.empty())
      continue;
    size_t oldIdx = oldIndices.front();
    treeBCs->GetEntry(oldIdx);
    outBC = originalBCs[oldIdx];
    for (auto &bh : bcBranches) {
      bh->copyValue();
    }
    treeBCsOut->Fill();
  }
  std::cout << "   Wrote O2bc with " << treeBCsOut->GetEntries() << " entries"
            << std::endl;
  treeBCsOut->Write();

  // --- Rewrite O2bcflag ---
  if (treeFlags) {
    std::cout << "   Rebuilding O2bcflag..." << std::endl;
    dirOut->cd();

    // Create a new empty tree instead of CloneTree(0)
    TTree *treeFlagsOut = new TTree(treeFlags->GetName(), treeFlags->GetTitle());

    std::vector<std::unique_ptr<BranchHandler>> flagBranches;
    for (auto brObj : *treeFlags->GetListOfBranches()) {
      TBranch *br = (TBranch *)brObj;
      flagBranches.emplace_back(
        std::make_unique<BranchHandler>(br, treeFlagsOut));
    }

    for (int newIdx = 0; newIdx < uniqueBCs.size(); newIdx++) {
      auto &oldIndices = newIndexOrigins[newIdx];
      if (oldIndices.empty())
        continue;
      size_t oldIdx = oldIndices.front();

      treeFlags->GetEntry(oldIdx);
      for (auto &fh : flagBranches) {
        fh->copyValue();
      }
      treeFlagsOut->Fill();
    }

    std::cout << "   Wrote O2bcflag with " << treeFlagsOut->GetEntries()
            << " entries" << std::endl;
    treeFlagsOut->Write();
}

  // --- Rewrite trees with fIndexBCs ---
  for (auto tree : treesWithBCid) {
    std::cout << "   Reindexing tree " << tree->GetName() << std::endl;
    dirOut->cd();
    TTree *treeOut = tree->CloneTree(0);
    Int_t oldBCid, newBCid;
    tree->SetBranchAddress("fIndexBCs", &oldBCid);
    treeOut->SetBranchAddress("fIndexBCs", &newBCid);
    for (Long64_t i = 0; i < tree->GetEntries(); i++) {
      tree->GetEntry(i);
      newBCid = indexMap[oldBCid];
      treeOut->Fill();
    }
    std::cout << "     Wrote " << treeOut->GetEntries() << " entries"
              << std::endl;
    treeOut->Write();
  }

  // Copy unaffected objects
  for (auto obj : otherObjects) {
    copyObject(obj, dirOut);
  }
}

void AODBcRewriter(const char *inFileName = "input.root",
                   const char *outFileName = "output.root") {
  TFile *fin = TFile::Open(inFileName, "READ");
  TFile *fout = TFile::Open(outFileName, "RECREATE");
  fout->SetCompressionSettings(fin->GetCompressionSettings());
  for (auto keyObj : *(fin->GetListOfKeys())) {
    TKey *key = (TKey *)keyObj;
    TObject *obj = key->ReadObj();
    if (obj->InheritsFrom(TDirectory::Class()) &&
        TString(key->GetName()).BeginsWith("DF_"))
      processDF((TDirectory *)obj, fout->mkdir(key->GetName()));
    else {
      fout->cd();
      copyObject(obj, fout);
    }
  }
  fout->Close();
  fin->Close();
}
