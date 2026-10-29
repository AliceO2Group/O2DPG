int External() {

  int checkPdgDecayMuon = 13;
  int checkPdgQuarkOne{4};
  int checkPdgQuarkTwo{5};
  float ratioQuarkOneTwo{2.};

  float ratioTrigger = 1./3; // one event triggered out of 5

  std::string path{"o2sim_Kine.root"};

  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file" << path << "\n";
    return 1;
  }

  auto tree = (TTree *)file.Get("o2sim");
  if (!tree) {
    std::cerr << "Cannot find tree o2sim in file" << path << "\n";
    return 1;
  }

  std::vector<o2::MCTrack> *tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  o2::dataformats::MCEventHeader *eventHeader = nullptr;
  tree->SetBranchAddress("MCEventHeader.", &eventHeader);

  int nEventsMB{0};
  int nEventsInjOne{0};
  int nEventsInjTwo{0};
  int nQuarks{0};
  int nMuons{0};

  int nMuonsInAcceptance{};

  auto nEvents = tree->GetEntries();

  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    // check subgenerator information
    if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
      bool isValid = false;
      int subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
      if (subGeneratorId == 0) {
        nEventsMB++;
      } else if (subGeneratorId == checkPdgQuarkOne) {
        nEventsInjOne++;
      } else if (subGeneratorId == checkPdgQuarkTwo) {
        nEventsInjTwo++;
      }
    }

    int nmuonsev = 0;
    int nmuonsevinacc = 0;

    for (auto &track : *tracks) {
      auto pdg = track.GetPdgCode();
      if (std::abs(pdg) == checkPdgQuark) {
        nQuarks++;
        continue;
      } // pdgquark
      auto y = track.GetRapidity();
      if (std::abs(pdg) == checkPdgDecayMuon) {
        int igmother = track.getMotherTrackId();
        auto gmTrack = (*tracks)[igmother];
        int gmpdg = gmTrack.GetPdgCode();
        if (int(std::abs(gmpdg) / 100.) == 4 ||
            int(std::abs(gmpdg) / 1000.) == 4) {
          nMuons++;
          nmuonsev++;
          if (-4.3 < y && y < -2.2) {
            nMuonsInAcceptance++;
            nmuonsevinacc++;
          }
        } // gmpdg

      } // pdgdecay

    } // loop track
    // std::cout << "#muons per event: " << nmuonsev << "\n";
    // std::cout << "#muons in acceptance per event: " << nmuonsev << "\n";
  } // events

  std::cout << "#events: " << nEvents << "\n";
  std::cout << "# MB events: " << nEventsMB << "\n";
  std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkOne)
            << nEventsInjOne << "\n";
  std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkTwo)
            << nEventsInjTwo << "\n";
  if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 ||
      nEventsMB > nEvents * (1 - ratioTrigger) *
                      1.05) { // we put some tolerance since the number of
                              // generated events is small
    std::cerr << "Number of generated MB events different than expected\n";
    return 1;
  }
  if ((nEventsInjOne + nEventsInjTwo) < nEvents * ratioTrigger * 0.95 ||
      (nEventsInjOne + nEventsInjOne) > nEvents * ratioTrigger * 1.05) {
    std::cerr << "Number of generated events injected with " << checkPdgQuarkOne << " and " << checkPdgQuarkTwo
              << " different than expected\n";
    return 1;
  }
  if (std::abs(float(nEventsInjOne) / nEventsInjOne - ratioQuarkOneTwo) / ratioQuarkOneTwo > 0.1) {
    std::cerr << "Ratio between quark " << checkPdgQuarkOne << " and quark " << checkPdgQuarkTwo
              << " different than expected\n";
    return 1;
  }
  std::cout << "#muons: " << nMuons << "\n";
  std::cout << "#muons in acceptance: " << nMuonsInAcceptance << "\n";

  return 0;
} // external
