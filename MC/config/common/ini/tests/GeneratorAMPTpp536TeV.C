int External()
{
  std::string path{"o2sim_Kine.root"};
  // Check that file exists, can be opened and has the correct tree
  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }
  auto tree = (TTree*)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }
  std::vector<o2::MCTrack>* tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);
  o2::dataformats::MCEventHeader* eventHeader = nullptr;
  tree->SetBranchAddress("MCEventHeader.", &eventHeader);

  // Check if there are 100 events, as simulated in the o2dpg-test
  auto nEvents = tree->GetEntries();
  if (nEvents != 100) {
    std::cerr << "Expected 100 events, got " << nEvents << "\n";
    return 1;
  }
  // Beam momentum per nucleon for Pb-Pb at sqrt(s_NN) = 5.36 TeV
  for (Long64_t i = 0; i < nEvents; ++i) {
    tree->GetEntry(i);
    if (tracks->empty()) {
      std::cerr << "Empty entry found at event " << i << "\n";
      return 1;
    }
  }
  return 0;
}
