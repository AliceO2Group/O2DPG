//=============================================================================
// filterAO2DGapTriggeredMCEvents.C
//
// Filter MC particles in gap-triggered AO2Ds while keeping all reconstructed
// information unchanged. minimumBiasSubGeneratorId identifies MB events; any
// other sub-generator is treated as interesting.
//
// Keep:
//   - all particles from interesting MC events;
//   - MB particles matched to tracks reconstructed in interesting events;
//   - recursively, all mothers and descendants of rescued cross-event particles.
// Removed MC-particle references are remapped to -1. Daughter slices are kept
// for the surviving daughters, preserving their order.
//
// Rewritten: O2mcparticle_001, O2mctracklabel, O2mcmfttracklabel,
//            O2mcfwdtracklabel, O2mccalolabel_001.
// All other AO2D objects are copied unchanged.
//
// Usage:
//   root -l -b -q 'filterAO2DGapTriggeredMCEvents.C("AO2D.root","AO2D_filter.root",0)'
//
// Alberto Calivà (alberto.caliva@cern.ch)
//=============================================================================
#include <TBranch.h>
#include <TDirectory.h>
#include <TFile.h>
#include <TKey.h>
#include <TTree.h>
#include "SimulationDataFormat/MCGenProperties.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <initializer_list>
#include <iostream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
namespace {
constexpr int kMaxMothers = 256;
constexpr int kMaxCaloLabels = 4096;
struct LabelDiagnostics {
  Long64_t crossEventAssociations = 0;
  Long64_t uniqueParticlesAdded = 0;
  Long64_t rows = 0;
  Long64_t invalidated = 0;
};
struct DirectoryDiagnostics {
  std::string name;
  Long64_t mcCollisionsTotal = 0;
  Long64_t mcCollisionsInteresting = 0;
  Long64_t mcCollisionsNonInteresting = 0;
  Long64_t recoCollisionsTotal = 0;
  Long64_t recoCollisionsInteresting = 0;
  Long64_t particlesInitial = 0;
  Long64_t particlesInterestingEvents = 0;
  Long64_t particlesMinimumBiasEvents = 0;
  Long64_t particlesInterestingSeeds = 0;
  Long64_t particlesCrossEventAdded = 0;
  Long64_t particlesDirectDaughtersAdded = 0;
  Long64_t particlesMotherAncestryAdded = 0;
  Long64_t particlesRetained = 0;
  Long64_t particlesRemoved = 0;
  Long64_t emptyDaughterSlicesCleared = 0;
  LabelDiagnostics tracks;
  LabelDiagnostics mft;
  LabelDiagnostics fwd;
  Long64_t caloRows = 0;
  Long64_t caloInvalidated = 0;
};
struct GlobalDiagnostics {
  Long64_t directoriesProcessed = 0;
  Long64_t directoriesFailed = 0;
  Long64_t mcCollisionsTotal = 0;
  Long64_t mcCollisionsInteresting = 0;
  Long64_t mcCollisionsNonInteresting = 0;
  Long64_t recoCollisionsTotal = 0;
  Long64_t recoCollisionsInteresting = 0;
  Long64_t particlesInitial = 0;
  Long64_t particlesInterestingEvents = 0;
  Long64_t particlesMinimumBiasEvents = 0;
  Long64_t particlesInterestingSeeds = 0;
  Long64_t particlesCrossEventAdded = 0;
  Long64_t particlesDirectDaughtersAdded = 0;
  Long64_t particlesMotherAncestryAdded = 0;
  Long64_t particlesRetained = 0;
  Long64_t particlesRemoved = 0;
  Long64_t emptyDaughterSlicesCleared = 0;
  LabelDiagnostics tracks;
  LabelDiagnostics mft;
  LabelDiagnostics fwd;
  Long64_t caloRows = 0;
  Long64_t caloInvalidated = 0;
};
void accumulateLabelDiagnostics(LabelDiagnostics& global, const LabelDiagnostics& local) {
  global.crossEventAssociations += local.crossEventAssociations;
  global.uniqueParticlesAdded += local.uniqueParticlesAdded;
  global.rows += local.rows;
  global.invalidated += local.invalidated;
}
void accumulateDirectoryDiagnostics(GlobalDiagnostics& global,
                                    const DirectoryDiagnostics& local) {
  ++global.directoriesProcessed;
  global.mcCollisionsTotal += local.mcCollisionsTotal;
  global.mcCollisionsInteresting += local.mcCollisionsInteresting;
  global.mcCollisionsNonInteresting += local.mcCollisionsNonInteresting;
  global.recoCollisionsTotal += local.recoCollisionsTotal;
  global.recoCollisionsInteresting += local.recoCollisionsInteresting;
  global.particlesInitial += local.particlesInitial;
  global.particlesInterestingEvents += local.particlesInterestingEvents;
  global.particlesMinimumBiasEvents += local.particlesMinimumBiasEvents;
  global.particlesInterestingSeeds += local.particlesInterestingSeeds;
  global.particlesCrossEventAdded += local.particlesCrossEventAdded;
  global.particlesDirectDaughtersAdded += local.particlesDirectDaughtersAdded;
  global.particlesMotherAncestryAdded += local.particlesMotherAncestryAdded;
  global.particlesRetained += local.particlesRetained;
  global.particlesRemoved += local.particlesRemoved;
  global.emptyDaughterSlicesCleared += local.emptyDaughterSlicesCleared;
  accumulateLabelDiagnostics(global.tracks, local.tracks);
  accumulateLabelDiagnostics(global.mft, local.mft);
  accumulateLabelDiagnostics(global.fwd, local.fwd);
  global.caloRows += local.caloRows;
  global.caloInvalidated += local.caloInvalidated;
}
double fractionPercent(Long64_t numerator, Long64_t denominator) {
  return denominator > 0 ? 100.0 * static_cast<double>(numerator) / static_cast<double>(denominator) : 0.0;
}
Long64_t getFileSizeBytes(const char* fileName) {
  std::ifstream stream(fileName, std::ios::binary | std::ios::ate);
  if (!stream) {
    return -1;
  }
  return static_cast<Long64_t>(stream.tellg());
}
std::string makeDefaultLogFileName(const char* outputFileName) {
  std::string name(outputFileName);
  const std::string suffix = ".root";
  if (name.size() >= suffix.size() &&
      name.compare(name.size() - suffix.size(), suffix.size(), suffix) == 0) {
    name.resize(name.size() - suffix.size());
  }
  return name + "_log.txt";
}
std::string currentTimeString() {
  const std::time_t now = std::time(nullptr);
  char buffer[64] = {};
  const std::tm* localTime = std::localtime(&now);
  if (!localTime) {
    return "unknown";
  }
  std::strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", localTime);
  return buffer;
}
void writeDirectoryDiagnostics(std::ostream& out, const DirectoryDiagnostics& d) {
  out << "------------------------------------------------------------\n"
      << d.name << "\n"
      << "------------------------------------------------------------\n\n";
  out << "MC collisions:\n"
      << "  total:                                  " << d.mcCollisionsTotal << "\n"
      << "  interesting:                            " << d.mcCollisionsInteresting << "\n"
      << "  non-interesting / MB:                   " << d.mcCollisionsNonInteresting << "\n\n";
  out << "Reconstructed collisions:\n"
      << "  total:                                  " << d.recoCollisionsTotal << "\n"
      << "  associated with interesting MC events:  " << d.recoCollisionsInteresting << "\n\n";
  out << "MC particles:\n"
      << "  initial:                                " << d.particlesInitial << "\n"
      << "  particles in interesting MC events:     " << d.particlesInterestingEvents << "\n"
      << "  particles in minimum-bias MC events:    " << d.particlesMinimumBiasEvents << "\n"
      << std::fixed << std::setprecision(4)
      << "  interesting / MB particle ratio:        "
      << (d.particlesMinimumBiasEvents > 0
              ? static_cast<double>(d.particlesInterestingEvents) /
                  static_cast<double>(d.particlesMinimumBiasEvents)
              : 0.0)
      << "\n"
      << "  interesting-event seeds:                " << d.particlesInterestingSeeds << "\n"
      << "  cross-event MB particles added:          " << d.particlesCrossEventAdded << "\n"
      << "  descendants added:                       " << d.particlesDirectDaughtersAdded << "\n"
      << "  mother-ancestry particles added:         " << d.particlesMotherAncestryAdded << "\n"
      << "  retained:                               " << d.particlesRetained << "\n"
      << "  removed:                                " << d.particlesRemoved << "\n"
      << std::fixed << std::setprecision(2)
      << "  retained fraction:                      "
      << fractionPercent(d.particlesRetained, d.particlesInitial) << " %\n"
      << "  removed fraction:                       "
      << fractionPercent(d.particlesRemoved, d.particlesInitial) << " %\n\n";
  const Long64_t interestingParticles = d.particlesInterestingSeeds;
  const Long64_t mbParticles = d.particlesInitial - d.particlesInterestingSeeds;
  out << std::fixed << std::setprecision(2)
      << "Average MC-particle multiplicity:\n"
      << "  particles / interesting MC collision:   "
      << (d.mcCollisionsInteresting > 0
            ? static_cast<double>(interestingParticles) /
                static_cast<double>(d.mcCollisionsInteresting)
            : 0.0)
      << "\n"
      << "  particles / non-interesting MC collision: "
      << (d.mcCollisionsNonInteresting > 0
            ? static_cast<double>(mbParticles) /
                static_cast<double>(d.mcCollisionsNonInteresting)
            : 0.0)
      << "\n\n";
  out << "Cross-event associations (interesting reco -> non-interesting MC):\n"
      << "  central-barrel track labels:             " << d.tracks.crossEventAssociations << "\n"
      << "    unique MC particles newly added:       " << d.tracks.uniqueParticlesAdded << "\n"
      << "  MFT track labels:                        " << d.mft.crossEventAssociations << "\n"
      << "    unique MC particles newly added:       " << d.mft.uniqueParticlesAdded << "\n"
      << "  forward track labels:                    " << d.fwd.crossEventAssociations << "\n"
      << "    unique MC particles newly added:       " << d.fwd.uniqueParticlesAdded << "\n\n";
  out << "Label remapping:\n"
      << "  O2mctracklabel rows:                      " << d.tracks.rows << "\n"
      << "    newly invalidated:                     " << d.tracks.invalidated << "\n"
      << "  O2mcmfttracklabel rows:                   " << d.mft.rows << "\n"
      << "    newly invalidated:                     " << d.mft.invalidated << "\n"
      << "  O2mcfwdtracklabel rows:                   " << d.fwd.rows << "\n"
      << "    newly invalidated:                     " << d.fwd.invalidated << "\n"
      << "  O2mccalolabel_001 rows:                   " << d.caloRows << "\n"
      << "    newly invalidated references:          " << d.caloInvalidated << "\n\n";
  out << "Genealogy:\n"
      << "  empty daughter slices cleared:           "
      << d.emptyDaughterSlicesCleared << "\n\n";
}
void writeGlobalDiagnostics(std::ostream& out,
                            const GlobalDiagnostics& g,
                            Long64_t inputSizeBytes,
                            Long64_t outputSizeBytes) {
  out << "============================================================\n"
      << "GLOBAL SUMMARY\n"
      << "============================================================\n\n";
  out << "Directories:\n"
      << "  successfully processed:                  " << g.directoriesProcessed << "\n"
      << "  failed:                                  " << g.directoriesFailed << "\n\n";
  out << "MC collisions:\n"
      << "  total:                                   " << g.mcCollisionsTotal << "\n"
      << "  interesting:                             " << g.mcCollisionsInteresting << "\n"
      << "  non-interesting / MB:                    " << g.mcCollisionsNonInteresting << "\n\n";
  out << "Reconstructed collisions:\n"
      << "  total:                                   " << g.recoCollisionsTotal << "\n"
      << "  associated with interesting MC events:   " << g.recoCollisionsInteresting << "\n\n";
  out << "MC particles:\n"
      << "  initial:                                 " << g.particlesInitial << "\n"
      << "  particles in interesting MC events:     " << g.particlesInterestingEvents << "\n"
      << "  particles in minimum-bias MC events:    " << g.particlesMinimumBiasEvents << "\n"
      << std::fixed << std::setprecision(4)
      << "  interesting / MB particle ratio:        "
      << (g.particlesMinimumBiasEvents > 0
              ? static_cast<double>(g.particlesInterestingEvents) /
                  static_cast<double>(g.particlesMinimumBiasEvents)
              : 0.0)
      << "\n"
      << std::fixed << std::setprecision(2)
      << "  avg particles / interesting MC event:   "
      << (g.mcCollisionsInteresting > 0
              ? static_cast<double>(g.particlesInterestingEvents) / static_cast<double>(g.mcCollisionsInteresting)
              : 0.0)
      << "\n"
      << "  avg particles / minimum-bias MC event:  "
      << (g.mcCollisionsNonInteresting > 0
              ? static_cast<double>(g.particlesMinimumBiasEvents) / static_cast<double>(g.mcCollisionsNonInteresting)
              : 0.0)
      << "\n"
      << "  interesting-event seeds:                 " << g.particlesInterestingSeeds << "\n"
      << "  cross-event MB particles added:           " << g.particlesCrossEventAdded << "\n"
      << "  descendants added:                        " << g.particlesDirectDaughtersAdded << "\n"
      << "  mother-ancestry particles added:          " << g.particlesMotherAncestryAdded << "\n"
      << "  retained:                                " << g.particlesRetained << "\n"
      << "  removed:                                 " << g.particlesRemoved << "\n"
      << std::fixed << std::setprecision(2)
      << "  retained fraction:                       "
      << fractionPercent(g.particlesRetained, g.particlesInitial) << " %\n"
      << "  removed fraction:                        "
      << fractionPercent(g.particlesRemoved, g.particlesInitial) << " %\n\n";
  const Long64_t rescuedMBParticles =
    g.particlesCrossEventAdded + g.particlesDirectDaughtersAdded + g.particlesMotherAncestryAdded;
  out << "MB rescue contribution:\n"
      << "  rescued MB particles:                    " << rescuedMBParticles << "\n"
      << "  fraction of retained MC particles:       "
      << fractionPercent(rescuedMBParticles, g.particlesRetained) << " %\n\n";
  out << "Cross-event associations:\n"
      << "  central barrel:                          " << g.tracks.crossEventAssociations << "\n"
      << "  MFT:                                     " << g.mft.crossEventAssociations << "\n"
      << "  forward:                                 " << g.fwd.crossEventAssociations << "\n\n";
  out << "Label remapping:\n"
      << "  track labels newly invalidated:          " << g.tracks.invalidated << "\n"
      << "  MFT labels newly invalidated:            " << g.mft.invalidated << "\n"
      << "  forward labels newly invalidated:        " << g.fwd.invalidated << "\n"
      << "  calorimeter references invalidated:      " << g.caloInvalidated << "\n\n";
  out << "Genealogy:\n"
      << "  empty daughter slices cleared:           "
      << g.emptyDaughterSlicesCleared << "\n\n";
  if (inputSizeBytes >= 0 && outputSizeBytes >= 0) {
    const double inputMB = static_cast<double>(inputSizeBytes) / (1024.0 * 1024.0);
    const double outputMB = static_cast<double>(outputSizeBytes) / (1024.0 * 1024.0);
    const double reduction =
      inputSizeBytes > 0
        ? 100.0 * (1.0 - static_cast<double>(outputSizeBytes) /
                           static_cast<double>(inputSizeBytes))
        : 0.0;
    const double compression =
      outputSizeBytes > 0
        ? static_cast<double>(inputSizeBytes) /
            static_cast<double>(outputSizeBytes)
        : 0.0;
    out << std::fixed << std::setprecision(2)
        << "File size:\n"
        << "  input:                                   " << inputMB << " MB\n"
        << "  output:                                  " << outputMB << " MB\n"
        << "  storage reduction:                       " << reduction << " %\n"
        << "  compression factor:                      " << compression << "x\n\n";
  }
}
struct StoredMCParticle {
  int mcCollisionId = -1;
  int pdgCode = 0;
  int statusCode = 0;
  UChar_t flags = 0;
  std::vector<int> mothers;
  std::array<int, 2> daughters = {-1, -1};
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
int getSubGeneratorIdFromGeneratorsID(Short_t generatorsID) {
  return o2::mcgenid::getSubGeneratorId(generatorsID);
}
bool isInterestingSubGenerator(int subGeneratorId, int minimumBiasSubGeneratorId) {
  return subGeneratorId != minimumBiasSubGeneratorId;
}
int remapMCParticleId(int oldId, const std::vector<int>& oldToNew) {
  if (oldId < 0 || oldId >= static_cast<int>(oldToNew.size())) {
    return -1;
  }
  return oldToNew[oldId];
}
bool isRewrittenTree(const std::string& treeName) {
  static const std::unordered_set<std::string> rewrittenTrees = {
    "O2mcparticle_001",
    "O2mctracklabel",
    "O2mcmfttracklabel",
    "O2mcfwdtracklabel",
    "O2mccalolabel_001"};
  return rewrittenTrees.count(treeName) != 0;
}
TTree* findTree(TDirectory* directory, std::initializer_list<const char*> candidates) {
  for (const char* name : candidates) {
    if (auto* tree = dynamic_cast<TTree*>(directory->Get(name))) {
      return tree;
    }
  }
  return nullptr;
}
TTree* findMCCollisionTree(TDirectory* directory) {
  return findTree(directory,{"O2mccollision_001", "O2mccollision", "O2mccollision_000"});
}
TTree* findMCCollisionLabelTree(TDirectory* directory) {
  return findTree(directory,{"O2mccollisionlabel", "O2mccollisionlabel_001", "O2mccollisionlabel_000"});
}
TTree* findCollisionTree(TDirectory* directory) {
  return findTree(directory,{"O2collision_001", "O2collision", "O2collision_000"});
}
TTree* findTrackTreeForLabel(TDirectory* directory, const char* labelTreeName, Long64_t expectedEntries) {
  TTree* tree = nullptr;
  const std::string labelName(labelTreeName);
  if (labelName == "O2mctracklabel") {
    tree = findTree(directory, {"O2track_iu", "O2track", "O2track_001", "O2track_000"});
  } else if (labelName == "O2mcmfttracklabel") {
    tree = findTree(directory, {"O2mfttrack_001", "O2mfttrack", "O2mfttrack_000"});
  } else if (labelName == "O2mcfwdtracklabel") {
    tree = findTree(directory, {"O2fwdtrack_001", "O2fwdtrack", "O2fwdtrack_000"});
  }
  if (!tree) {
    return nullptr;
  }
  if (tree->GetEntries() != expectedEntries) {
    std::cerr << "Warning: " << labelTreeName << " has " << expectedEntries
              << " rows, but candidate reconstructed track table " << tree->GetName()
              << " has " << tree->GetEntries()
              << " rows. Cross-event seeding from this table will be skipped.\n";
    return nullptr;
  }
  if (!tree->GetBranch("fIndexCollisions")) {
    std::cerr << "Warning: " << tree->GetName()
              << " has no fIndexCollisions branch. Cross-event seeding from "
              << labelTreeName << " will be skipped.\n";
    return nullptr;
  }
  return tree;
}
bool buildMCCollisionSubGeneratorMap(TDirectory* inputDirectory, std::vector<int>& subGeneratorIdByCollision) {
  auto* mcCollisionTree = findMCCollisionTree(inputDirectory);
  if (!mcCollisionTree) {
    std::cerr << "Missing MC-collision table\n";
    return false;
  }
  if (!mcCollisionTree->GetBranch("fGeneratorsID")) {
    std::cerr << mcCollisionTree->GetName()
              << ": missing required branch fGeneratorsID\n";
    return false;
  }
  Short_t generatorsID = 0;
  mcCollisionTree->SetBranchAddress("fGeneratorsID", &generatorsID);
  const Long64_t numberOfCollisions = mcCollisionTree->GetEntries();
  subGeneratorIdByCollision.resize(numberOfCollisions, -1);
  std::unordered_map<int, Long64_t> collisionCountsBySubGeneratorId;
  for (Long64_t collisionId = 0; collisionId < numberOfCollisions; ++collisionId) {
    mcCollisionTree->GetEntry(collisionId);
    const int subGeneratorId = getSubGeneratorIdFromGeneratorsID(generatorsID);
    subGeneratorIdByCollision[collisionId] = subGeneratorId;
    ++collisionCountsBySubGeneratorId[subGeneratorId];
  }
  std::cout << mcCollisionTree->GetName() << ": decoded sub-generator-ID population:\n";
  for (const auto& entry : collisionCountsBySubGeneratorId) {
    std::cout << "  sub-generator ID " << entry.first << ": " << entry.second << " MC collisions\n";
  }
  return true;
}
bool buildRecoCollisionInterestingMap(TDirectory* inputDirectory,
                                        const std::vector<int>& subGeneratorIdByCollision,
                                        int minimumBiasSubGeneratorId,
                                        std::vector<char>& isInterestingRecoCollision,
                                        DirectoryDiagnostics& diagnostics) {
  auto* collisionTree = findCollisionTree(inputDirectory);
  auto* mcCollisionLabelTree = findMCCollisionLabelTree(inputDirectory);
  if (!collisionTree) {
    std::cerr << "Missing reconstructed collision table; cannot identify "
              << "interesting reconstructed events\n";
    return false;
  }
  if (!mcCollisionLabelTree) {
    std::cerr << "Missing O2mccollisionlabel table; cannot identify "
              << "interesting reconstructed events\n";
    return false;
  }
  if (!mcCollisionLabelTree->GetBranch("fIndexMcCollisions")) {
    std::cerr << mcCollisionLabelTree->GetName()
              << ": missing fIndexMcCollisions\n";
    return false;
  }
  const Long64_t numberOfRecoCollisions = collisionTree->GetEntries();
  if (mcCollisionLabelTree->GetEntries() != numberOfRecoCollisions) {
    std::cerr << "Mismatch: " << collisionTree->GetName() << " has "
              << numberOfRecoCollisions << " rows while "
              << mcCollisionLabelTree->GetName() << " has "
              << mcCollisionLabelTree->GetEntries() << " rows\n";
    return false;
  }
  int mcCollisionId = -1;
  mcCollisionLabelTree->SetBranchAddress("fIndexMcCollisions", &mcCollisionId);
  isInterestingRecoCollision.assign(numberOfRecoCollisions, 0);
  Long64_t interestingRecoCollisions = 0;
  Long64_t invalidMcCollisionLabels = 0;
  for (Long64_t recoCollisionId = 0;
       recoCollisionId < numberOfRecoCollisions;
       ++recoCollisionId) {
    mcCollisionLabelTree->GetEntry(recoCollisionId);
    if (mcCollisionId < 0 ||
        mcCollisionId >= static_cast<int>(subGeneratorIdByCollision.size())) {
      if (mcCollisionId >= 0) {
        ++invalidMcCollisionLabels;
      }
      continue;
    }
    if (isInterestingSubGenerator(subGeneratorIdByCollision[mcCollisionId], minimumBiasSubGeneratorId)) {
      isInterestingRecoCollision[recoCollisionId] = 1;
      ++interestingRecoCollisions;
    }
  }
  diagnostics.recoCollisionsTotal = numberOfRecoCollisions;
  diagnostics.recoCollisionsInteresting = interestingRecoCollisions;
  std::cout << "Reco collisions associated with non-MB MC events: " << interestingRecoCollisions
            << " / " << numberOfRecoCollisions << "\n";
  if (invalidMcCollisionLabels > 0) {
    std::cerr << "Warning: " << invalidMcCollisionLabels
              << " reconstructed collisions have out-of-range MC-collision labels\n";
  }
  return true;
}
void copyUnchangedObjects(TDirectory* inputDirectory, TDirectory* outputDirectory) {
  TIter nextKey(inputDirectory->GetListOfKeys());
  TKey* key = nullptr;
  while ((key = static_cast<TKey*>(nextKey()))) {
    if (key->GetCycle() != inputDirectory->GetKey(key->GetName())->GetCycle()) {
      continue;
    }
    TObject* object = key->ReadObj();
    const std::string objectName = object->GetName();
    if (object->InheritsFrom(TDirectory::Class())) {
      outputDirectory->cd();
      auto* newDirectory = outputDirectory->mkdir(objectName.c_str());
      copyUnchangedObjects(static_cast<TDirectory*>(object), newDirectory);
      delete object;
      continue;
    }
    if (object->InheritsFrom(TTree::Class())) {
      if (isRewrittenTree(objectName)) {
        delete object;
        continue;
      }
      auto* inputTree = static_cast<TTree*>(object);
      outputDirectory->cd();
      auto* outputTree = inputTree->CloneTree(-1, "fast");
      outputTree->Write(objectName.c_str(), TObject::kOverwrite);
      delete object;
      continue;
    }
    outputDirectory->cd();
    object->Write(objectName.c_str(), TObject::kOverwrite);
    delete object;
  }
}
void markCrossEventTrackReferences(TDirectory* inputDirectory,
                                  const char* labelTreeName,
                                  const std::vector<char>& isInterestingRecoCollision,
                                  const std::vector<int>& particleMcCollisionId,
                                  const std::vector<int>& subGeneratorIdByCollision,
                                  int minimumBiasSubGeneratorId,
                                  std::vector<char>& keepParticle,
                                  std::vector<int>& motherWorkList,
                                  std::vector<int>& crossEventSeeds,
                                  LabelDiagnostics& diagnostics) {
  auto* labelTree = dynamic_cast<TTree*>(inputDirectory->Get(labelTreeName));
  if (!labelTree) {
    return;
  }
  if (!labelTree->GetBranch("fIndexMcParticles")) {
    std::cerr << labelTreeName
              << ": missing fIndexMcParticles; cross-event seeding skipped\n";
    return;
  }
  auto* trackTree = findTrackTreeForLabel(inputDirectory,
                                          labelTreeName,
                                          labelTree->GetEntries());
  if (!trackTree) {
    return;
  }
  int mcParticleId = -1;
  int recoCollisionId = -1;
  labelTree->SetBranchAddress("fIndexMcParticles", &mcParticleId);
  trackTree->SetBranchAddress("fIndexCollisions", &recoCollisionId);
  Long64_t crossEventMatches = 0;
  Long64_t newlyMarked = 0;
  Long64_t invalidParticleReferences = 0;
  Long64_t invalidRecoCollisionReferences = 0;
  const Long64_t numberOfRows = labelTree->GetEntries();
  for (Long64_t row = 0; row < numberOfRows; ++row) {
    labelTree->GetEntry(row);
    trackTree->GetEntry(row);
    if (mcParticleId < 0) {
      continue;
    }
    if (mcParticleId >= static_cast<int>(particleMcCollisionId.size())) {
      ++invalidParticleReferences;
      continue;
    }
    if (recoCollisionId < 0 ||
        recoCollisionId >= static_cast<int>(isInterestingRecoCollision.size())) {
      if (recoCollisionId >= 0) {
        ++invalidRecoCollisionReferences;
      }
      continue;
    }
    // Only tracks reconstructed in an interesting event may rescue an MB MC
    // particle. Normal MB-reco -> MB-MC labels do not seed the keep mask.
    if (!isInterestingRecoCollision[recoCollisionId]) {
      continue;
    }
    const int mcCollisionId = particleMcCollisionId[mcParticleId];
    if (mcCollisionId < 0 ||
        mcCollisionId >= static_cast<int>(subGeneratorIdByCollision.size())) {
      continue;
    }
    // If the MC particle already belongs to the interesting event, it is already
    // kept by the primary seed rule. We only count/mark genuine cross-event cases.
    if (isInterestingSubGenerator(subGeneratorIdByCollision[mcCollisionId], minimumBiasSubGeneratorId)) {
      continue;
    }
    ++crossEventMatches;
    // Record every unique genuine cross-event particle. This separate seed list is
    // used later to keep ONLY its direct daughters.
    if (std::find(crossEventSeeds.begin(), crossEventSeeds.end(), mcParticleId) ==
        crossEventSeeds.end()) {
      crossEventSeeds.push_back(mcParticleId);
    }
    if (!keepParticle[mcParticleId]) {
      keepParticle[mcParticleId] = 1;
      motherWorkList.push_back(mcParticleId);
      ++newlyMarked;
    }
  }
  diagnostics.crossEventAssociations = crossEventMatches;
  diagnostics.uniqueParticlesAdded = newlyMarked;
  std::cout << labelTreeName << ": found " << crossEventMatches
            << " interesting-reco -> non-interesting-MC associations; added "
            << newlyMarked << " MC particles to the keep set\n";
  if (invalidParticleReferences > 0) {
    std::cerr << "Warning: " << labelTreeName << " contains "
              << invalidParticleReferences
              << " out-of-range MC-particle references\n";
  }
  if (invalidRecoCollisionReferences > 0) {
    std::cerr << "Warning: " << trackTree->GetName() << " contains "
              << invalidRecoCollisionReferences
              << " out-of-range reconstructed-collision references\n";
  }
}
bool rewriteMCParticles(TDirectory* inputDirectory,
                         TDirectory* outputDirectory,
                         const std::vector<int>& subGeneratorIdByCollision,
                         const std::vector<char>& isInterestingRecoCollision,
                         int minimumBiasSubGeneratorId,
                         std::vector<int>& oldToNew,
                         DirectoryDiagnostics& diagnostics) {
  auto* inputTree = dynamic_cast<TTree*>(inputDirectory->Get("O2mcparticle_001"));
  if (!inputTree) {
    std::cerr << "Missing O2mcparticle_001\n";
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
  inputTree->SetBranchAddress("fIndexMcCollisions", &mcCollisionId);
  inputTree->SetBranchAddress("fPdgCode", &pdgCode);
  inputTree->SetBranchAddress("fStatusCode", &statusCode);
  inputTree->SetBranchAddress("fFlags", &flags);
  inputTree->SetBranchAddress("fIndexArray_Mothers_size", &mothersSize);
  inputTree->SetBranchAddress("fIndexArray_Mothers", mothers);
  inputTree->SetBranchAddress("fIndexSlice_Daughters", daughtersSlice);
  inputTree->SetBranchAddress("fWeight", &weight);
  inputTree->SetBranchAddress("fPx", &px);
  inputTree->SetBranchAddress("fPy", &py);
  inputTree->SetBranchAddress("fPz", &pz);
  inputTree->SetBranchAddress("fE", &e);
  inputTree->SetBranchAddress("fVx", &vx);
  inputTree->SetBranchAddress("fVy", &vy);
  inputTree->SetBranchAddress("fVz", &vz);
  inputTree->SetBranchAddress("fVt", &vt);
  const Long64_t numberOfParticles = inputTree->GetEntries();
  diagnostics.particlesInitial = numberOfParticles;
  oldToNew.assign(numberOfParticles, -1);
  std::vector<int> particleMcCollisionId(numberOfParticles, -1);
  std::vector<std::vector<int>> originalMothers(numberOfParticles);
  std::vector<std::array<int, 2>> originalDaughters(numberOfParticles, {-1, -1});
  std::vector<char> keepParticle(numberOfParticles, 0);
  std::vector<int> motherWorkList;
  std::vector<int> crossEventSeeds;
  motherWorkList.reserve(numberOfParticles);
  crossEventSeeds.reserve(1024);
  Long64_t particlesFromInterestingEvents = 0;
  Long64_t particlesFromMinimumBiasEvents = 0;
  Long64_t invalidCollisionReferences = 0;
  Long64_t invalidMotherReferences = 0;
  Long64_t invalidDaughterSlices = 0;
  const int maxMothersSize = static_cast<int>(inputTree->GetMaximum("fIndexArray_Mothers_size"));
  if (maxMothersSize > kMaxMothers) {
    std::cerr << "Error: maximum number of mothers (" << maxMothersSize
              << ") exceeds buffer size (" << kMaxMothers << ")\n";
    return false;
  }
  // First pass: store genealogy and seed with ALL particles from interesting MC events.
  for (Long64_t oldParticleId = 0; oldParticleId < numberOfParticles; ++oldParticleId) {
    inputTree->GetEntry(oldParticleId);
    particleMcCollisionId[oldParticleId] = mcCollisionId;
    const int safeMothersSize = std::min(mothersSize, kMaxMothers);
    if (mothersSize > kMaxMothers) {
      std::cerr << "Warning: particle " << oldParticleId << " has " << mothersSize
                << " mothers; only the first " << kMaxMothers << " are read\n";
    }
    for (int motherIndex = 0; motherIndex < safeMothersSize; ++motherIndex) {
      const int motherId = mothers[motherIndex];
      if (motherId < 0) {
        continue;
      }
      if (motherId >= numberOfParticles) {
        ++invalidMotherReferences;
        continue;
      }
      originalMothers[oldParticleId].push_back(motherId);
    }
    const int firstDaughter = daughtersSlice[0];
    const int lastDaughter = daughtersSlice[1];
    if (firstDaughter >= 0 || lastDaughter >= 0) {
      if (firstDaughter >= 0 &&
          lastDaughter >= firstDaughter &&
          lastDaughter < numberOfParticles) {
        originalDaughters[oldParticleId] = {firstDaughter, lastDaughter};
      } else {
        ++invalidDaughterSlices;
      }
    }
    if (mcCollisionId < 0 ||
        mcCollisionId >= static_cast<int>(subGeneratorIdByCollision.size())) {
      ++invalidCollisionReferences;
      continue;
    }
    if (isInterestingSubGenerator(subGeneratorIdByCollision[mcCollisionId], minimumBiasSubGeneratorId)) {
      keepParticle[oldParticleId] = 1;
      ++particlesFromInterestingEvents;
    } else {
      ++particlesFromMinimumBiasEvents;
    }
  }
  diagnostics.particlesInterestingEvents = particlesFromInterestingEvents;
  diagnostics.particlesMinimumBiasEvents = particlesFromMinimumBiasEvents;
  diagnostics.particlesInterestingSeeds = particlesFromInterestingEvents;
  std::cout << "O2mcparticle_001: initially marked "
            << particlesFromInterestingEvents
            << " particles from non-MB MC events\n";
  // Cross-event exceptions only:
  // interesting reco track -> MC particle from a non-interesting MC event.
  markCrossEventTrackReferences(inputDirectory,
                                "O2mctracklabel",
                                isInterestingRecoCollision,
                                particleMcCollisionId,
                                subGeneratorIdByCollision,
                                minimumBiasSubGeneratorId,
                                keepParticle,
                                motherWorkList,
                                crossEventSeeds,
                                diagnostics.tracks);
  markCrossEventTrackReferences(inputDirectory,
                                "O2mcmfttracklabel",
                                isInterestingRecoCollision,
                                particleMcCollisionId,
                                subGeneratorIdByCollision,
                                minimumBiasSubGeneratorId,
                                keepParticle,
                                motherWorkList,
                                crossEventSeeds,
                                diagnostics.mft);
  markCrossEventTrackReferences(inputDirectory,
                                "O2mcfwdtracklabel",
                                isInterestingRecoCollision,
                                particleMcCollisionId,
                                subGeneratorIdByCollision,
                                minimumBiasSubGeneratorId,
                                keepParticle,
                                motherWorkList,
                                crossEventSeeds,
                                diagnostics.fwd);
  diagnostics.particlesCrossEventAdded =
    diagnostics.tracks.uniqueParticlesAdded +
    diagnostics.mft.uniqueParticlesAdded +
    diagnostics.fwd.uniqueParticlesAdded;
  // Keep all descendants recursively for the genuine cross-event seed particles.
  // Every newly retained descendant is also added to the mother-ancestry work list
  // so that every retained particle still has valid mother references.
  Long64_t directDaughtersAdded = 0;
  std::vector<int> daughterWorkList = crossEventSeeds;
  std::vector<char> daughterQueued(numberOfParticles, 0);
  for (int crossEventParticleId : crossEventSeeds) {
    daughterQueued[crossEventParticleId] = 1;
  }
  std::size_t nextDaughterParticle = 0;
  while (nextDaughterParticle < daughterWorkList.size()) {
    const int particleId = daughterWorkList[nextDaughterParticle++];
    const int firstDaughter = originalDaughters[particleId][0];
    const int lastDaughter = originalDaughters[particleId][1];
    if (firstDaughter < 0 || lastDaughter < firstDaughter) {
      continue;
    }
    for (int daughterId = firstDaughter; daughterId <= lastDaughter; ++daughterId) {
      if (!keepParticle[daughterId]) {
        keepParticle[daughterId] = 1;
        motherWorkList.push_back(daughterId);
        ++directDaughtersAdded;
      }
      if (!daughterQueued[daughterId]) {
        daughterQueued[daughterId] = 1;
        daughterWorkList.push_back(daughterId);
      }
    }
  }
  diagnostics.particlesDirectDaughtersAdded = directDaughtersAdded;
  std::cout << "O2mcparticle_001: added " << directDaughtersAdded
            << " daughters through recursive descendant closure\n";
  // Recursive mother-ancestry closure. This is applied only to rescued cross-event
  // particles and all their recursively retained descendants. Particles from interesting
  // MC events are already kept together with their full event and do not seed this traversal.
  // Newly retained mothers do NOT cause their other daughters/siblings to be kept.
  std::size_t nextParticle = 0;
  Long64_t particlesAddedByMotherAncestry = 0;
  while (nextParticle < motherWorkList.size()) {
    const int particleId = motherWorkList[nextParticle++];
    for (int motherId : originalMothers[particleId]) {
      if (!keepParticle[motherId]) {
        keepParticle[motherId] = 1;
        motherWorkList.push_back(motherId);
        ++particlesAddedByMotherAncestry;
      }
    }
  }
  diagnostics.particlesMotherAncestryAdded = particlesAddedByMotherAncestry;
  std::cout << "O2mcparticle_001: added " << particlesAddedByMotherAncestry
            << " particles through recursive mother-ancestry closure\n";
  Long64_t keptCount = 0;
  for (Long64_t oldParticleId = 0; oldParticleId < numberOfParticles; ++oldParticleId) {
    if (keepParticle[oldParticleId]) {
      oldToNew[oldParticleId] = static_cast<int>(keptCount++);
    }
  }
  std::vector<StoredMCParticle> retainedParticles;
  retainedParticles.reserve(keptCount);
  Long64_t brokenMotherReferences = 0;
  Long64_t emptyDaughterSlices = 0;
  for (Long64_t oldParticleId = 0; oldParticleId < numberOfParticles; ++oldParticleId) {
    if (!keepParticle[oldParticleId]) {
      continue;
    }
    inputTree->GetEntry(oldParticleId);
    StoredMCParticle particle;
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
    for (int oldMotherId : originalMothers[oldParticleId]) {
      const int newMotherId = remapMCParticleId(oldMotherId, oldToNew);
      if (newMotherId >= 0) {
        particle.mothers.push_back(newMotherId);
      } else {
        ++brokenMotherReferences;
      }
    }
    const int oldFirstDaughter = originalDaughters[oldParticleId][0];
    const int oldLastDaughter = originalDaughters[oldParticleId][1];
    if (oldFirstDaughter >= 0 && oldLastDaughter >= oldFirstDaughter) {
      // A daughter slice represents a contiguous interval
      // [firstDaughter, lastDaughter]. Preserve the surviving daughters.
      int newFirstDaughter = -1;
      int previousNewDaughter = -1;
      for (int oldDaughterId = oldFirstDaughter;
           oldDaughterId <= oldLastDaughter;
           ++oldDaughterId) {
        const int newDaughterId = remapMCParticleId(oldDaughterId, oldToNew);
        if (newDaughterId < 0) {
          continue;
        }
        if (newFirstDaughter < 0) {
          newFirstDaughter = newDaughterId;
        }
        previousNewDaughter = newDaughterId;
      }
      if (newFirstDaughter >= 0) {
        particle.daughters = {newFirstDaughter, previousNewDaughter};
      } else {
        particle.daughters = {-1, -1};
        ++emptyDaughterSlices;
      }
    }
    retainedParticles.push_back(std::move(particle));
  }
  outputDirectory->cd();
  auto* outputTree = inputTree->CloneTree(0);
  for (const auto& particle : retainedParticles) {
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
    mothersSize = static_cast<int>(particle.mothers.size());
    for (int motherIndex = 0; motherIndex < mothersSize; ++motherIndex) {
      mothers[motherIndex] = particle.mothers[motherIndex];
    }
    daughtersSlice[0] = particle.daughters[0];
    daughtersSlice[1] = particle.daughters[1];
    outputTree->Fill();
  }
  outputTree->Write("O2mcparticle_001", TObject::kOverwrite);
  const double survivalFraction = numberOfParticles > 0
                                    ? static_cast<double>(keptCount) /
                                        static_cast<double>(numberOfParticles)
                                    : 0.;
  diagnostics.particlesRetained = keptCount;
  diagnostics.particlesRemoved = numberOfParticles - keptCount;
  diagnostics.emptyDaughterSlicesCleared = emptyDaughterSlices;
  std::cout << "O2mcparticle_001: retained " << keptCount << " / "
            << numberOfParticles << " particles; survival fraction = "
            << survivalFraction << "\n";
  if (invalidCollisionReferences > 0) {
    std::cerr << "Warning: " << invalidCollisionReferences
              << " MC particles had invalid MC-collision references\n";
  }
  if (invalidMotherReferences > 0) {
    std::cerr << "Warning: " << invalidMotherReferences
              << " out-of-range mother references were found\n";
  }
  if (invalidDaughterSlices > 0) {
    std::cerr << "Warning: " << invalidDaughterSlices
              << " invalid daughter slices were found\n";
  }
  if (brokenMotherReferences > 0) {
    std::cerr << "Warning: genealogy closure left " << brokenMotherReferences
              << " broken mother references. This should normally be zero.\n";
  }
  if (emptyDaughterSlices > 0) {
    std::cout << "O2mcparticle_001: cleared " << emptyDaughterSlices
              << " empty daughter slices after filtering\n";
  }
  return true;
}
void rewriteSingleMCLabelTable(TDirectory* inputDirectory,
                               TDirectory* outputDirectory,
                               const char* treeName,
                               const std::vector<int>& oldToNew,
                               LabelDiagnostics& diagnostics) {
  auto* inputTree = dynamic_cast<TTree*>(inputDirectory->Get(treeName));
  if (!inputTree) {
    return;
  }
  if (!inputTree->GetBranch("fIndexMcParticles")) {
    std::cerr << treeName << ": missing fIndexMcParticles; copying unchanged\n";
    outputDirectory->cd();
    auto* outputTree = inputTree->CloneTree(-1, "fast");
    outputTree->Write(treeName, TObject::kOverwrite);
    return;
  }
  int mcParticleId = -1;
  inputTree->SetBranchAddress("fIndexMcParticles", &mcParticleId);
  outputDirectory->cd();
  auto* outputTree = inputTree->CloneTree(0);
  const Long64_t numberOfLabels = inputTree->GetEntries();
  Long64_t newlyInvalidatedLabels = 0;
  for (Long64_t labelId = 0; labelId < numberOfLabels; ++labelId) {
    inputTree->GetEntry(labelId);
    const int oldMcParticleId = mcParticleId;
    const int remappedId = remapMCParticleId(oldMcParticleId, oldToNew);
    if (oldMcParticleId >= 0 && remappedId < 0) {
      ++newlyInvalidatedLabels;
    }
    mcParticleId = remappedId;
    outputTree->Fill();
  }
  outputTree->Write(treeName, TObject::kOverwrite);
  diagnostics.rows = numberOfLabels;
  diagnostics.invalidated = newlyInvalidatedLabels;
  std::cout << treeName << ": remapped " << numberOfLabels
            << " rows; newly invalidated " << newlyInvalidatedLabels
            << " labels\n";
}
void rewriteCaloMCLabels(TDirectory* inputDirectory,
                         TDirectory* outputDirectory,
                         const std::vector<int>& oldToNew,
                         DirectoryDiagnostics& diagnostics) {
  constexpr const char* treeName = "O2mccalolabel_001";
  auto* inputTree = dynamic_cast<TTree*>(inputDirectory->Get(treeName));
  if (!inputTree) {
    return;
  }
  auto* sizeBranch = inputTree->GetBranch("fIndexArrayMcParticles_size");
  auto* idsBranch = inputTree->GetBranch("fIndexArrayMcParticles");
  if (!sizeBranch || !idsBranch) {
    std::cerr << treeName
              << ": expected MC-particle array branches not found; copying unchanged\n";
    outputDirectory->cd();
    auto* outputTree = inputTree->CloneTree(-1, "fast");
    outputTree->Write(treeName, TObject::kOverwrite);
    return;
  }
  int idsSize = 0;
  int ids[kMaxCaloLabels] = {};
  inputTree->SetBranchAddress("fIndexArrayMcParticles_size", &idsSize);
  inputTree->SetBranchAddress("fIndexArrayMcParticles", ids);
  outputDirectory->cd();
  auto* outputTree = inputTree->CloneTree(0);
  const Long64_t numberOfRows = inputTree->GetEntries();
  const int maxCaloLabelsSize = static_cast<int>(inputTree->GetMaximum("fIndexArrayMcParticles_size"));
  if (maxCaloLabelsSize > kMaxCaloLabels) {
    std::cerr << "Error: maximum number of calorimeter labels (" << maxCaloLabelsSize
              << ") exceeds buffer size (" << kMaxCaloLabels << ")\n";
    return;
  }
  Long64_t newlyInvalidatedReferences = 0;
  for (Long64_t row = 0; row < numberOfRows; ++row) {
    inputTree->GetEntry(row);
    if (idsSize > kMaxCaloLabels) {
      std::cerr << "Error: " << treeName << " row " << row << " contains "
                << idsSize << " labels, exceeding buffer size "
                << kMaxCaloLabels << ". Aborting this table rewrite.\n";
      delete outputTree;
      return;
    }
    for (int labelIndex = 0; labelIndex < idsSize; ++labelIndex) {
      const int oldMcParticleId = ids[labelIndex];
      ids[labelIndex] = remapMCParticleId(oldMcParticleId, oldToNew);
      if (oldMcParticleId >= 0 && ids[labelIndex] < 0) {
        ++newlyInvalidatedReferences;
      }
    }
    outputTree->Fill();
  }
  outputTree->Write(treeName, TObject::kOverwrite);
  diagnostics.caloRows = numberOfRows;
  diagnostics.caloInvalidated = newlyInvalidatedReferences;
  std::cout << treeName
            << ": remapped all MC-particle references; newly invalidated "
            << newlyInvalidatedReferences << " references\n";
}
} // namespace
void filterAO2DGapTriggeredMCEvents(const char* inputFileName = "AO2D.root",
                                    const char* outputFileName = "AO2D_filter.root",
                                    int minimumBiasSubGeneratorId = 0,
                                    const char* logFileName = nullptr) {
  const std::string resolvedLogFileName = logFileName ? std::string(logFileName) : makeDefaultLogFileName(outputFileName);
  const Long64_t inputFileSizeBytes = getFileSizeBytes(inputFileName);
  std::ofstream logFile(resolvedLogFileName);
  if (!logFile) {
    std::cerr << "Cannot create diagnostic log file " << resolvedLogFileName << "\n";
    return;
  }
  logFile << "AO2D GAP-TRIGGER MC FILTER REPORT\n\n"
          << "Date: " << currentTimeString() << "\n"
          << "Input: " << inputFileName << "\n"
          << "Output: " << outputFileName << "\n"
          << "Minimum-bias sub-generator ID: " << minimumBiasSubGeneratorId << "\n\n"
          << "Filtering strategy:\n"
          << "  - keep all reconstructed AO2D tables\n"
          << "  - keep all MC particles from interesting events\n"
          << "  - rescue interesting-reco -> non-interesting-MC cross particles\n"
          << "  - keep all daughters recursively for rescued cross particles\n"
          << "  - keep all mothers recursively\n"
          << "  - remove all remaining MC particles and remap references\n\n";
  auto* inputFile = TFile::Open(inputFileName, "READ");
  if (!inputFile || inputFile->IsZombie()) {
    std::cerr << "Cannot open input file " << inputFileName << "\n";
    return;
  }
  auto* outputFile = TFile::Open(outputFileName, "RECREATE", "", 505);
  if (!outputFile || outputFile->IsZombie()) {
    std::cerr << "Cannot create output file " << outputFileName << "\n";
    inputFile->Close();
    return;
  }
  std::cout << "Filtering MC particles in gap-trigger production [V2]\n"
            << "  input file:              " << inputFileName << "\n"
            << "  output file:             " << outputFileName << "\n"
            << "  minimum-bias sub-gen ID: " << minimumBiasSubGeneratorId << "\n"
            << "  reconstructed tables:    kept unchanged\n"
            << "  extra MC seeds:          interesting-reco -> MB-MC only\n"
            << "  genealogy:               recursive mothers + recursive daughters of cross-event MB particles\n";
  TIter nextKey(inputFile->GetListOfKeys());
  TKey* key = nullptr;
  int processedDirectories = 0;
  int failedDirectories = 0;
  GlobalDiagnostics globalDiagnostics;
  while ((key = static_cast<TKey*>(nextKey()))) {
    if (key->GetCycle() != inputFile->GetKey(key->GetName())->GetCycle()) {
      continue;
    }
    TObject* object = key->ReadObj();
    const std::string objectName = object->GetName();
    if (std::string(key->GetName()) == "metaData") {
      outputFile->cd();
      object->Write("metaData", TObject::kSingleKey | TObject::kOverwrite);
      delete object;
      continue;
    }
    if (key->GetName() == std::string("parentFiles")) {
      outputFile->cd();
      object->Write("parentFiles", TObject::kSingleKey | TObject::kOverwrite);
      delete object;
      continue;
    }
    if (!object->InheritsFrom(TDirectory::Class())) {
      outputFile->cd();
      object->Write(objectName.c_str(), TObject::kOverwrite);
      delete object;
      continue;
    }
    auto* inputDirectory = static_cast<TDirectory*>(object);
    outputFile->cd();
    auto* outputDirectory = outputFile->mkdir(objectName.c_str());
    std::cout << "Processing directory " << objectName << "\n";
    DirectoryDiagnostics directoryDiagnostics;
    directoryDiagnostics.name = objectName;
    copyUnchangedObjects(inputDirectory, outputDirectory);
    std::vector<int> subGeneratorIdByCollision;
    std::vector<char> isInterestingRecoCollision;
    std::vector<int> oldToNew;
    const bool subGeneratorMapBuilt =
      buildMCCollisionSubGeneratorMap(inputDirectory, subGeneratorIdByCollision);
    if (subGeneratorMapBuilt) {
      directoryDiagnostics.mcCollisionsTotal =
        static_cast<Long64_t>(subGeneratorIdByCollision.size());
      for (int subGeneratorId : subGeneratorIdByCollision) {
        if (isInterestingSubGenerator(subGeneratorId, minimumBiasSubGeneratorId)) {
          ++directoryDiagnostics.mcCollisionsInteresting;
        } else {
          ++directoryDiagnostics.mcCollisionsNonInteresting;
        }
      }
    }
    const bool recoCollisionMapBuilt =
      subGeneratorMapBuilt &&
      buildRecoCollisionInterestingMap(inputDirectory,
                                       subGeneratorIdByCollision,
                                       minimumBiasSubGeneratorId,
                                       isInterestingRecoCollision,
                                      directoryDiagnostics);
    const bool particlesRewritten =
      recoCollisionMapBuilt &&
      rewriteMCParticles(inputDirectory,
                         outputDirectory,
                         subGeneratorIdByCollision,
                         isInterestingRecoCollision,
                         minimumBiasSubGeneratorId,
                         oldToNew,
                        directoryDiagnostics);
    if (!particlesRewritten) {
      std::cerr << "Failed to filter directory " << objectName << "\n";
      ++failedDirectories;
      ++globalDiagnostics.directoriesFailed;
      delete object;
      continue;
    }
    rewriteSingleMCLabelTable(inputDirectory,
                              outputDirectory,
                              "O2mctracklabel",
                              oldToNew,
                              directoryDiagnostics.tracks);
    rewriteSingleMCLabelTable(inputDirectory,
                              outputDirectory,
                              "O2mcmfttracklabel",
                              oldToNew,
                              directoryDiagnostics.mft);
    rewriteSingleMCLabelTable(inputDirectory,
                              outputDirectory,
                              "O2mcfwdtracklabel",
                              oldToNew,
                              directoryDiagnostics.fwd);
    rewriteCaloMCLabels(inputDirectory,
                        outputDirectory,
                        oldToNew,
                        directoryDiagnostics);
    writeDirectoryDiagnostics(logFile, directoryDiagnostics);
    accumulateDirectoryDiagnostics(globalDiagnostics, directoryDiagnostics);
    ++processedDirectories;
    delete object;
  }
  outputFile->Close();
  inputFile->Close();
  const Long64_t outputFileSizeBytes = getFileSizeBytes(outputFileName);
  globalDiagnostics.directoriesFailed = failedDirectories;
  writeGlobalDiagnostics(logFile,
                         globalDiagnostics,
                         inputFileSizeBytes,
                         outputFileSizeBytes);
  logFile.close();
  if (failedDirectories > 0) {
    std::cerr << "Completed with failures: " << failedDirectories
              << " directory/directories could not be filtered.\n";
  }
  std::cout << "Done. Successfully filtered " << processedDirectories
            << " directory/directories and wrote " << outputFileName << "\n"
            << "Diagnostic report written to " << resolvedLogFileName << "\n";
  const Long64_t rescuedMBParticles =
    globalDiagnostics.particlesCrossEventAdded +
    globalDiagnostics.particlesDirectDaughtersAdded +
    globalDiagnostics.particlesMotherAncestryAdded;
  std::cout << "\n============================================================\n"
            << "GLOBAL SUMMARY [V3]\n"
            << "============================================================\n"
            << "MC particles initial:             " << globalDiagnostics.particlesInitial << "\n"
            << "MC particles interesting events:  " << globalDiagnostics.particlesInterestingEvents << "\n"
            << "MC particles minimum-bias events: " << globalDiagnostics.particlesMinimumBiasEvents << "\n"
            << std::fixed << std::setprecision(4)
            << "Interesting / MB particle ratio:  "
            << (globalDiagnostics.particlesMinimumBiasEvents > 0
                  ? static_cast<double>(globalDiagnostics.particlesInterestingEvents) /
                      static_cast<double>(globalDiagnostics.particlesMinimumBiasEvents)
                  : 0.0)
            << "\n"
            << std::fixed << std::setprecision(2)
            << "Avg particles / interesting event: "
            << (globalDiagnostics.mcCollisionsInteresting > 0
                  ? static_cast<double>(globalDiagnostics.particlesInterestingEvents) /
                      static_cast<double>(globalDiagnostics.mcCollisionsInteresting)
                  : 0.0)
            << "\n"
            << "Avg particles / minimum-bias event: "
            << (globalDiagnostics.mcCollisionsNonInteresting > 0
                  ? static_cast<double>(globalDiagnostics.particlesMinimumBiasEvents) /
                      static_cast<double>(globalDiagnostics.mcCollisionsNonInteresting)
                  : 0.0)
            << "\n"
            << "MC particles retained:            " << globalDiagnostics.particlesRetained << "\n"
            << "MC particles removed:             " << globalDiagnostics.particlesRemoved << "\n"
            << std::fixed << std::setprecision(2)
            << "Retained fraction:       "
            << fractionPercent(globalDiagnostics.particlesRetained,
                               globalDiagnostics.particlesInitial)
            << " %\n"
            << "Removed fraction:        "
            << fractionPercent(globalDiagnostics.particlesRemoved,
                               globalDiagnostics.particlesInitial)
            << " %\n"
            << "Cross-event MB seeds:    "
            << globalDiagnostics.particlesCrossEventAdded << "\n"
            << "Descendants added:       "
            << globalDiagnostics.particlesDirectDaughtersAdded << "\n"
            << "Mother ancestry added:   "
            << globalDiagnostics.particlesMotherAncestryAdded << "\n"
            << "Rescued MB particles:    " << rescuedMBParticles << "\n"
            << "MB rescue fraction:      "
            << fractionPercent(rescuedMBParticles,
                               globalDiagnostics.particlesRetained)
            << " % of retained MC particles\n";
  if (inputFileSizeBytes >= 0 && outputFileSizeBytes >= 0) {
    const double inputMB =
      static_cast<double>(inputFileSizeBytes) / (1024.0 * 1024.0);
    const double outputMB =
      static_cast<double>(outputFileSizeBytes) / (1024.0 * 1024.0);
    const double reduction =
      inputFileSizeBytes > 0
        ? 100.0 * (1.0 - static_cast<double>(outputFileSizeBytes) /
                           static_cast<double>(inputFileSizeBytes))
        : 0.0;
    std::cout << "Input file size:         " << inputMB << " MB\n"
              << "Output file size:        " << outputMB << " MB\n"
              << "Storage reduction:       " << reduction << " %\n";
  }
}
//==============================================================================================================================
