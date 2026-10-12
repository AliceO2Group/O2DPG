int External()
{
    std::string path{"o2sim_Kine.root"};
    std::vector<int> checkPdgHadron{521};
    std::vector<int> nucleiDauPdg{1000010020};

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
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), std::abs(pdg)) != checkPdgHadron.end())
            {
                if(std::abs(track.GetRapidity()) > 1.5) continue;
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
    std::cout << "# signal hadrons: " << nSignals << "\n";
    std::cout << "# signal hadrons decaying into nuclei: " << nSignalGoodDecay << "\n";

    return 0;
}