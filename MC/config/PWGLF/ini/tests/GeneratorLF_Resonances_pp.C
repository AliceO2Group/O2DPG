int External()
{
    std::string path{"o2sim_Kine.root"};
    int numberOfInjectedSignalsPerEvent{10};
    std::vector<int> injectedPDGs{
        313,     // K0*0
        -313,    // K0*0bar
        323,     // K*+-
        -323,    // K*bar+-
        333,     // phi
        9010221, // f_0(980)
        // 9030221, // f_0(1500)
        // 10331,   // f_0(1710)
        113,   // rho(770)0
        213,   // rho(770)+
        -213,  // rho(770)bar-
        3224,  // Sigma(1385)+
        -3224, // Sigma(1385)bar-
        3124,  // Lambda(1520)0
        -3124, // Lambda(1520)0bar
        3324,  // Xi(1530)0
        -3324  // Xi(1530)0bar
        // 123314,  // Xi(1820)-
        // -123314, // Xi(1820)+
        // 123324,  // Xi(1820)0
        // -123324  // Xi(1820)0bar
    };
    std::vector<std::vector<int>> decayDaughters{
        {321, 211},   // K0*0
        {-321, -211}, // K0*0bar
        {311, 211},   // K*+-
        {-311, -211}, // K*bar+-
        {321, 321},   // phi
        {211, 211},   // f_0(980)
        //{211, 211},         // f_0(1500)
        //{211, 211},         // f_0(1710)
        {211, 211},    // rho(770)0
        {211, 111},    // rho(770)+
        {-211, -111},  // rho(770)bar-
        {3122, 211},   // Sigma(1385)+
        {-3122, -211}, // Sigma(1385)bar-
        {3212, 321},   // Lambda(1520)0
        {-3212, -321}, // Lambda(1520)0bar
        {3312, 211},   // Xi(1530)0
        {-3312, -211}  // Xi(1530)0bar
        // {211, 211, 111},    // Xi(1820)-
        // {-211, -211, -111}, // Xi(1820)+
        // {211, 211, 111},    // Xi(1820)0
        // {-211, -211, -111}  // Xi(1820)0bar
    };

    std::cout << "Check for injected particles:";
    for (auto pdg : injectedPDGs)
    {
        std::cout << "\ndecay PDG " << pdg;
    }
    std::cout << "\n";

    TFile file(path.c_str(), "READ");
    if (file.IsZombie())
    {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    std::vector<int> nSignal(injectedPDGs.size(), 0);
    std::vector<std::vector<int>> nDecays;
    for (int i = 0; i < injectedPDGs.size(); i++)
    {
        nDecays.push_back(std::vector<int>(decayDaughters[i].size(), 0));
    }
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++)
    {
        tree->GetEntry(i);
        for (auto &track : *tracks)
        {
            auto pdg = track.GetPdgCode();
            auto it = std::find(injectedPDGs.begin(), injectedPDGs.end(), pdg);
            int index = std::distance(injectedPDGs.begin(), it); // index of injected PDG
            if (it != injectedPDGs.end()) // found
            {
                // count signal PDG
                nSignal[index]++;
                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j)
                {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    // count decay PDGs
                    for (int i = 0, n = decayDaughters[index].size(); i < n; ++i)
                    {
                        if (pdgDau == decayDaughters[index][i])
                        {
                            nDecays[index][i]++;
                        }
                    }
                }
            }
        }
    }
    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    for (int i = 0; i < injectedPDGs.size(); i++)
    {
        std::cout << "# Mother \n";
        std::cout << injectedPDGs[i] << ": " << nSignal[i] << "\n";
        for (int j = 0; j < decayDaughters[i].size(); j++)
        {
            std::cout << "# Daughter " << decayDaughters[i][j] << ": " << nDecays[i][j] << "\n";
        }
        if (nSignal[i] != nEvents * numberOfInjectedSignalsPerEvent)
        {
            std::cerr << "Number of generated" << injectedPDGs[i] << "lower than expected\n";
            return 1;
        }
        for (int j = 0; j < decayDaughters[i].size(); j++)
        {
            if (nDecays[i][j] != nSignal[i])
            {
                std::cerr << "Number of generated" << decayDaughters[i][j] << "lower than expected\n";
                return 1;
            }
        }
    }

    return 0;
}

int Pythia8()
{
    // THIS IS OBVIOUSLY NOT HOW A TEST SHOULD LOOK LIKE.
    // We are wating for the G4 patch with the correct Omega_c lifetime, then it will be updated
    return 0;
}
