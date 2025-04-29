int External()
{
    std::string path{"o2sim_Kine.root"};
    std::vector<int> checkPdgHadron{5122};                 // Lambda_b
    std::vector<int> nucleiDauPdg{1000020030, 1000010030}; // 3He, 3H

    TFile file(path.c_str(), "READ");
    if (file.IsZombie())
    {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nSignals{}, nSignalGoodDecay{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++)
    {
        tree->GetEntry(i);
        for (auto &track : *tracks)
        {
            auto pdg = track.GetPdgCode();
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), std::abs(pdg)) != checkPdgHadron.end()) // found signal
            {
                // count signal PDG
                if(std::abs(track.GetRapidity()) > 1.5) continue; // skip if outside rapidity window
                nSignals++;
                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j)
                {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    if (std::find(nucleiDauPdg.begin(), nucleiDauPdg.end(), std::abs(pdgDau)) != nucleiDauPdg.end())
                    {
                        nSignalGoodDecay++;
                    }
                }
            }
        }
    }
    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying into nuclei: " << nSignalGoodDecay << "\n";

    float fracForcedDecays = float(nSignalGoodDecay) / nSignals;
    if (fracForcedDecays < 0.8) // we put some tolerance (lambdaB in MB events do not coalesce)
    {
        std::cerr << "Fraction of signals decaying into nuclei: " << fracForcedDecays << ", lower than expected\n";
        return 1;
    }

    return 0;
}
