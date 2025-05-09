int External() {
  std::string path{"o2sim_Kine.root"};
  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }
  auto tree = (TTree *)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree 'o2sim' in file " << path << "\n";
    return 1;
  }
  // Get the MCTrack branch
  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);
  // Check if only pairs are contained in the simulation
  int nEvents = tree->GetEntries();
  int count_e = 0;
  int count_p = 0;
  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    for (auto &track : *tracks)
    {
      auto pdg = track.GetPdgCode();
      if (pdg == 11) {
        count_e++;
      } else if (pdg == -11) {
        count_p++;
      } else {
        std::cerr << "Found unexpected PDG code: " << pdg << "\n";
        return 1;
      }
    }
  }
  if (count_e < count_p) {
    std::cerr << "Less electrons than positrons: " << count_e << " vs " << count_p << "\n";
    return 1;
  }
  file.Close();

  return 0;
}