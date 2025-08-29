int External() {
  std::string path{"o2sim_Kine.root"};

  int checkPdgDecayElectron = 11;
  int checkPdgQuarkOne = 4;
  int checkPdgQuarkTwo = 5;
  float ratioTrigger = 1. / 5; // one event triggered out of 5

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

  int nEventsMB{}, nEventsInjOne{}, nEventsInjTwo{};
  int nQuarksOne{}, nQuarksTwo{};
  int nElectrons{};
  auto nEvents = tree->GetEntries();

  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);

    // check subgenerator information
    if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
      bool isValid = false;
      int subGeneratorId = eventHeader->getInfo<int>(
          o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
      if (subGeneratorId == 0) {
        nEventsMB++;
      } else if (subGeneratorId == checkPdgQuarkOne) {
        nEventsInjOne++;
      } else if (subGeneratorId == checkPdgQuarkTwo) {
        nEventsInjTwo++;
      }
    } // if event header

    int nelectronsev = 0;

    for (auto &track : *tracks) {
      auto pdg = track.GetPdgCode();
      if (std::abs(pdg) == checkPdgQuarkOne) {
        nQuarksOne++;
        continue;
      }
      if (std::abs(pdg) == checkPdgQuarkTwo) {
        nQuarksTwo++;
        continue;
      }

      auto y = track.GetRapidity();
      if (std::abs(pdg) == checkPdgDecayElectron) {
        int igmother = track.getMotherTrackId();
        auto gmTrack = (*tracks)[igmother];
        int gmpdg = gmTrack.GetPdgCode();
        if (int(std::abs(gmpdg) / 100.) == 4 ||
            int(std::abs(gmpdg) / 1000.) == 4 ||
            int(std::abs(gmpdg) / 100.) == 5 ||
            int(std::abs(gmpdg) / 1000.) == 5) {
          nElectrons++;
          nelectronsev++;
        } // gmpdg
      } // pdgdecay
    } // loop track
    // std::cout << "#electrons per event: " << nelectronsev << "\n";
  }

  std::cout << "--------------------------------\n";
  std::cout << "# Events: " << nEvents << "\n";
  std::cout << "# MB events: " << nEventsMB << "\n";
  std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkOne)
            << nEventsInjOne << "\n";
  std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkTwo)
            << nEventsInjTwo << "\n";
  std::cout << Form("# %d (anti)quarks: ", checkPdgQuarkOne) << nQuarksOne
            << "\n";
  std::cout << Form("# %d (anti)quarks: ", checkPdgQuarkTwo) << nQuarksTwo
            << "\n";

  if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 ||
      nEventsMB > nEvents * (1 - ratioTrigger) *
                      1.05) { // we put some tolerance since the number of
                              // generated events is small
    std::cerr << "Number of generated MB events different than expected\n";
    return 1;
  }
  if (nEventsInjOne < nEvents * ratioTrigger * 0.5 * 0.95 ||
      nEventsInjOne > nEvents * ratioTrigger * 0.5 * 1.05) {
    std::cerr << "Number of generated events injected with " << checkPdgQuarkOne
              << " different than expected\n";
    return 1;
  }
  if (nEventsInjTwo < nEvents * ratioTrigger * 0.5 * 0.95 ||
      nEventsInjTwo > nEvents * ratioTrigger * 0.5 * 1.05) {
    std::cerr << "Number of generated events injected with " << checkPdgQuarkTwo
              << " different than expected\n";
    return 1;
  }
  if (nQuarksOne <
      nEvents *
          ratioTrigger) { // we expect anyway more because the same quark is
                          // repeated several time, after each gluon radiation
    std::cerr << "Number of generated (anti)quarks " << checkPdgQuarkOne
              << " lower than expected\n";
    return 1;
  }
  if (nQuarksTwo <
      nEvents *
          ratioTrigger) { // we expect anyway more because the same quark is
                          // repeated several time, after each gluon radiation
    std::cerr << "Number of generated (anti)quarks " << checkPdgQuarkTwo
              << " lower than expected\n";
    return 1;
  }
  std::cout << "#electrons: " << nElectrons << "\n";

  return 0;
} // external
