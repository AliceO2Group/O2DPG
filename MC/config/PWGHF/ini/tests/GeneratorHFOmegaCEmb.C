int External()
{
    std::string path{"o2sim_Kine.root"};
    int checkPdgSignal{4332};
    std::vector<int> checkPdgDecays{3334, 211};

    std::cout << "Check for\nsignal PDG " << checkPdgSignal;
    for (auto pdg : checkPdgDecays)
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

    int nSignal{};
    std::vector<int> nDecays(checkPdgDecays.size(), 0);
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++)
    {
        tree->GetEntry(i);
        for (auto &track : *tracks)
        {
            auto pdg = track.GetPdgCode();
            if (std::abs(pdg) == checkPdgSignal)
            {
                // count signal PDG
                nSignal++;

                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j)
                {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    // count decay PDGs
                    for (int i = 0, n = checkPdgDecays.size(); i < n; ++i)
                    {
                        if (std::abs(pdgDau) == checkPdgDecays[i])
                        {
                            nDecays[i]++;
                        }
                    }
                }
            }
        }
    }
    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << "# Mother " << checkPdgSignal << ": " << nSignal << "\n";

    for (int i = 0; i < checkPdgDecays.size(); i++)
    {
        std::cout << "# Daughter " << checkPdgDecays[i] << ": " << nDecays[i] << "\n";
    }

    if (nSignal != nEvents * 3)
    {
        std::cerr << "Number of generated" << checkPdgSignal << "lower than expected\n";
        return 1;
    }

    for (int i = 0; i < checkPdgDecays.size(); i++)
    {
        if (nDecays[i] != nSignal)
        {
            std::cerr << "Number of generated" << checkPdgDecays[i] << "lower than expected\n";
            return 1;
        }
    }

    return 0;
}
