//=============================================================================
// filterAO2DMCParticlesPdg.C
//
// Filter AO2D MC particles using a list of PDG-code seeds.
//
// Selection policy:
//
//   keep = selected PDG particles
//        + all ancestors of selected PDG particles
//        + all descendants of selected PDG particles
//
// IMPORTANT:
//
//   The upward and downward traversals are completely independent.
//
//   - Ancestor traversal:
//       seed -> mother -> grandmother -> ...
//     Ancestors DO NOT become daughter-expansion seeds.
//
//   - Descendant traversal:
//       seed -> daughter -> granddaughter -> ...
//     Descendants DO NOT become mother-expansion seeds.
//
// Therefore sibling branches of an ancestor are NOT automatically retained.
//
// All surviving MC-particle indices are remapped.
// Reconstructed tables are copied unchanged, while MC-label tables are remapped.
//
// fIndexSlice_Daughters stores:
//   {firstDaughter, lastDaughterInclusive}
//
// Usage:
//
//   root -l -b -q 'filterAO2DMCParticlesPdg.C("AO2D.root","AO2D_filter.root",{3122,-3122})'
//
//=============================================================================

#include <TBranch.h>
#include <TDirectory.h>
#include <TFile.h>
#include <TKey.h>
#include <TObject.h>
#include <TTree.h>

