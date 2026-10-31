
#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "SimulationDataFormat/MCTrack.h"
#include "TFile.h"
#include "TTree.h"

#include <algorithm>
#include <iostream>
#include <string>
#include <vector>
#endif

int External()
{
  std::string path{"o2sim_Kine.root"};

  std::vector<int> injectedPDGs = {
    -1000010020 // anti-deuteron
  };

  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  auto* tree = (TTree*)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }

  std::vector<o2::MCTrack>* tracks = nullptr;
  tree->SetBranchAddress("MCTrack", &tracks);

  std::vector<int> nSignal(injectedPDGs.size(), 0);
  std::vector<int> nEventsWithSignal(injectedPDGs.size(), 0);

  const auto nEvents = tree->GetEntries();

  for (Long64_t i = 0; i < nEvents; ++i) {
    tree->GetEntry(i);

    std::vector<bool> found(injectedPDGs.size(), false);

    for (const auto& track : *tracks) {
      const int pdg = track.GetPdgCode();

      auto it = std::find(
          injectedPDGs.begin(),
          injectedPDGs.end(),
          pdg);

      if (it != injectedPDGs.end()) {
        const auto index = std::distance(injectedPDGs.begin(), it);
        ++nSignal[index];
        found[index] = true;
      }
    }

    for (size_t j = 0; j < injectedPDGs.size(); ++j) {
      if (found[j]) {
        ++nEventsWithSignal[j];
      }
    }
  }

  std::cout << "--------------------------------\n";
  std::cout << "# Events: " << nEvents << "\n";

  for (size_t i = 0; i < injectedPDGs.size(); ++i) {
    std::cout << "PDG: " << injectedPDGs[i] << "\n";
    std::cout << "# Generated particles: " << nSignal[i] << "\n";
    std::cout << "# Events containing particle: "
              << nEventsWithSignal[i] << "\n";

    if (nSignal[i] == 0) {
      std::cerr << "No generated particles with PDG "
                << injectedPDGs[i] << "\n";
      return 1;
    }
  }

  return 0;
}
