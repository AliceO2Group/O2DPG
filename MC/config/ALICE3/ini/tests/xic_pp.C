int External()
{
  std::string path{"o2sim_Kine.root"};
  int pdgToCheck = 4232;

  TFile file(path.c_str(), "read");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << std::endl;
    return 1;
  }

  int nInjectedParticles = 0;
  TTree* tree = (TTree*)file.Get("o2sim");
  
  if (!tree) {
    std::cerr << "Cannot find tree o2sim in file " << path << "\n";
    return 1;
  }

  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  int nEvents = tree->GetEntries();
  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    for (auto& track : *tracks) {
      auto pdgCode = track.GetPdgCode();
      if (pdgCode == pdgToCheck) {
        // not injecting anti-particle
        nInjectedParticles++;
      }
    }
  }

  if (nInjectedParticles < nEvents) {
    // Check that we are correctly injecting one
    // particle per event
    return 1;
  }

  return 0;
}




