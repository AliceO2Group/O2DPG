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

  auto nEvents = tree->GetEntries();
  if (nEvents == 0) {
    std::cerr << "No event of interest\n";
    return 1;
  }
  return 0;
}
