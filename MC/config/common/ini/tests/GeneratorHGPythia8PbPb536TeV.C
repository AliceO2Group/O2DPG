int External()
{
  const int A = 208; // mass number of both nuclei
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
  std::vector<o2::MCTrack>* tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);
  o2::dataformats::MCEventHeader* header = nullptr;
  tree->SetBranchAddress("MCEventHeader.", &header);

  using Key = o2::dataformats::MCInfoKeys;
  const auto nEvents = tree->GetEntries();
  if (nEvents == 0) {
    std::cerr << "No events found\n";
    return 1;
  }
  for (Long64_t i = 0; i < nEvents; ++i) {
    tree->GetEntry(i);
    bool valid = false;
    const int nColl = header->getInfo<int>(Key::nColl, valid);
    if (!valid || nColl < 1 || nColl > A * A) {
      std::cerr << "Missing or invalid Ncoll in event " << i << "\n";
      return 1;
    }
    const int nPart = header->getInfo<int>(Key::nPart, valid);
    if (!valid || nPart < 2 || nPart > 2 * A) {
      std::cerr << "Missing or invalid Npart in event " << i << "\n";
      return 1;
    }
    // each NN collision is a PYTHIA pp event: two beam protons with half of sqrt(s_NN) each
    int nBeams = 0;
    for (const auto& track : *tracks) {
      if (o2::mcgenstatus::getHepMCStatusCode(track.getStatusCode()) == 4) {
        if (track.GetPdgCode() != 2212 || std::abs(track.GetEnergy() - 2680.) > 1e-3) {
          std::cerr << "Unexpected beam particle " << track.GetPdgCode() << " with energy " << track.GetEnergy() << " in event " << i << "\n";
          return 1;
        }
        nBeams++;
      }
    }
    if (nBeams != 2 * nColl) {
      std::cerr << "Found " << nBeams << " beam protons for " << nColl << " NN collisions in event " << i << "\n";
      return 1;
    }
  }
  return 0;
}
