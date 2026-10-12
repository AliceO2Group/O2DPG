int External()
{
    const std::string path{"o2sim_Kine.root"};

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

    // Counters
    int nMBPhi = 0;
    int nKPlusFromMBPhi = 0;
    int nKMinusFromMBPhi = 0;
    int numberOfEventsProcessed = 0;

    for (Long64_t i = 0; i < tree->GetEntries(); ++i)
    {
        tree->GetEntry(i);
        ++numberOfEventsProcessed;

        for (size_t idx = 0; idx < tracks->size(); ++idx)
        {
            const auto &track = tracks->at(idx);
            const auto pdg = track.GetPdgCode();

            if (pdg == 333)
            {
                ++nMBPhi;

                if (track.getFirstDaughterTrackId() >= 0)
                {
                    for (int j = track.getFirstDaughterTrackId(); j <= track.getLastDaughterTrackId(); ++j)
                    {
                        auto dauPdg = tracks->at(j).GetPdgCode();
                        if (dauPdg == 321)
                        {
                            ++nKPlusFromMBPhi;
                        }
                        if (dauPdg == -321)
                        {
                            ++nKMinusFromMBPhi;
                        }
                    }
                }
            }
        }
    }

    // --------------------------- Output ---------------------------
    std::cout << "=================================================\n";
    std::cout << "Total Events: " << tree->GetEntries() << "\n\n";
    std::cout << "Total events processed: " << numberOfEventsProcessed << "\n";
    std::cout << "Total Minimum Bias Phi (333): " << nMBPhi << "\n";
    std::cout << "  -> Decayed to K+: " << nKPlusFromMBPhi << "\n";
    std::cout << "  -> Decayed to K-: " << nKMinusFromMBPhi << "\n";
    std::cout << "=================================================\n";

    return 0;
}

void GeneratorLF_doublephi_trigger()
{
    External();
}
