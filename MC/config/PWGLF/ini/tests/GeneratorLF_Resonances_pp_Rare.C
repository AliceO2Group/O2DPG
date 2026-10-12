
int External()
{
  const std::string path{"o2sim_Kine.root"};
  const int numberOfGapEvents{4}; // generateLFRapidity(..., gap=5)
  const std::vector<int> injectedPDGs = {
    9010221,  // f0(980)
    3324, -3324,       // Xi(1530)0 and anti-Xi(1530)0
    123324, -123324,   // Xi(1820)0 and anti-Xi(1820)0
    123314, -123314,   // Xi(1820)- and Xi(1820)+
    123334, -123334    // Omega(2012)- and Omega(2012)+
  };
  const std::vector<std::vector<int>> decayDaughters = {
    {211, -211},
    {3312, 211}, {-3312, -211},
    {3122, 310}, {-3122, 310},
    {3122, -321}, {-3122, 321},
    {3312, 310}, {-3312, 310}
  };

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

  std::vector<int> nSignal(injectedPDGs.size(), 0);
  std::vector<int> nNotDecayed(injectedPDGs.size(), 0);
  std::vector<std::vector<int>> nDecays;
  for (const auto& daughters : decayDaughters) {
    nDecays.emplace_back(daughters.size(), 0);
  }

  int numberOfEventsProcessed{0};
  int numberOfEventsProcessedWithoutInjection{0};
  for (Long64_t i = 0; i < tree->GetEntries(); ++i) {
    tree->GetEntry(i);
    ++numberOfEventsProcessed;
    bool hasInjection{false};
    for (const auto& track : *tracks) {
      const auto pdg = track.GetPdgCode();
      const auto it = std::find(injectedPDGs.begin(), injectedPDGs.end(), pdg);
      if (it == injectedPDGs.end()) {
        continue;
      }
      const auto index = static_cast<size_t>(std::distance(injectedPDGs.begin(), it));
      ++nSignal[index];
      if (track.getFirstDaughterTrackId() < 0) {
        ++nNotDecayed[index];
        continue;
      }
      for (int j = track.getFirstDaughterTrackId(); j <= track.getLastDaughterTrackId(); ++j) {
        const auto pdgDau = tracks->at(j).GetPdgCode();
        bool foundDau{false};
        for (size_t k = 0; k < decayDaughters[index].size(); ++k) {
          if (pdgDau == decayDaughters[index][k]) {
            ++nDecays[index][k];
            foundDau = true;
            hasInjection = true;
            break;
          }
        }
        if (!foundDau) {
          std::cerr << "Decay daughter not found: " << pdg << " -> " << pdgDau
                    << " (mother=" << track.getMotherTrackId()
                    << ", secondMother=" << track.getSecondMotherTrackId() << ")\n";
        }
      }
    }
    if (!hasInjection) {
      ++numberOfEventsProcessedWithoutInjection;
    }
  }

  std::cout << "--------------------------------\n";
  std::cout << "# Events: " << tree->GetEntries() << "\n";
  for (size_t i = 0; i < injectedPDGs.size(); ++i) {
    std::cout << "# Mother\n";
    std::cout << injectedPDGs[i] << " generated: " << nSignal[i]
              << ", " << nNotDecayed[i] << " did not decay\n";
    for (size_t j = 0; j < decayDaughters[i].size(); ++j) {
      std::cout << "# Daughter " << decayDaughters[i][j] << ": " << nDecays[i][j] << "\n";
    }
  }
  std::cout << "--------------------------------\n";
  std::cout << "Number of events processed: " << numberOfEventsProcessed << "\n";
  std::cout << "Number of input for the gap events: " << numberOfGapEvents << "\n";
  std::cout << "Number of events processed without injection: "
            << numberOfEventsProcessedWithoutInjection << "\n";
  const double ratioOfNormalEvents = numberOfEventsProcessed
                                       ? static_cast<double>(numberOfEventsProcessedWithoutInjection) /
                                           numberOfEventsProcessed
                                       : 0.0;
  std::cout << "Fraction without injection: " << ratioOfNormalEvents << "\n";
  const double expectedRatio = static_cast<double>(numberOfGapEvents) / (numberOfGapEvents + 1);
  std::cout << "Expected fraction for 1+" << numberOfGapEvents << " pattern: " << expectedRatio << "\n";

  // Same basic gap sanity check as the referenced O2DPG test.
  if (ratioOfNormalEvents > 0.90 || ratioOfNormalEvents < 0.70) {
    std::cerr << "The number of injected events is too low or too high\n";
    return 1;
  }
  return 0;
}
