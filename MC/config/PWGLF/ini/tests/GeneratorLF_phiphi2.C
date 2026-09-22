int External()
{
    const std::string path{"/home/sawan/alice/practice/testMC/PhiPhi/o2sim_Kine.root"};

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
    int nResonance999999 = 0;
    int nNotDecayed999999 = 0;
    int nPhiFromResonance = 0;

    // Decay counts into K+ K- (PDG 321, -321)
    int nKPlusFromResonancePhi = 0;
    int nKMinusFromResonancePhi = 0;

    int nDirectInjectedPhi = 0;
    int nMBPhi = 0;

    int nKPlusFromDirectPhi = 0;
    int nKMinusFromDirectPhi = 0;
    int nKPlusFromMBPhi = 0;
    int nKMinusFromMBPhi = 0;

    int numberOfEventsProcessed = 0;
    int numberOfEventsProcessedWithoutInjection = 0;

    for (Long64_t i = 0; i < tree->GetEntries(); ++i)
    {
        tree->GetEntry(i);
        ++numberOfEventsProcessed;
        bool hasInjection = false;

        for (size_t idx = 0; idx < tracks->size(); ++idx)
        {
            const auto &track = tracks->at(idx);
            const auto pdg = track.GetPdgCode();

            // 1. Process Custom Resonance 999999
            if (pdg == 999999)
            {
                ++nResonance999999;
                hasInjection = true;

                if (track.getFirstDaughterTrackId() < 0)
                {
                    ++nNotDecayed999999;
                    continue;
                }

                // Loop through daughters of 999999 (Phi mesons)
                for (int j = track.getFirstDaughterTrackId(); j <= track.getLastDaughterTrackId(); ++j)
                {
                    const auto &phiTrack = tracks->at(j);
                    if (phiTrack.GetPdgCode() == 333)
                    {
                        ++nPhiFromResonance;

                        // Check daughters of this Phi (granddaughters of 999999)
                        if (phiTrack.getFirstDaughterTrackId() >= 0)
                        {
                            for (int k = phiTrack.getFirstDaughterTrackId(); k <= phiTrack.getLastDaughterTrackId(); ++k)
                            {
                                auto grandDauPdg = tracks->at(k).GetPdgCode();
                                if (grandDauPdg == 321) ++nKPlusFromResonancePhi;
                                if (grandDauPdg == -321) ++nKMinusFromResonancePhi;
                            }
                        }
                    }
                }
            }

            // 2. Process Phi (333) Mesons
            else if (pdg == 333)
            {
                int motherId = track.getMotherTrackId();
                int motherPdg = (motherId >= 0 && motherId < (int)tracks->size()) ? tracks->at(motherId).GetPdgCode() : 0;

                // Skip Phi from 999999 here as it was handled above
                if (motherPdg == 999999)
                {
                    continue;
                }

                bool isDirectInjected = (motherId < 0);

                if (isDirectInjected)
                {
                    ++nDirectInjectedPhi;
                    hasInjection = true;

                    if (track.getFirstDaughterTrackId() >= 0)
                    {
                        for (int j = track.getFirstDaughterTrackId(); j <= track.getLastDaughterTrackId(); ++j)
                        {
                            auto dauPdg = tracks->at(j).GetPdgCode();
                            if (dauPdg == 321) ++nKPlusFromDirectPhi;
                            if (dauPdg == -321) ++nKMinusFromDirectPhi;
                        }
                    }
                }
                else
                {
                    // Minimum Bias Phi
                    ++nMBPhi;

                    if (track.getFirstDaughterTrackId() >= 0)
                    {
                        for (int j = track.getFirstDaughterTrackId(); j <= track.getLastDaughterTrackId(); ++j)
                        {
                            auto dauPdg = tracks->at(j).GetPdgCode();
                            if (dauPdg == 321) ++nKPlusFromMBPhi;
                            if (dauPdg == -321) ++nKMinusFromMBPhi;
                        }
                    }
                }
            }
        }

        if (!hasInjection)
        {
            ++numberOfEventsProcessedWithoutInjection;
        }
    }

    std::cout << "--------------------------------\n";
    std::cout << "Total Events Processed: " << tree->GetEntries() << "\n\n";

    std::cout << "--- 1. INJECTED RESONANCE (999999) ---\n";
    std::cout << "Total Injected Resonance 999999: " << nResonance999999 << "\n";
    std::cout << "Resonances not decayed: " << nNotDecayed999999 << "\n";
    std::cout << "Daughter Phi (333) produced from 999999: " << nPhiFromResonance << "\n";
    std::cout << "  -> Decayed to K+: " << nKPlusFromResonancePhi << "\n";
    std::cout << "  -> Decayed to K-: " << nKMinusFromResonancePhi << "\n\n";

    std::cout << "--- 2. DIRECTLY INJECTED PHI (333) ---\n";
    std::cout << "Total Directly Injected Phi (333): " << nDirectInjectedPhi << "\n";
    std::cout << "  -> Decayed to K+: " << nKPlusFromDirectPhi << "\n";
    std::cout << "  -> Decayed to K-: " << nKMinusFromDirectPhi << "\n\n";

    std::cout << "--- 3. MINIMUM BIAS PHI (333) ---\n";
    std::cout << "Total Minimum Bias Phi (333): " << nMBPhi << "\n";
    std::cout << "  -> Decayed to K+: " << nKPlusFromMBPhi << "\n";
    std::cout << "  -> Decayed to K-: " << nKMinusFromMBPhi << "\n";
    std::cout << "--------------------------------\n";
    std::cout << "Events processed without signal injection: " << numberOfEventsProcessedWithoutInjection << "\n";

    return 0;
}

void GeneratorLF_phiphi2()
{
    External();
}