int External()
{
    std::string path{"o2sim_Kine.root"};
    int checkPdgQuark{4};
    float ratioTrigger = 1./3; // one event triggered out of 3
    std::vector<int> checkPdgHadron{411, 421, 431, 443, 4122, 4132, 4232, 4332};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{ // sorted pdg of daughters
        {411, {{-321, 211, 211}, {-313, 211}, {211, 311}, {211, 333}}}, // D+
        {421, {{-321, 211}, {-321, 111, 211}}}, // D0
        {431, {{211, 333}}}, // Ds+
        {443, {{-11, 11}}}, // Jpsi
        {4122, {{-313, 2212}, {-321, 2224}, {211, 102134}, {-321, 211, 2212}}}, // Lc+
        {4132, {{211, 3312}}}, // Xic0
        {4232, {{-313, 2212}, {-321, 3324}, {211, 211, 3312}, {-321, 211, 2212}}}, // Xic+
        {4332, {{211, 3334}}} // Omegac+
    };

    TFile file(path.c_str(), "READ");
    if (file.IsZombie())
    {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nQuarks{}, nSignals{}, nSignalGoodDecay{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++)
    {
        tree->GetEntry(i);
        for (auto &track : *tracks)
        {
            auto pdg = track.GetPdgCode();
            if (std::abs(pdg) == checkPdgQuark) {
                nQuarks++;
                continue;
            }
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), std::abs(pdg)) != checkPdgHadron.end()) // found signal
            {
                // count signal PDG
                nSignals++;

                std::vector<int> pdgsDecay{};
                std::vector<int> pdgsDecayAntiPart{};
                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j)
                {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    pdgsDecay.push_back(pdgDau);
                    if (pdgDau != 333) { // phi is antiparticle of itself
                        pdgsDecayAntiPart.push_back(-pdgDau);
                    } else {
                        pdgsDecayAntiPart.push_back(pdgDau);
                    }
                }

                std::sort(pdgsDecay.begin(), pdgsDecay.end());
                std::sort(pdgsDecayAntiPart.begin(), pdgsDecayAntiPart.end());

                for (auto &decay : checkHadronDecays[std::abs(pdg)]) {
                    if (pdgsDecay == decay || pdgsDecayAntiPart == decay) {
                        nSignalGoodDecay++;
                        break;
                    }
                }
            }
        }
    }
    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuark) << nQuarks << "\n";
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying in the correct channel: " << nSignalGoodDecay << "\n";


    if (nQuarks < 2 * nEvents * ratioTrigger) // we expect anyway more because the same quark is repeated several time, after each gluon radiation
    {
        std::cerr << "Number of generated (anti)quarks " << checkPdgQuark << " lower than expected\n";
        return 1;
    }

    float fracForcedDecays = float(nSignalGoodDecay) / nSignals;
    if (fracForcedDecays < 0.85) // we put some tolerance (e.g. due to oscillations which might change the final state)
    {
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    return 0;
}
