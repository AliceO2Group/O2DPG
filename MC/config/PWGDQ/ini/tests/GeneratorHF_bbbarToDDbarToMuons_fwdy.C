int External()
{
  int checkPdgDecay = 13;
  std::string path{"o2sim_Kine.root"};
  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }
  auto tree = (TTree*)file.Get("o2sim");
  std::vector<o2::MCTrack>* tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  int nLeptons{};
  int nLeptonsInAcceptance{};
  int nLeptonsToBeDone{};
  int nSignalPairs{};
  int nLeptonPairs{};
  int nLeptonPairsInAcceptance{};
  int nLeptonPairsToBeDone{};
  auto nEvents = tree->GetEntries();

  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    int nleptonseinacc = 0;
    int nleptonse = 0;
    int nleptonseToBeDone = 0;
    int nopenHeavy = 0;
    for (auto& track : *tracks) {
      auto pdg = track.GetPdgCode();
      auto y = track.GetRapidity();
      if (std::abs(pdg) == checkPdgDecay) {
        int igmother = track.getMotherTrackId();
        if (igmother > 0) {
          auto gmTrack = (*tracks)[igmother];
          int gmpdg = gmTrack.GetPdgCode();
          if ( int(std::abs(gmpdg)/100.) == 4 || int(std::abs(gmpdg)/1000.) == 4 || int(std::abs(gmpdg)/100.) == 5 || int(std::abs(gmpdg)/1000.) == 5 ) {
            nLeptons++;
            nleptonse++;
            if (-4.3 < y && y < -2.3) {
              nleptonseinacc++;
              nLeptonsInAcceptance++;
            }
            if (track.getToBeDone()) {
              nLeptonsToBeDone++;
              nleptonseToBeDone++;
            }
          }
        }    
      } else if (std::abs(pdg) == 411 || std::abs(pdg) == 421 || std::abs(pdg) == 431 || std::abs(pdg) == 4122 || std::abs(pdg) == 4132 || std::abs(pdg) == 4232 || std::abs(pdg) == 4332 || std::abs(pdg) == 511 || std::abs(pdg) == 521 || std::abs(pdg) == 531 || std::abs(pdg) == 541 || std::abs(pdg) == 5112 || std::abs(pdg) == 5122 || std::abs(pdg) == 5232 || std::abs(pdg) == 5132 || std::abs(pdg) == 5332) {
        nopenHeavy++;
      }
    }
    if (nopenHeavy > 1) nSignalPairs++;
    if (nleptonse > 1) nLeptonPairs++;
    if (nleptonseToBeDone > 1) nLeptonPairsToBeDone++;
    if (nleptonseinacc > 1) nLeptonPairsInAcceptance++;
  }
  std::cout << "#events: " << nEvents << "\n"
  << "#leptons in acceptance: " << nLeptonsInAcceptance << "\n"
  << "#lepton pairs in acceptance: " << nLeptonPairsInAcceptance << "\n"
  << "#leptons: " << nLeptons << "\n"
  << "#leptons to be done: " << nLeptonsToBeDone << "\n"
  << "#signal pairs: " << nSignalPairs << "\n"
  << "#lepton pairs: " << nLeptonPairs << "\n"
  << "#lepton pairs to be done: " << nLeptonPairsToBeDone << "\n";
  if (nLeptons == 0) {
    std::cerr << "Number of leptons should be greater than 1.\n";
    return 1;
  }
  if (nLeptonPairs < nSignalPairs) {
    std::cerr << "Number of lepton pairs should be at least equaled to the number of open charm hadron pairs\n";
    return 1;
  }
  if (nLeptonPairsInAcceptance < nEvents) {
    std::cerr << "Number of lepton pairs should be at least equaled to the number of events\n";
    return 1;
  }
  if (nLeptonPairs != nLeptonPairsToBeDone) {
    std::cerr << "The number of lepton pairs should be the same as the number of lepton pairs which should be transported.\n";
    return 1;
  }
  if (nLeptons != nLeptonsToBeDone) {
    std::cerr << "The number of leptons should be the same as the number of leptons which should be transported.\n";
    return 1;
  }

  return 0;
}
