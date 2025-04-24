int External() 
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
  auto nEvents = tree->GetEntries();
  int nInjected = 0;
  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    for (auto& track : *tracks) {
      auto pdgCode = std::fabs(track.GetPdgCode());
      if (pdgCode == 3312) {
        nInjected++;
      }
    }
  }

  // Check if we are above typical Angantyr numbers
  if (nInjected < 5 * nEvents) {
    std::cerr << "Too few particles injected\n";
    return 1;
  }

  return 0;
}