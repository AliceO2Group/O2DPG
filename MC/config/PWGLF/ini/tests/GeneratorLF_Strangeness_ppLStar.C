int External()
{
    std::string path{"o2sim_Kine.root"};
    const int pdgMother = 3124; // Lambda(1520)0

    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }
    auto tree = (TTree *)file.Get("o2sim");
    if (!tree) {
        std::cerr << "Cannot find tree o2sim in file " << path << "\n";
        return 1;
    }
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    const auto nEvents = tree->GetEntries();
    int nMother = 0;
    int nNotDecayed = 0;
    int nBadDecay = 0;                // mothers not decaying exactly to Lambda + gamma
    std::vector<int> motherPerEvent;  // number of injected mothers in each event

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);

        int nInEvent = 0;
        for (auto &track : *tracks) {
            const int pdg = track.GetPdgCode();
            if (std::abs(pdg) != pdgMother) {
                continue;
            }
            nInEvent++;
            nMother++;

            if (track.getFirstDaughterTrackId() < 0) {
                nNotDecayed++;
                continue;
            }
            const int expectedLambda = (pdg > 0) ? 3122 : -3122;
            int nLambda = 0, nGamma = 0, nDau = 0;
            for (int j = track.getFirstDaughterTrackId(); j <= track.getLastDaughterTrackId(); ++j) {
                const int pdgDau = tracks->at(j).GetPdgCode();
                nDau++;
                if (pdgDau == expectedLambda) nLambda++;
                if (pdgDau == 22) nGamma++;
            }
            if (nDau != 2 || nLambda != 1 || nGamma != 1) {
                nBadDecay++;
                std::cerr << "Unexpected decay of " << pdg << " (" << nDau << " daughters)\n";
            }
        }
        motherPerEvent.push_back(nInEvent);
    }

    // the trigger ratio is inferred from the first event containing a mother
    // (the generator counts events from 1 and injects every triggerRatio-th event)
    int triggerRatio = 0;
    for (int i = 0; i < nEvents; i++) {
        if (motherPerEvent[i] > 0) {
            triggerRatio = i + 1;
            break;
        }
    }

    int nEventsWrongCount = 0;
    int nGapEvents = 0;
    if (triggerRatio > 0) {
        for (int i = 0; i < nEvents; i++) {
            const bool isGapEvent = ((i + 1) % triggerRatio == 0);
            if (isGapEvent) {
                nGapEvents++;
            }
            const int nExpected = isGapEvent ? 1 : 0;
            if (motherPerEvent[i] != nExpected) {
                nEventsWrongCount++;
                std::cerr << "Event " << i << ": found " << motherPerEvent[i]
                          << " Lambda(1520), expected " << nExpected << "\n";
            }
        }
    }

    std::cout << "--------------------------------\n";
    std::cout << "# Events:                  " << nEvents << "\n";
    std::cout << "# Inferred trigger ratio:  " << triggerRatio << "\n";
    std::cout << "# Gap-trigger events:      " << nGapEvents << "\n";
    std::cout << "# Lambda(1520) + anti:     " << nMother << "\n";
    std::cout << "# not decayed:             " << nNotDecayed << "\n";
    std::cout << "# unexpected decays:       " << nBadDecay << "\n";
    std::cout << "# events wrong count:      " << nEventsWrongCount << "\n";
    std::cout << "--------------------------------\n";

    if (triggerRatio == 0) {
        std::cerr << "No Lambda(1520) found in any event\n";
        return 1;
    }
    if (nMother != nGapEvents || nEventsWrongCount > 0) {
        std::cerr << "Lambda(1520) must appear exactly once every triggerRatio events\n";
        return 1;
    }
    if (nNotDecayed > 0 || nBadDecay > 0) {
        std::cerr << "Lambda(1520) must always decay to Lambda + gamma\n";
        return 1;
    }
    return 0;
}

void GeneratorLF_Strangeness_ppLStar() { External(); }