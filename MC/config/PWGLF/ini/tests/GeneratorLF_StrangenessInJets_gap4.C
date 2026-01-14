#include "TFile.h"
#include "TTree.h"
#include "TMath.h"
#include "fastjet/ClusterSequence.hh"
#include <vector>
#include <iostream>
#include "DataFormatsMC/MCTrack.h"

using namespace fastjet;

int External() {
  std::string path{"o2sim_Kine.root"};

  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  auto tree = (TTree *)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }

  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  // Jet parameters
  const double ptJetThreshold = 10.0;
  const double jetR = 0.4;
  const int gapSize = 4; // 4 events auto-accepted, 5th needs strange-in-jet

  // Xi and Omega PDG codes
  const std::vector<int> pdgXiOmega = {3312, -3312, 3334, -3334};

  Long64_t nEntries = tree->GetEntries();

  for (Long64_t iEntry = 0; iEntry < nEntries; ++iEntry) {
    tree->GetEntry(iEntry);
    if (!tracks || tracks->empty()) continue;

    bool acceptEvent = false;

    // Gap-trigger logic
    if (iEntry % (gapSize + 1) < gapSize) {
      // Accept event automatically
      acceptEvent = true;
      std::cout << "Gap-trigger accepted event " << iEntry << " (no Xi/Omega check)\n";
    } else {
      // Require Xi/Omega inside a jet
      std::vector<PseudoJet> fjParticles;
      std::vector<int> fjIndexMap;
      for (size_t i = 0; i < tracks->size(); ++i) {
        const auto &t = tracks->at(i);
        if (t.GetPdgCode() == 0) continue;
        if (std::abs(t.GetEta()) > 0.8) continue; // acceptance cut
        fjParticles.emplace_back(t.GetPx(), t.GetPy(), t.GetPz(), t.GetE());
        fjIndexMap.push_back(i);
      }

      if (!fjParticles.empty()) {
        JetDefinition jetDef(antikt_algorithm, jetR);
        ClusterSequence cs(fjParticles, jetDef);
        std::vector<PseudoJet> jets = sorted_by_pt(cs.inclusive_jets(ptJetThreshold));

        for (auto &jet : jets) {
          auto constituents = jet.constituents();
          for (auto &c : constituents) {
            int trackIndex = fjIndexMap[c.user_index()];
            int pdg = tracks->at(trackIndex).GetPdgCode();
            if (std::find(pdgXiOmega.begin(), pdgXiOmega.end(), pdg) != pdgXiOmega.end()) {
              acceptEvent = true;
              std::cout << "Accepted event " << iEntry
                        << ": Jet pt = " << jet.pt()
                        << ", eta = " << jet.eta()
                        << ", phi = " << jet.phi()
                        << ", contains PDG " << pdg << "\n";
              break;
            }
          }
          if (acceptEvent) break;
        }
      }
    }

    if (acceptEvent) {
      // Here you could break if you only want the first accepted event,
      // or continue to process all events following the gap-trigger pattern
    }
  }

  return 0;
}
