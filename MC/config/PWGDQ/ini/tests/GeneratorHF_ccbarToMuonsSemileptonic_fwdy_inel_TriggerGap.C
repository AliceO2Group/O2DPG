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
            if (-4.3 < y && y < -2.2) {
              nleptonseinacc++;
              nLeptonsInAcceptance++;
            }
            if (track.getToBeDone()) {
              nLeptonsToBeDone++;
              nleptonseToBeDone++;
            }
          }
        }    
      } else if (std::abs(pdg) == 411 || std::abs(pdg) == 421 || std::abs(pdg) == 431 || std::abs(pdg) == 4122 || std::abs(pdg) == 4132 || std::abs(pdg) == 4232 || std::abs(pdg) == 4332) {
        nopenHeavy++;
      }
    }
    if (nopenHeavy > 1) nSignalPairs++;
    if (nleptonse > 1) nLeptonPairs++;
    if (nleptonseToBeDone > 1) nLeptonPairsToBeDone++;
    if (nleptonseinacc > 1) nLeptonPairsInAcceptance++;
  }
  std::cout << "#events: " << nEvents << "\n"
  << "#muons in acceptance: " << nLeptonsInAcceptance << "\n"
  << "#muon pairs in acceptance: " << nLeptonPairsInAcceptance << "\n"
  << "#muons: " << nLeptons << "\n"
  << "#muons to be done: " << nLeptonsToBeDone << "\n"
  << "#signal pairs: " << nSignalPairs << "\n"
  << "#muon pairs: " << nLeptonPairs << "\n"
  << "#muon pairs to be done: " << nLeptonPairsToBeDone << "\n";
  if (nLeptonPairs != nLeptonPairsToBeDone) {
    std::cerr << "The number of muon pairs should be the same as the number of muon pairs which should be transported.\n";
    return 1;
  }
  if (nLeptons != nLeptonsToBeDone) {
    std::cerr << "The number of muons should be the same as the number of muons which should be transported.\n";
    return 1;
  }

  return 0;
}