#include <fstream>
#include <iomanip>
#include <iostream>
#include <streambuf>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace
{

// Mirror everything written to std::cout/std::cerr to a text log file.
class TeeBuf : public std::streambuf
{
 public:
  TeeBuf(std::streambuf* first, std::streambuf* second)
    : mFirst(first), mSecond(second)
  {
  }

 protected:
  int overflow(int c) override
  {
    if (c == traits_type::eof()) {
      return traits_type::not_eof(c);
    }

    const char ch = static_cast<char>(c);
    const bool firstOk = mFirst->sputc(ch) != traits_type::eof();
    const bool secondOk = mSecond->sputc(ch) != traits_type::eof();

    return (firstOk && secondOk) ? c : traits_type::eof();
  }

  int sync() override
  {
    const int firstStatus = mFirst->pubsync();
    const int secondStatus = mSecond->pubsync();
    return (firstStatus == 0 && secondStatus == 0) ? 0 : -1;
  }

 private:
  std::streambuf* mFirst = nullptr;
  std::streambuf* mSecond = nullptr;
};

constexpr int kMaxMothers = 256;
constexpr int kMaxCaloLabels = 4096;

//_____________________________________________________________________________
struct GlobalSummary {
  Long64_t directoriesProcessed = 0;

  Long64_t mcParticlesInitial = 0;
  Long64_t pdgSeeds = 0;
  Long64_t ancestorsAdded = 0;
  Long64_t descendantsAdded = 0;
  Long64_t mcParticlesKept = 0;
  Long64_t mcParticlesRemoved = 0;

  Long64_t preservedDaughterSlices = 0;
  Long64_t clearedDaughterSlices = 0;

  Long64_t invalidMotherReferences = 0;
  Long64_t invalidDaughterSlices = 0;

  Long64_t validTrackLabels = 0;
  Long64_t invalidatedTrackLabels = 0;
  Long64_t validMFTTrackLabels = 0;
  Long64_t invalidatedMFTTrackLabels = 0;
  Long64_t validFwdTrackLabels = 0;
  Long64_t invalidatedFwdTrackLabels = 0;
  Long64_t validCaloLabels = 0;
  Long64_t invalidatedCaloLabels = 0;
};

//_____________________________________________________________________________
struct KeptParticle {
  int oldId = -1;
  int mcCollisionId = -1;
  int pdgCode = 0;
  int statusCode = 0;
  UChar_t flags = 0;

  std::vector<int> mothers;

  int firstDaughter = -1;
  int lastDaughter = -1;

  float weight = 0.f;
  float px = 0.f;
  float py = 0.f;
  float pz = 0.f;
  float e = 0.f;
  float vx = 0.f;
  float vy = 0.f;
  float vz = 0.f;
  float vt = 0.f;
};

//_____________________________________________________________________________
int remapId(int oldId, const std::vector<int>& oldToNew)
{
  if (oldId < 0 || oldId >= static_cast<int>(oldToNew.size())) {
    return -1;
  }
  return oldToNew[oldId];
}

//_____________________________________________________________________________
bool hasBranch(TTree* tree, const char* branchName)
{
  if (!tree->GetBranch(branchName)) {
    std::cerr << "Missing branch " << branchName
              << " in tree " << tree->GetName() << "\n";
    return false;
  }
  return true;
}

//_____________________________________________________________________________
bool isAffectedTree(const std::string& name)
{
  static const std::unordered_set<std::string> affected = {
    "O2mcparticle_001",
    "O2mctracklabel",
    "O2mcmfttracklabel",
    "O2mcfwdtracklabel",
    "O2mccalolabel_001"
  };

  return affected.count(name) > 0;
}

//_____________________________________________________________________________
void copyDirectory(TDirectory* inDir, TDirectory* outDir)
{
  TIter next(inDir->GetListOfKeys());
  TKey* key = nullptr;

  while ((key = static_cast<TKey*>(next()))) {
    const TKey* latestKey = inDir->GetKey(key->GetName());
    if (latestKey && key->GetCycle() != latestKey->GetCycle()) {
      continue;
    }
    TObject* obj = key->ReadObj();
    if (!obj) {
      continue;
    }

    const std::string name = obj->GetName();

    if (obj->InheritsFrom(TDirectory::Class())) {
      outDir->cd();
      auto* newDir = outDir->mkdir(name.c_str());

      if (!newDir) {
        std::cerr << "Could not create output directory "
                  << name << "\n";
        delete obj;
        continue;
      }

      copyDirectory(static_cast<TDirectory*>(obj), newDir);
      delete obj;
      continue;
    }

    if (obj->InheritsFrom(TTree::Class())) {
      if (isAffectedTree(name)) {
        delete obj;
        continue;
      }

      auto* inTree = static_cast<TTree*>(obj);

      outDir->cd();
      auto* outTree = inTree->CloneTree(-1, "fast");

      if (!outTree) {
        std::cerr << "Could not clone tree " << name << "\n";
        delete obj;
        continue;
      }

      outTree->Write(name.c_str(), TObject::kOverwrite);
      delete obj;
      continue;
    }

    outDir->cd();
    obj->Write(name.c_str(), TObject::kOverwrite);
    delete obj;
  }
}

//_____________________________________________________________________________
bool rewriteMCParticles(TDirectory* inDir,
                        TDirectory* outDir,
                        std::vector<int>& oldToNew,
                        const std::unordered_set<int>& keptPDGs,
                        GlobalSummary& summary)
{
  auto* inTree =
    dynamic_cast<TTree*>(inDir->Get("O2mcparticle_001"));

  if (!inTree) {
    std::cerr << "Missing O2mcparticle_001 in directory "
              << inDir->GetName() << "\n";
    return false;
  }

  const std::vector<const char*> requiredBranches = {
    "fIndexMcCollisions",
    "fPdgCode",
    "fStatusCode",
    "fFlags",
    "fIndexArray_Mothers_size",
    "fIndexArray_Mothers",
    "fIndexSlice_Daughters",
    "fWeight",
    "fPx",
    "fPy",
    "fPz",
    "fE",
    "fVx",
    "fVy",
    "fVz",
    "fVt"
  };

  for (const char* branchName : requiredBranches) {
    if (!hasBranch(inTree, branchName)) {
      return false;
    }
  }

  const int maximumMothers =
    static_cast<int>(inTree->GetMaximum("fIndexArray_Mothers_size"));

  if (maximumMothers > kMaxMothers) {
    std::cerr
      << "Fatal: maximum mother-array size in "
      << inDir->GetName()
      << " is " << maximumMothers
      << ", while the allocated buffer supports only "
      << kMaxMothers << "\n";
    return false;
  }

  int mcCollisionId = -1;
  int pdgCode = 0;
  int statusCode = 0;
  UChar_t flags = 0;

  int mothersSize = 0;
  int mothers[kMaxMothers] = {};

  int daughtersSlice[2] = {-1, -1};

  float weight = 0.f;
  float px = 0.f;
  float py = 0.f;
  float pz = 0.f;
  float e = 0.f;
  float vx = 0.f;
  float vy = 0.f;
  float vz = 0.f;
  float vt = 0.f;

  inTree->SetBranchAddress("fIndexMcCollisions", &mcCollisionId);
  inTree->SetBranchAddress("fPdgCode", &pdgCode);
  inTree->SetBranchAddress("fStatusCode", &statusCode);
  inTree->SetBranchAddress("fFlags", &flags);
  inTree->SetBranchAddress("fIndexArray_Mothers_size", &mothersSize);
  inTree->SetBranchAddress("fIndexArray_Mothers", mothers);
  inTree->SetBranchAddress("fIndexSlice_Daughters", daughtersSlice);
  inTree->SetBranchAddress("fWeight", &weight);
  inTree->SetBranchAddress("fPx", &px);
  inTree->SetBranchAddress("fPy", &py);
  inTree->SetBranchAddress("fPz", &pz);
  inTree->SetBranchAddress("fE", &e);
  inTree->SetBranchAddress("fVx", &vx);
  inTree->SetBranchAddress("fVy", &vy);
  inTree->SetBranchAddress("fVz", &vz);
  inTree->SetBranchAddress("fVt", &vt);

  const Long64_t nEntries = inTree->GetEntries();

  std::vector<std::vector<int>> originalMothers(nEntries);
  std::vector<int> firstDaughter(nEntries, -1);
  std::vector<int> lastDaughter(nEntries, -1);

  std::vector<char> selectedPDG(nEntries, 0);
  std::vector<char> keep(nEntries, 0);

  Long64_t nPDGSelected = 0;
  Long64_t nInvalidMotherReferences = 0;
  Long64_t nInvalidDaughterSlices = 0;

  //===========================================================================
  // First pass: cache genealogy and mark the original PDG seeds.
  //===========================================================================
  for (Long64_t i = 0; i < nEntries; ++i) {
    inTree->GetEntry(i);

    if (mothersSize < 0 || mothersSize > kMaxMothers) {
      std::cerr << "Invalid mother-array size "
                << mothersSize
                << " at MC-particle entry "
                << i << "\n";
      return false;
    }

    originalMothers[i].reserve(mothersSize);

    for (int im = 0; im < mothersSize; ++im) {
      const int mother = mothers[im];

      if (mother < 0) {
        continue;
      }

      if (mother >= nEntries) {
        ++nInvalidMotherReferences;
        continue;
      }

      originalMothers[i].push_back(mother);
    }

    const int first = daughtersSlice[0];
    const int last = daughtersSlice[1];

    if (first < 0 || last < first) {
      firstDaughter[i] = -1;
      lastDaughter[i] = -1;
    } else if (first >= nEntries || last >= nEntries) {
      ++nInvalidDaughterSlices;
      firstDaughter[i] = -1;
      lastDaughter[i] = -1;
    } else {
      firstDaughter[i] = first;
      lastDaughter[i] = last;
    }

    if (keptPDGs.count(pdgCode) > 0) {
      selectedPDG[i] = 1;
      keep[i] = 1;
      ++nPDGSelected;
    }
  }

  //===========================================================================
  // UPWARD traversal.
  //
  // Start ONLY from original PDG seeds.
  // Newly found mothers can generate further mothers, but NEVER daughters.
  //===========================================================================
  std::vector<char> visitedUp(nEntries, 0);
  std::vector<int> ancestorQueue;
  ancestorQueue.reserve(nPDGSelected);

  for (Long64_t i = 0; i < nEntries; ++i) {
    if (selectedPDG[i]) {
      visitedUp[i] = 1;
      ancestorQueue.push_back(static_cast<int>(i));
    }
  }

  Long64_t nAncestorsAdded = 0;
  size_t upPosition = 0;

  while (upPosition < ancestorQueue.size()) {
    const int particleId = ancestorQueue[upPosition++];

    for (const int mother : originalMothers[particleId]) {
      if (!visitedUp[mother]) {
        visitedUp[mother] = 1;
        ancestorQueue.push_back(mother);

        if (!keep[mother]) {
          keep[mother] = 1;
          ++nAncestorsAdded;
        }
      }
    }
  }

  //===========================================================================
  // DOWNWARD traversal.
  //
  // Again start ONLY from original PDG seeds.
  // Newly found daughters can generate further daughters, but NEVER mothers.
  //===========================================================================
  std::vector<char> visitedDown(nEntries, 0);
  std::vector<int> descendantQueue;
  descendantQueue.reserve(nPDGSelected);

  for (Long64_t i = 0; i < nEntries; ++i) {
    if (selectedPDG[i]) {
      visitedDown[i] = 1;
      descendantQueue.push_back(static_cast<int>(i));
    }
  }

  Long64_t nDescendantsAdded = 0;
  size_t downPosition = 0;

  while (downPosition < descendantQueue.size()) {
    const int particleId = descendantQueue[downPosition++];

    const int first = firstDaughter[particleId];
    const int last = lastDaughter[particleId];

    if (first < 0 || last < first) {
      continue;
    }

    for (int daughter = first; daughter <= last; ++daughter) {
      if (!visitedDown[daughter]) {
        visitedDown[daughter] = 1;
        descendantQueue.push_back(daughter);

        if (!keep[daughter]) {
          keep[daughter] = 1;
          ++nDescendantsAdded;
        }
      }
    }
  }

  //===========================================================================
  // Construct old-to-new index map.
  //===========================================================================
  oldToNew.assign(nEntries, -1);

  int newId = 0;

  for (Long64_t i = 0; i < nEntries; ++i) {
    if (keep[i]) {
      oldToNew[i] = newId++;
    }
  }

  const Long64_t nKept = newId;
  const Long64_t nRemoved = nEntries - nKept;

  std::cout
    << "O2mcparticle_001: PDG seeds             = "
    << nPDGSelected << " / " << nEntries << "\n";

  std::cout
    << "O2mcparticle_001: ancestors added       = "
    << nAncestorsAdded << "\n";

  std::cout
    << "O2mcparticle_001: descendants added     = "
    << nDescendantsAdded << "\n";

  std::cout
    << "O2mcparticle_001: kept after selection  = "
    << nKept
    << " / " << nEntries
    << ", survival fraction = "
    << (nEntries > 0
          ? static_cast<double>(nKept) /
              static_cast<double>(nEntries)
          : 0.0)
    << "\n";

  //===========================================================================
  // Second pass: cache retained particle payloads and remap mothers.
  //===========================================================================
  std::vector<KeptParticle> kept;
  kept.reserve(newId);

  for (Long64_t i = 0; i < nEntries; ++i) {
    if (!keep[i]) {
      continue;
    }

    inTree->GetEntry(i);

    KeptParticle particle;

    particle.oldId = static_cast<int>(i);
    particle.mcCollisionId = mcCollisionId;
    particle.pdgCode = pdgCode;
    particle.statusCode = statusCode;
    particle.flags = flags;
    particle.weight = weight;
    particle.px = px;
    particle.py = py;
    particle.pz = pz;
    particle.e = e;
    particle.vx = vx;
    particle.vy = vy;
    particle.vz = vz;
    particle.vt = vt;

    // Keep only mother references that survived.
    for (const int oldMother : originalMothers[i]) {
      const int newMother = remapId(oldMother, oldToNew);
      if (newMother >= 0) {
        particle.mothers.push_back(newMother);
      }
    }

    particle.firstDaughter = firstDaughter[i];
    particle.lastDaughter = lastDaughter[i];

    kept.push_back(std::move(particle));
  }

  //===========================================================================
  // Create output tree.
  //===========================================================================
  outDir->cd();

  auto* outTree = inTree->CloneTree(0);

  if (!outTree) {
    std::cerr << "Could not create output O2mcparticle_001\n";
    return false;
  }

  Long64_t nPreservedDaughterSlices = 0;
  Long64_t nClearedDaughterSlices = 0;

  //===========================================================================
  // Third pass: write retained particles with remapped indices.
  //
  // Preserve the surviving daughters if their remapped indices remain
  // contiguous in the filtered table.
  //===========================================================================
  for (const auto& particle : kept) {
    mcCollisionId = particle.mcCollisionId;
    pdgCode = particle.pdgCode;
    statusCode = particle.statusCode;
    flags = particle.flags;
    weight = particle.weight;
    px = particle.px;
    py = particle.py;
    pz = particle.pz;
    e = particle.e;
    vx = particle.vx;
    vy = particle.vy;
    vz = particle.vz;
    vt = particle.vt;

    mothersSize =
      static_cast<int>(particle.mothers.size());

    if (mothersSize > kMaxMothers) {
      std::cerr
        << "Fatal: remapped mother list has size "
        << mothersSize
        << ", exceeding the buffer size "
        << kMaxMothers << "\n";
      delete outTree;
      return false;
    }

    for (int im = 0; im < kMaxMothers; ++im) {
      mothers[im] = -1;
    }

    for (int im = 0; im < mothersSize; ++im) {
      mothers[im] = particle.mothers[im];
    }

    daughtersSlice[0] = -1;
    daughtersSlice[1] = -1;

    if (particle.firstDaughter >= 0 &&
        particle.lastDaughter >= particle.firstDaughter) {

      int firstNewDaughter = -1;
      int lastNewDaughter = -1;

      for (int oldDaughter = particle.firstDaughter;
           oldDaughter <= particle.lastDaughter;
           ++oldDaughter) {

        const int newDaughter =
          remapId(oldDaughter, oldToNew);

        if (newDaughter < 0) {
          continue;
        }

        if (firstNewDaughter < 0) {
          firstNewDaughter = newDaughter;
        }

        lastNewDaughter = newDaughter;
      }

      if (firstNewDaughter >= 0 &&
          lastNewDaughter >= firstNewDaughter) {

        daughtersSlice[0] = firstNewDaughter;
        daughtersSlice[1] = lastNewDaughter;
        ++nPreservedDaughterSlices;

      } else {
        ++nClearedDaughterSlices;
      }
    }

    outTree->Fill();
  }

  outTree->Write(
    "O2mcparticle_001",
    TObject::kOverwrite);

  std::cout
    << "O2mcparticle_001: preserved daughter slices = "
    << nPreservedDaughterSlices << "\n";

  std::cout
    << "O2mcparticle_001: cleared daughter slices   = "
    << nClearedDaughterSlices << "\n";

  summary.mcParticlesInitial += nEntries;
  summary.pdgSeeds += nPDGSelected;
  summary.ancestorsAdded += nAncestorsAdded;
  summary.descendantsAdded += nDescendantsAdded;
  summary.mcParticlesKept += nKept;
  summary.mcParticlesRemoved += nRemoved;
  summary.preservedDaughterSlices += nPreservedDaughterSlices;
  summary.clearedDaughterSlices += nClearedDaughterSlices;
  summary.invalidMotherReferences += nInvalidMotherReferences;
  summary.invalidDaughterSlices += nInvalidDaughterSlices;

  return true;
}

//_____________________________________________________________________________
void rewriteSingleLabelTable(
  TDirectory* inDir,
  TDirectory* outDir,
  const char* treeName,
  const std::vector<int>& oldToNew,
  Long64_t& globalValidLabels,
  Long64_t& globalInvalidatedLabels)
{
  auto* inTree =
    dynamic_cast<TTree*>(inDir->Get(treeName));

  if (!inTree) {
    return;
  }

  if (!hasBranch(inTree, "fIndexMcParticles")) {
    std::cerr
      << "Tree " << treeName
      << " will not be written because its expected "
      << "MC-particle index branch is missing.\n";
    return;
  }

  int mcParticleId = -1;

  inTree->SetBranchAddress(
    "fIndexMcParticles",
    &mcParticleId);

  outDir->cd();

  auto* outTree = inTree->CloneTree(0);

  if (!outTree) {
    std::cerr << "Could not create output tree "
              << treeName << "\n";
    return;
  }

  const Long64_t nEntries = inTree->GetEntries();

  Long64_t nValidLabels = 0;
  Long64_t nInvalidatedLabels = 0;

  for (Long64_t i = 0; i < nEntries; ++i) {
    inTree->GetEntry(i);

    mcParticleId =
      remapId(mcParticleId, oldToNew);

    if (mcParticleId >= 0) {
      ++nValidLabels;
    } else {
      ++nInvalidatedLabels;
    }

    outTree->Fill();
  }

  outTree->Write(
    treeName,
    TObject::kOverwrite);

  std::cout
    << treeName
    << ": valid remapped labels = "
    << nValidLabels
    << ", invalidated labels = "
    << nInvalidatedLabels
    << "\n";

  globalValidLabels += nValidLabels;
  globalInvalidatedLabels += nInvalidatedLabels;
}

//_____________________________________________________________________________
void rewriteCaloLabels(
  TDirectory* inDir,
  TDirectory* outDir,
  const std::vector<int>& oldToNew,
  GlobalSummary& summary)
{
  auto* inTree =
    dynamic_cast<TTree*>(
      inDir->Get("O2mccalolabel_001"));

  if (!inTree) {
    return;
  }

  auto* sizeBranch =
    inTree->GetBranch(
      "fIndexArrayMcParticles_size");

  auto* idsBranch =
    inTree->GetBranch(
      "fIndexArrayMcParticles");

  if (!sizeBranch || !idsBranch) {
    std::cout
      << "O2mccalolabel_001: expected array branches "
      << "not found; copying unchanged\n";

    outDir->cd();

    auto* outTree =
      inTree->CloneTree(-1, "fast");

    if (outTree) {
      outTree->Write(
        "O2mccalolabel_001",
        TObject::kOverwrite);
    }

    return;
  }

  const int maximumLabels =
    static_cast<int>(
      inTree->GetMaximum("fIndexArrayMcParticles_size"));

  if (maximumLabels > kMaxCaloLabels) {
    std::cerr
      << "Fatal: maximum number of calorimeter labels is "
      << maximumLabels
      << ", while the buffer supports only "
      << kMaxCaloLabels
      << ". O2mccalolabel_001 will not be written.\n";
    return;
  }

  int idsSize = 0;
  int ids[kMaxCaloLabels] = {};

  inTree->SetBranchAddress(
    "fIndexArrayMcParticles_size",
    &idsSize);

  inTree->SetBranchAddress(
    "fIndexArrayMcParticles",
    ids);

  outDir->cd();

  auto* outTree = inTree->CloneTree(0);

  if (!outTree) {
    std::cerr
      << "Could not create output O2mccalolabel_001\n";
    return;
  }

  const Long64_t nEntries = inTree->GetEntries();

  Long64_t nValidLabels = 0;
  Long64_t nInvalidatedLabels = 0;

  for (Long64_t i = 0; i < nEntries; ++i) {
    inTree->GetEntry(i);

    if (idsSize < 0 || idsSize > kMaxCaloLabels) {
      std::cerr
        << "Invalid calorimeter-label array size "
        << idsSize
        << " at entry " << i << "\n";
      delete outTree;
      return;
    }

    for (int j = 0; j < idsSize; ++j) {
      ids[j] = remapId(ids[j], oldToNew);

      if (ids[j] >= 0) {
        ++nValidLabels;
      } else {
        ++nInvalidatedLabels;
      }
    }

    outTree->Fill();
  }

  outTree->Write(
    "O2mccalolabel_001",
    TObject::kOverwrite);

  std::cout
    << "O2mccalolabel_001: valid remapped labels = "
    << nValidLabels
    << ", invalidated labels = "
    << nInvalidatedLabels
    << "\n";

  summary.validCaloLabels += nValidLabels;
  summary.invalidatedCaloLabels += nInvalidatedLabels;
}

//_____________________________________________________________________________
double bytesToMB(Long64_t bytes)
{
  return static_cast<double>(bytes) / (1024.0 * 1024.0);
}

//_____________________________________________________________________________
void printGlobalSummary(const GlobalSummary& summary,
                        Long64_t inputBytes,
                        Long64_t outputBytes)
{
  const double retainedFraction =
    summary.mcParticlesInitial > 0
      ? 100.0 *
          static_cast<double>(summary.mcParticlesKept) /
          static_cast<double>(summary.mcParticlesInitial)
      : 0.0;

  const double removedFraction =
    summary.mcParticlesInitial > 0
      ? 100.0 *
          static_cast<double>(summary.mcParticlesRemoved) /
          static_cast<double>(summary.mcParticlesInitial)
      : 0.0;

  const double seedFraction =
    summary.mcParticlesInitial > 0
      ? 100.0 *
          static_cast<double>(summary.pdgSeeds) /
          static_cast<double>(summary.mcParticlesInitial)
      : 0.0;

  const double ancestorFractionOfKept =
    summary.mcParticlesKept > 0
      ? 100.0 *
          static_cast<double>(summary.ancestorsAdded) /
          static_cast<double>(summary.mcParticlesKept)
      : 0.0;

  const double descendantFractionOfKept =
    summary.mcParticlesKept > 0
      ? 100.0 *
          static_cast<double>(summary.descendantsAdded) /
          static_cast<double>(summary.mcParticlesKept)
      : 0.0;

  const double storageReduction =
    inputBytes > 0
      ? 100.0 *
          (1.0 -
           static_cast<double>(outputBytes) /
             static_cast<double>(inputBytes))
      : 0.0;

  std::cout
    << "\n============================================================\n"
    << "\nGLOBAL SUMMARY [ASYMMETRIC PDG FILTER]\n"
    << "\n============================================================\n\n";

  std::cout << std::fixed << std::setprecision(2);

  std::cout
    << "Directories processed:              "
    << summary.directoriesProcessed << "\n";

  std::cout
    << "MC particles initial:               "
    << summary.mcParticlesInitial << "\n";

  std::cout
    << "PDG-selected seed particles:        "
    << summary.pdgSeeds
    << "  (" << seedFraction << " % of initial)\n";

  std::cout
    << "Ancestors added:                    "
    << summary.ancestorsAdded
    << "  (" << ancestorFractionOfKept << " % of kept)\n";

  std::cout
    << "Descendants added:                  "
    << summary.descendantsAdded
    << "  (" << descendantFractionOfKept << " % of kept)\n";

  std::cout
    << "MC particles kept:                  "
    << summary.mcParticlesKept << "\n";

  std::cout
    << "MC particles removed:               "
    << summary.mcParticlesRemoved << "\n";

  std::cout
    << "Retained fraction:                  "
    << retainedFraction << " %\n";

  std::cout
    << "Removed fraction:                   "
    << removedFraction << " %\n";

  std::cout
    << "Preserved daughter slices:          "
    << summary.preservedDaughterSlices << "\n";

  std::cout
    << "Cleared daughter slices:            "
    << summary.clearedDaughterSlices << "\n";

  if (summary.invalidMotherReferences > 0) {
    std::cout
      << "Invalid original mother refs:       "
      << summary.invalidMotherReferences << "\n";
  }

  if (summary.invalidDaughterSlices > 0) {
    std::cout
      << "Invalid original daughter slices:   "
      << summary.invalidDaughterSlices << "\n";
  }

  std::cout
    << "\nTrack labels valid / invalidated:    "
    << summary.validTrackLabels
    << " / " << summary.invalidatedTrackLabels << "\n";

  std::cout
    << "MFT labels valid / invalidated:      "
    << summary.validMFTTrackLabels
    << " / " << summary.invalidatedMFTTrackLabels << "\n";

  std::cout
    << "Fwd labels valid / invalidated:      "
    << summary.validFwdTrackLabels
    << " / " << summary.invalidatedFwdTrackLabels << "\n";

  std::cout
    << "Calo labels valid / invalidated:     "
    << summary.validCaloLabels
    << " / " << summary.invalidatedCaloLabels << "\n";

  std::cout
    << "\nInput file size:                     "
    << bytesToMB(inputBytes) << " MB\n";

  std::cout
    << "Output file size:                    "
    << bytesToMB(outputBytes) << " MB\n";

  std::cout
    << "Storage reduction:                   "
    << storageReduction << " %\n";

  std::cout
    << "\n============================================================\n";
}

} // namespace

