int External()
{
    int checkPdgDecay = 13;
    double yMin = -4.3;
    double yMax = -2.3;
    double ptMin = 0.0;
    double ptMax = 999.;

    std::string path{"o2sim_Kine.root"};
    std::cout << "Check for primary muons, PDG +-" << checkPdgDecay << ", " << yMin << " < y < " << yMax << ", " << ptMin << " < pt < " << ptMax << " GeV/c\n";

    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree*)file.Get("o2sim");
    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nMuons{};
    int nAntiMuons{};
    int nOutsideY{};
    int nOutsidePt{};
    int nNonPrimary{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        for (auto& track : *tracks) {
            auto pdg = track.GetPdgCode();
            auto rapidity =  track.GetRapidity();
            auto pt = track.GetPt();
	        auto idMoth = track.getMotherTrackId();
            if (std::abs(pdg) != checkPdgDecay) {
                continue;
            }
            if (pdg == checkPdgDecay) {
                nMuons++; //counts muons
            } else {
                nAntiMuons++; //counts anti-muons
            }
            if (idMoth >= 0) {
                nNonPrimary++; //counts non-primary muons (those with a mother track)
            }

            if (rapidity < yMin || rapidity > yMax) {
                nOutsideY++;
            }
            if (pt < ptMin || pt > ptMax) {
                nOutsidePt++;
            }
        }
    }

    std::cout << "#events: " << nEvents << "\n"
              << "#mu-: " << nMuons << "\n"
              << "#mu+: " << nAntiMuons << "\n"
              << "#non-primary muons: " << nNonPrimary << "\n"
              << "#muons outside y-range: " << nOutsideY << "\n"
              << "#muons outside pt-range: " << nOutsidePt << "\n";

    if (nMuons == 0 || nAntiMuons == 0) {
        std::cerr << "Expected both mu- and mu+, found nMuons=" << nMuons << " nAntiMuons=" << nAntiMuons << "\n";
        return 1;
    }
    if (nNonPrimary != 0) {
        std::cerr << "All generated muons should be primaries (no mother track).\n";
        return 1;
    }
    if (nOutsideY != 0 || nOutsidePt != 0) {
        std::cerr << "Some muons were generated outside the configured (y, pt) window.\n";
        return 1;
    }

    return 0;
}
