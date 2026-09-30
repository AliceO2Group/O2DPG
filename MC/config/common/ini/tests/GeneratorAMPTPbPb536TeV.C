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

  // Check if there are 2 events, as simulated in the o2dpg-test
  auto nEvents = tree->GetEntries();
  if (nEvents != 2) {
    std::cerr << "Expected 2 events, got " << nEvents << "\n";
    return 1;
  }
  // Beam momentum per nucleon for Pb-Pb at sqrt(s_NN) = 5.36 TeV
  const double beamMomentum = std::sqrt(2680. * 2680. - 0.938 * 0.938);
  for (Long64_t i = 0; i < nEvents; ++i) {
    tree->GetEntry(i);
    if (tracks->empty()) {
      std::cerr << "Empty entry found at event " << i << "\n";
      return 1;
    }
    // Check the heavy-ion information of the header
    bool isValid = false;
    auto nPart = eventHeader->getInfo<int>(o2::dataformats::MCInfoKeys::nPart, isValid);
    if (!isValid || nPart <= 0) {
      std::cerr << "Event " << i << " has no valid number of participants\n";
      return 1;
    }
    if (eventHeader->GetB() < 0. || eventHeader->GetB() > 20.) {
      std::cerr << "Event " << i << " has impact parameter " << eventHeader->GetB() << " outside the [0, 20] fm range\n";
      return 1;
    }
    // Spectator nucleons (pT = 0, beam momentum) must be kept for both beams.
    // AMPT writes momenta with 4 decimals, hence the tolerance
    int nSpectatorsA = 0, nSpectatorsC = 0;
    for (const auto& track : *tracks) {
      if (track.GetPdgCode() != 2212 && track.GetPdgCode() != 2112) {
        continue;
      }
      if (track.GetPt() == 0. && std::abs(std::abs(track.GetStartVertexMomentumZ()) - beamMomentum) < 1e-2) {
        (track.GetStartVertexMomentumZ() > 0 ? nSpectatorsA : nSpectatorsC)++;
      }
    }
    // The total number of nucleons in each nucleus must be conserved
    if (nSpectatorsA + nSpectatorsC + nPart > 2 * 208) {
      std::cerr << "Event " << i << " has more nucleons than the colliding nuclei\n";
      return 1;
    }
    if (nSpectatorsA == 0 || nSpectatorsC == 0) {
      std::cerr << "Event " << i << " has no spectator nucleons (A side: " << nSpectatorsA << ", C side: " << nSpectatorsC << ")\n";
      return 1;
    }
    std::cout << "Event " << i << ": " << tracks->size() << " tracks, b = " << eventHeader->GetB() << " fm, Npart = " << nPart
              << ", spectators A/C = " << nSpectatorsA << "/" << nSpectatorsC << "\n";
  }
  return 0;
}
