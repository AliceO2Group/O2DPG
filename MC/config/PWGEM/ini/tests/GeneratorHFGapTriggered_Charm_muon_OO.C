int External()
{
  int checkPdgDecay = 13;
  std::string path{"o2sim_Kine.root"};
  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  float ratioTrigger = 1./3.; // one event triggered out of 3
  auto tree = (TTree*)file.Get("o2sim");
  std::vector<o2::MCTrack>* tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  int nLeptonsInAcceptance{};
  int nLeptons{};
  int nAntileptons{};
  int nLeptonsToBeDone{};
  int nAntileptonsToBeDone{};
  int nSignalPairs{};
  int nLeptonPairs{};
  int nLeptonPairsToBeDone{};
  auto nEvents = tree->GetEntries();

  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    int nElectrons = 0;
    int nPositrons = 0;
    int nElectronsToBeDone = 0;
    int nPositronsToBeDone = 0;
    int nOpenCharmPos = 0;
    int nOpenCharmNeg = 0;
    int nPositronsElectronsInAcceptance = 0;
    for (auto& track : *tracks) {
      auto pdg = track.GetPdgCode();
      auto y = track.GetRapidity();
      if (pdg == checkPdgDecay) {
        int igmother = track.getMotherTrackId();
        if (igmother > 0) {
          auto gmTrack = (*tracks)[igmother];
          int gmpdg = gmTrack.GetPdgCode();
          if (int(std::abs(gmpdg)/100.) == 4 || int(std::abs(gmpdg)/1000.) == 4) {
            nLeptons++;
            nElectrons++;
            if (-1 < y && y < 1) nPositronsElectronsInAcceptance++;
            if (track.getToBeDone()) {
              nLeptonsToBeDone++;
              nElectronsToBeDone++;
            }
          }
        }    
      } else if (pdg == -checkPdgDecay) {
        int igmother = track.getMotherTrackId();
        if (igmother > 0) {
          auto gmTrack = (*tracks)[igmother];
          int gmpdg = gmTrack.GetPdgCode();
          if (int(TMath::Abs(gmpdg)/100.) == 4 || int(TMath::Abs(gmpdg)/1000.) == 4) {
            nAntileptons++;
            nPositrons++;
            if (-1 < y && y < 1) nPositronsElectronsInAcceptance++;
            if (track.getToBeDone()) {
              nAntileptonsToBeDone++;
              nPositronsToBeDone++;
            }
          }
        }
      } else if (pdg == 411 || pdg == 421 || pdg == 431 || pdg == 4122 || pdg == 4132 || pdg == 4232 || pdg == 4332) {
        nOpenCharmPos++;
      }  else if (pdg == -411 || pdg == -421 || pdg == -431 || pdg == -4122 || pdg == -4132 || pdg == -4232 || pdg == -4332) {
        nOpenCharmNeg++;
      }
    }
    if (nOpenCharmPos > 0 && nOpenCharmNeg > 0) {
      nSignalPairs++;
    }
    if (nPositronsElectronsInAcceptance > 1) {
      nLeptonsInAcceptance++;
    }
    if (nElectrons > 0 && nPositrons > 0) {
      nLeptonPairs++;
    }
    if (nElectronsToBeDone > 0 && nPositronsToBeDone > 0) nLeptonPairsToBeDone++;
  }
  std::cout << "#events: " << nEvents << "\n"
    << "#leptons: " << nLeptons << "\n"
    << "#antileptons: " << nAntileptons << "\n"
    << "#leptons to be done: " << nLeptonsToBeDone << "\n"
    << "#antileptons to be done: " << nAntileptonsToBeDone << "\n"
    << "#open-charm hadron pairs: " << nSignalPairs << "\n"
    << "#leptons in acceptance: " << nLeptonsInAcceptance << "\n"
    << "#Electron-positron pairs: " << nLeptonPairs << "\n"
    << "#Electron-positron pairs to be done: " << nLeptonPairsToBeDone << "\n";
  if (nLeptons == 0 && nAntileptons == 0) {
    std::cerr << "Number of leptons, number of anti-leptons should all be greater than 1.\n";
    return 1;
  }
  if (nLeptonPairs != nLeptonPairsToBeDone) {
    std::cerr << "The number of electron-positron pairs should be the same as the number of electron-positron pairs which should be transported.\n";
    return 1;
  }
  if (nLeptons != nLeptonsToBeDone) {
    std::cerr << "The number of leptons should be the same as the number of leptons which should be transported.\n";
    return 1;
  }
  if (nLeptonsInAcceptance ==  (nEvents/ratioTrigger)) {
    std::cerr << "The number of leptons in acceptance should be at least equaled to the number of events.\n";
    return 1;
  }
  if (nLeptonPairs <  nLeptonsInAcceptance) {
    std::cerr << "The number of positron-electron pairs should be at least equaled to the number of leptons in acceptance.\n";
    return 1;
  }

  return 0;
}
