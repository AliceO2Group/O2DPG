int External()
{
  std::string path{"o2sim_Kine.root"};

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

  std::vector<o2::MCTrack>* tracks = nullptr;
  tree->SetBranchAddress("MCTrack", &tracks);

  const auto nEvents = tree->GetEntries();

  for (Long64_t iEv = 0; iEv < nEvents; ++iEv) {
    tree->GetEntry(iEv);

    bool hasSigma = false;
    bool hasProton = false;

    for (const auto& track : *tracks) {
      const int pdg = track.GetPdgCode();
      const int absPdg = std::abs(pdg);

      if (absPdg == 3112 || absPdg == 3222) {
        hasSigma = true;
      }

      if (pdg == 2212) {
        hasProton = true;
      }

      if (hasSigma && hasProton) {
        std::cout << "Found event of interest at entry " << iEv << "\n";
        return 0;
      }
    }
  }

  std::cerr << "No Sigma-proton event of interest\n";
  return 1;
}