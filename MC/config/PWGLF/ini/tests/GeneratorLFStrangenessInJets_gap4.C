#include "TFile.h"
#include "TTree.h"
#include <vector>
#include <iostream>
#include "SimulationDataFormat/MCTrack.h"

int Hybrid()
{
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

  std::cout << "Found " << tree->GetEntries() << " events." << std::endl;
  return 0;
}