//_____________________________________________________________________________
void filterAO2DMCParticlesPdg(
  const char* input = "AO2D.root",
  const char* output = "AO2D_filter.root",
  const std::vector<int>& pdgs = {},
  const char* logFileName = "filterAO2DMCParticlesPdg.log")
{
  if (!input || !output) {
    std::cerr << "Input or output filename is null\n";
    return;
  }

  if (pdgs.empty()) {
    std::cerr
      << "The requested PDG-code list is empty. "
      << "Nothing will be filtered.\n";
    return;
  }

  std::ofstream logFile;
  std::streambuf* originalCoutBuf = std::cout.rdbuf();
  std::streambuf* originalCerrBuf = std::cerr.rdbuf();

  if (logFileName && logFileName[0] != '\0') {
    logFile.open(logFileName, std::ios::out | std::ios::trunc);

    if (!logFile.is_open()) {
      std::cerr << "Cannot create log file "
                << logFileName << "\n";
      return;
    }
  }

  TeeBuf coutTee(originalCoutBuf, logFile.is_open() ? logFile.rdbuf() : originalCoutBuf);
  TeeBuf cerrTee(originalCerrBuf, logFile.is_open() ? logFile.rdbuf() : originalCerrBuf);

  if (logFile.is_open()) {
    std::cout.rdbuf(&coutTee);
    std::cerr.rdbuf(&cerrTee);
  }

  // Restore the original stream buffers automatically before returning.
  struct StreamRestorer {
    std::streambuf* coutBuf;
    std::streambuf* cerrBuf;
    ~StreamRestorer()
    {
      std::cout.flush();
      std::cerr.flush();
      std::cout.rdbuf(coutBuf);
      std::cerr.rdbuf(cerrBuf);
    }
  } streamRestorer{originalCoutBuf, originalCerrBuf};

  const std::unordered_set<int> keptPDGs(
    pdgs.begin(),
    pdgs.end());

  auto* inFile = TFile::Open(input, "READ");

  if (!inFile || inFile->IsZombie()) {
    std::cerr
      << "Cannot open input file "
      << input << "\n";

    if (inFile) {
      inFile->Close();
      delete inFile;
    }

    return;
  }

  const Long64_t inputBytes = inFile->GetSize();

  auto* outFile = TFile::Open(output, "RECREATE", "", 505);

  if (!outFile || outFile->IsZombie()) {
    std::cerr
      << "Cannot create output file "
      << output << "\n";

    if (outFile) {
      outFile->Close();
      delete outFile;
    }

    inFile->Close();
    delete inFile;
    return;
  }

  std::cout
    << "\nFiltering MC particles by PDG code\n\n";

  std::cout
    << "  input file:   " << input << "\n"
    << "  output file:  " << output << "\n"
    << "  log file:     "
    << (logFile.is_open() ? logFileName : "(disabled)") << "\n"
    << "  PDG seeds:   ";

  for (const int pdg : pdgs) {
    std::cout << " " << pdg;
  }

  std::cout
    << "\n"
    << "  ancestry:     recursive mothers from original PDG seeds only\n"
    << "  descendants:  recursive daughters from original PDG seeds only\n"
    << "  side branches from ancestors: NOT kept\n"
    << "  reco tables:  kept unchanged; MC-particle labels remapped\n";

  GlobalSummary summary;

  TIter next(inFile->GetListOfKeys());
  TKey* key = nullptr;

  while ((key = static_cast<TKey*>(next()))) {
    const TKey* latestKey = inFile->GetKey(key->GetName());
    if (latestKey && key->GetCycle() != latestKey->GetCycle()) {
      continue;
    }
    TObject* obj = key->ReadObj();

    if (!obj) {
      continue;
    }

    if (std::string(key->GetName()) == "metaData") {
      outFile->cd();
      obj->Write("metaData", TObject::kSingleKey | TObject::kOverwrite);
      delete obj;
      continue;
    }

    const std::string name = obj->GetName();

    if (name == "parentFiles") {
      outFile->cd();
      obj->Write("parentFiles", TObject::kSingleKey | TObject::kOverwrite);
      delete obj;
      continue;
    }

    if (!obj->InheritsFrom(TDirectory::Class())) {
      outFile->cd();
      obj->Write(name.c_str(), TObject::kOverwrite);
      delete obj;
      continue;
    }

    auto* inDir =
      static_cast<TDirectory*>(obj);

    outFile->cd();

    auto* outDir =
      outFile->mkdir(name.c_str());

    if (!outDir) {
      std::cerr
        << "Could not create output directory "
        << name << "\n";
      delete obj;
      continue;
    }

    std::cout
      << "\nProcessing directory "
      << name << "\n";

    copyDirectory(inDir, outDir);

    std::vector<int> oldToNew;

    const bool mcParticlesRewritten =
      rewriteMCParticles(
        inDir,
        outDir,
        oldToNew,
        keptPDGs,
        summary);

    if (mcParticlesRewritten) {
      ++summary.directoriesProcessed;

      rewriteSingleLabelTable(
        inDir,
        outDir,
        "O2mctracklabel",
        oldToNew,
        summary.validTrackLabels,
        summary.invalidatedTrackLabels);

      rewriteSingleLabelTable(
        inDir,
        outDir,
        "O2mcmfttracklabel",
        oldToNew,
        summary.validMFTTrackLabels,
        summary.invalidatedMFTTrackLabels);

      rewriteSingleLabelTable(
        inDir,
        outDir,
        "O2mcfwdtracklabel",
        oldToNew,
        summary.validFwdTrackLabels,
        summary.invalidatedFwdTrackLabels);

      rewriteCaloLabels(
        inDir,
        outDir,
        oldToNew,
        summary);

    } else {
      std::cerr
        << "MC particles were not rewritten in directory "
        << name
        << "; associated label tables were not rewritten.\n";
    }

    delete obj;
  }

  outFile->Flush();

  const Long64_t outputBytes = outFile->GetSize();

  printGlobalSummary(
    summary,
    inputBytes,
    outputBytes);

  outFile->Close();
  inFile->Close();

  delete outFile;
  delete inFile;

  std::cout
    << "\nDone. Written "
    << output << "\n";

  if (logFile.is_open()) {
    std::cout
      << "Log written to "
      << logFileName << "\n";
  }
}
