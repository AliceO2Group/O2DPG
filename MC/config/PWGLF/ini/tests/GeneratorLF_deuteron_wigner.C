
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

  std::vector<o2::MCTrack>* tracks = nullptr;
  tree->SetBranchAddress("MCTrack", &tracks);

  Long64_t nEntries = tree->GetEntries();
  int nSelected = 0;

  for (Long64_t i = 0; i < nEntries; ++i) {
    tree->GetEntry(i);
    for (const auto& track : *tracks) {
      if (std::abs(track.GetPdgCode()) == 1000010020) { // Deuteron
        ++nSelected;
        break; // Found in this event
      }
    }
  }

  if (nSelected == 0) {
    std::cout << "No events with deuterons found.\n";
  } else {
    std::cout << "Found " << nSelected << " events with deuterons\n";
  }
  return 0;

}

