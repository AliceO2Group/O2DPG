int External()
{
  std::string path{"o2sim_Kine.root"};
  int numberOfInjectedSignalsPerEvent{1};
  std::vector<int> injectedPDGs = {
    3334,
    -3334,
    3312,
    -3312};

  auto nInjection = injectedPDGs.size();

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

  std::vector<int> nSignal;
  for (int i = 0; i < nInjection; i++) {
    nSignal.push_back(0);
  }

  auto nEvents = tree->GetEntries();
  for (int i = 0; i < nEvents; i++) {
    auto check = tree->GetEntry(i);
    for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack) {
      auto track = tracks->at(idxMCTrack);
      auto pdg = track.GetPdgCode();
      auto it = std::find(injectedPDGs.begin(), injectedPDGs.end(), pdg);
      int index = std::distance(injectedPDGs.begin(), it); // index of injected PDG
      if (it != injectedPDGs.end())                        // found
      {
        // count signal PDG
        nSignal[index]++;
      }
    }
  }
  std::cout << "--------------------------------\n";
  std::cout << "# Events: " << nEvents << "\n";
  for (int i = 0; i < nInjection; i++) {
    std::cout << "# Injected nuclei \n";
    std::cout << injectedPDGs[i] << ": " << nSignal[i] << "\n";
    if (nSignal[i] == 0) {
      std::cerr << "No generated: " << injectedPDGs[i] << "\n";
      return 1; // At least one of the injected particles should be generated
    }
  }
  return 0;
}
