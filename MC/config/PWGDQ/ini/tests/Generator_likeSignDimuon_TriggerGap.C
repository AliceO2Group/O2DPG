int External()
{
  const int ratioTrigger = 1./3;
  std::string path{"o2sim_Kine.root"};
  TFile file(path.c_str(), "READ");
  if (file.IsZombie()) {
    std::cerr << "Cannot open ROOT file " << path << "\n";
    return 1;
  }

  auto tree = (TTree*)file.Get("o2sim");
  std::vector<o2::MCTrack>* tracks{};
  tree->SetBranchAddress("MCTrack", &tracks);

  o2::dataformats::MCEventHeader* eventHeader = nullptr;
  tree->SetBranchAddress("MCEventHeader.", &eventHeader);

  int nEvents = tree->GetEntries();
  int nEventsMB = 0;
  int nEventsSignal = 0;
  int nEventsWithLSM = 0;
  int nMuonsInAcceptance = 0;
  int nLSMPairs = 0;

  for (int i = 0; i < nEvents; i++) {
    tree->GetEntry(i);
    if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
      bool isValid = false;
      int subGeneratorId = eventHeader->getInfo<int>(
        o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
        if (subGeneratorId == 0) {
          nEventsMB++;
        } else if (subGeneratorId == 1) {
          nEventsSignal++;
        }
    }

    std::vector<int> muonPDGs;
    for (const auto& track : *tracks) {
      if (std::abs(track.GetPdgCode()) != 13) {
        continue;
      }
      double y = track.GetRapidity();
      if (y > -4.3 && y < -2.2) {
        muonPDGs.push_back(track.GetPdgCode());
        nMuonsInAcceptance++;
      }
    }
    if (muonPDGs.size() < 2) {
      continue;
    }
    int nLsmPairsEvent = 0;
    for (size_t j = 0; j < muonPDGs.size(); j++) {
      for (size_t k = j + 1; k < muonPDGs.size(); k++) {
        if (muonPDGs[j] * muonPDGs[k] > 0) {
          nLsmPairsEvent++;
        }
      }
    }
    if (nLsmPairsEvent > 0) {
      nEventsWithLSM++;
      nLSMPairs += nLsmPairsEvent;
    }
  }

  std::cout << "#events: " << nEvents << "\n"
            << "#minimum bias events: " << nEventsMB << "\n"
            << "#trigger events: " << nEventsSignal << "\n"
            << "#events with like-sign muons: " << nEventsWithLSM << "\n"
            << "#muons in acceptance: " << nMuonsInAcceptance << "\n"
            << "#like-sign dimuon pairs in acceptance: " << nLSMPairs << "\n";

  if (nLSMPairs == 0) {
    std::cerr << "Number of like-sign muon pairs should be greater than 0.\n";
    return 1;
  }
  if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 ||
      nEventsMB > nEvents * (1 - ratioTrigger) * 1.05) { // we put some tolerance since the number of generated events is small
    std::cerr << "Number of generated MB events different than expected\n";
    return 1;
  }
  if (nEventsSignal < nEvents * ratioTrigger * 0.95 ||
      nEventsSignal > nEvents * ratioTrigger * 1.05) {
    std::cerr << "Number of generated events injected different than expected\n";
    return 1;
  }

  return 0;
}
