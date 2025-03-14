int External()
{
  std::string path = "o2sim_Kine.root";
  int pdgToCheck = 3312;

  TFile file(path.c_str(), "read");
  if (file.IsZombie()) {
    std::err << "Cannot open ROOT file " << path << std::endl;
    return 1;
  }

  int nInjectedParticles = 0;
  TTree* tree = (TTree*)file.Get("o2sim");
  std::vector<o2::MCTrack>* tracks{};
  tree->SetBranchAdress("MCTrack", &tracks)

  int nEvents = tree->GetEntries();
  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    for (const auto& track : tracks) {
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