int External()
{
    std::string path{"o2sim_Kine.root"};
    int numberOfInjectedSignalsPerEvent{1};
    int numberOfGapEvents{4};
    int numberOfEventsProcessed{0};
    int numberOfEventsProcessedWithoutInjection{0};
    std::vector<int> injectedPDGs = {
        323,     // K*+-
        -323,    // K*bar+-
        9010221, // f_0(980)
        113,     // rho(770)0
        213,     // rho(770)+
        -213,    // rho(770)bar-
        3224,    // Sigma(1385)+
        -3224,   // Sigma(1385)bar-
        3114,    // Sigma(1385)-
        -3114,   // Sigma(1385)bar+
        3124,    // Lambda(1520)0
        -3124,   // Lambda(1520)0bar
        3324,    // Xi(1530)0
        -3324,   // Xi(1530)0bar
        10323,   // K1(1270)+
        -10323,  // K1(1270)-bar
        2224,    // Delta(1232)+
        -2224,   // Delta(1232)bar-
        2114,    // Delta(1232)0
        -2114,   // Delta(1232)0bar
        123314,  // Xi(1820)-
        -123314, // Xi(1820)+
        123324,  // Xi(1820)0
        -123324  // Xi(1820)0bar
    };
    std::vector<std::vector<int>> decayDaughters = {
        {311, 211},    // K*+-
        {-311, -211},  // K*bar+-
        {211, -211},   // f_0(980)
        {211, -211},   // rho(770)0
        {211, 111},    // rho(770)+
        {-211, 111},   // rho(770)bar-
        {3122, 211},   // Sigma(1385)+
        {-3122, -211}, // Sigma(1385)bar-
        {3122, -211},  // Sigma(1385)-
        {-3122, 211},  // Sigma(1385)bar+
        {2212, -321},  // Lambda(1520)0
        {-2212, 321},  // Lambda(1520)0bar
        {3312, 211},   // Xi(1530)0
        {-3312, -211}, // Xi(1530)0bar
        {321, 211},    // K1(1270)+
        {-321, -211},  // K1(1270)-bar
        {2212, 211},   // Delta(1232)+
        {-2212, -211}, // Delta(1232)bar-
        {2212, -211},  // Delta(1232)-
        {-2212, 211},  // Delta(1232)bar+
        {3122, -311},  // Xi(1820)-
        {3122, 311},   // Xi(1820)+
        {3122, 310},   // Xi(1820)0
        {-3122, 310}   // Xi(1820)0bar
    };

    auto nInjection = injectedPDGs.size();

    TFile file(path.c_str(), "READ");
    if (file.IsZombie())
    {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    if (!tree)
    {
        std::cerr << "Cannot find tree o2sim in file " << path << "\n";
        return 1;
    }
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    std::vector<int> nSignal;
    for (int i = 0; i < nInjection; i++)
    {
        nSignal.push_back(0);
    }
    std::vector<std::vector<int>> nDecays;
    std::vector<int> nNotDecayed;
    for (int i = 0; i < nInjection; i++)
    {
        std::vector<int> nDecay;
        for (int j = 0; j < decayDaughters[i].size(); j++)
        {
            nDecay.push_back(0);
        }
        nDecays.push_back(nDecay);
        nNotDecayed.push_back(0);
    }
    auto nEvents = tree->GetEntries();
    bool hasInjection = false;
    for (int i = 0; i < nEvents; i++)
    {
        hasInjection = false;
        numberOfEventsProcessed++;
        auto check = tree->GetEntry(i);
        for (int idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
        {
            auto track = tracks->at(idxMCTrack);
            auto pdg = track.GetPdgCode();
            auto it = std::find(injectedPDGs.begin(), injectedPDGs.end(), pdg);
            int index = std::distance(injectedPDGs.begin(), it); // index of injected PDG
            if (it != injectedPDGs.end())                        // found
            {
                // count signal PDG
                nSignal[index]++;
                if (track.getFirstDaughterTrackId() < 0)
                {
                    nNotDecayed[index]++;
                    continue;
                }
                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j)
                {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    bool foundDau = false;
                    // count decay PDGs
                    for (int idxDaughter = 0; idxDaughter < decayDaughters[index].size(); ++idxDaughter)
                    {
                        if (pdgDau == decayDaughters[index][idxDaughter])
                        {
                            nDecays[index][idxDaughter]++;
                            foundDau = true;
                            hasInjection = true;
                            break;
                        }
                    }
                    if (!foundDau)
                    {
                        std::cerr << "Decay daughter not found: " << pdg << " -> " << pdgDau << "\n";
                    }
                }
            }
        }
        if (!hasInjection)
        {
            numberOfEventsProcessedWithoutInjection++;
        }
    }
    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    for (int i = 0; i < nInjection; i++)
    {
        std::cout << "# Mother \n";
        std::cout << injectedPDGs[i] << " generated: " << nSignal[i] << ", " << nNotDecayed[i] << " did not decay\n";
        if (nSignal[i] == 0)
        {
            std::cerr << "No generated: " << injectedPDGs[i] << "\n";
            // return 1; // At least one of the injected particles should be generated
        }
        for (int j = 0; j < decayDaughters[i].size(); j++)
        {
            std::cout << "# Daughter " << decayDaughters[i][j] << ": " << nDecays[i][j] << "\n";
        }
        // if (nSignal[i] != nEvents * numberOfInjectedSignalsPerEvent)
        // {
        //     std::cerr << "Number of generated: " << injectedPDGs[i] << ", lower than expected\n";
        //     // return 1; // Don't need to return 1, since the number of generated particles is not the same for each event
        // }
    }
    std::cout << "--------------------------------\n";
    std::cout << "Number of events processed: " << numberOfEventsProcessed << "\n";
    std::cout << "Number of input for the gap events: " << numberOfGapEvents << "\n";
    std::cout << "Number of events processed without injection: " << numberOfEventsProcessedWithoutInjection << "\n";
    // injected event + numberOfGapEvents*gap events + injected event + numberOfGapEvents*gap events + ...
    // total fraction of the gap event: numberOfEventsProcessedWithoutInjection/numberOfEventsProcessed
    float ratioOfNormalEvents = numberOfEventsProcessedWithoutInjection / numberOfEventsProcessed;
    if (ratioOfNormalEvents > 0.75)
    {
        std::cout << "The number of injected event is loo low!!" << std::endl;
        return 1;
    }

    return 0;
}

void GeneratorLF_Resonances_pp1360_injection() { External(); }
