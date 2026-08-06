int External()
{
    std::string path{"o2sim_Kine.root"};

    //Kept only target single resonance (e.g. PDG 10331 -> K0S K0S)
    std::vector<int> injectedPDGs = {10331};
    std::vector<std::vector<int>> decayDaughters = {{310, 310}};

    int numberOfInjectedSignalsPerEvent = 5;
    int numberOfEventsProcessed = 0;
    int numberOfEventsProcessedWithoutInjection = 0;

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

    std::vector<int> nSignal(nInjection, 0);
    std::vector<std::vector<int>> nDecays;
    std::vector<int> nNotDecayed(nInjection, 0);

    for (size_t i = 0; i < nInjection; i++)
    {
        std::vector<int> nDecay(decayDaughters[i].size(), 0);
        nDecays.push_back(nDecay);
    }

    auto nEvents = tree->GetEntries();
    bool hasInjection = false;

    for (int i = 0; i < nEvents; i++)
    {
        hasInjection = false;
        numberOfEventsProcessed++;
        tree->GetEntry(i);

        for (size_t idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
        {
            auto track = tracks->at(idxMCTrack);
            auto pdg = track.GetPdgCode();
            auto it = std::find(injectedPDGs.begin(), injectedPDGs.end(), pdg);

            if (it != injectedPDGs.end()) // Found injected mother particle
            {
                int index = std::distance(injectedPDGs.begin(), it);
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

                    for (size_t idxDaughter = 0; idxDaughter < decayDaughters[index].size(); ++idxDaughter)
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
    for (size_t i = 0; i < nInjection; i++)
    {
        std::cout << "# Mother PDG: " << injectedPDGs[i] << "\n";
        std::cout << "  Generated: " << nSignal[i] << ", " << nNotDecayed[i] << " did not decay\n";

        if (nSignal[i] == 0)
        {
            std::cerr << "No generated signal found for PDG: " << injectedPDGs[i] << "\n";
        }
        for (size_t j = 0; j < decayDaughters[i].size(); j++)
        {
            std::cout << "  Daughter PDG " << decayDaughters[i][j] << ": " << nDecays[i][j] << "\n";
        }
    }
    std::cout << "--------------------------------\n";
    std::cout << "Number of events processed: " << numberOfEventsProcessed << "\n";
    std::cout << "Number of events without injection: " << numberOfEventsProcessedWithoutInjection << "\n";

    return 0;
}

void generatorLF_Resonances_flat_mass() { External(); }