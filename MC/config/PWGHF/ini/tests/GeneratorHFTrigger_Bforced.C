int External()
{
    std::string path{"o2sim_Kine.root"};
    int checkPdgQuark{5};
    float ratioTrigger = 1./3; // one event triggered out of 3
    std::vector<int> checkPdgHadron{411, 421, 431, 443, 4122, 4132, 4232, 4332, 511, 521, 531, 5122};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{
        {411, {{-321, 211, 211}, {-313, 211}, {211, 311}, {211, 333}}}, // D+
        {421, {{-321, 211}, {-321, 111, 211}}}, // D0
        {431, {{211, 333}}}, // Ds+
        {443, {{-11, 11}}}, // Jpsi
        {4122, {{-313, 2212}, {-321, 2224}, {211, 102134}, {-321, 211, 2212}}}, // Lc+
        {4132, {{211, 3312}}}, // Xic0
        {4232, {{-313, 2212}, {-321, 3324}, {211, 211, 3312}, {-321, 211, 2212}}}, // Xic+
        {4332, {{211, 3334}}}, // Omegac+
        {511, {{-411, 211}, {-413, 211}, {-211, 431}}}, // B0
        {521, {{-421, 211}}}, // B+
        {531, {{-431, 211}}}, // Bs
        {5122, {{-211, 4122}}} // Lb
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
                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j)
                {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    pdgsDecay.push_back(pdgDau);
                }

                for (auto &decay : checkHadronDecays[std::abs(pdg)]) {

                    if (decay.size() == pdgsDecay.size()) { // first we check that the number of daughters is correct
                        int nGoodPart{0}, nGoodAntiPart{0};
                        for (auto &dauPdg : pdgsDecay) { // then we check that all the daughters have the correct pdg
                            for (auto &dauPdgExpected : decay) {
                                if (dauPdg == dauPdgExpected) {
                                    nGoodPart++;
                                } else if (dauPdg == -dauPdgExpected) {
                                    nGoodAntiPart++;
                                }
                            }
                        }
                        if (nGoodPart == decay.size() || nGoodAntiPart == decay.size()) {
                            nSignalGoodDecay++;
                            break;
                        }
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


    if (nQuarks < 0.95 * (2 * nEvents * ratioTrigger)) // we put some tolerance
    {
        std::cerr << "Number of generated (anti)quarks " << checkPdgQuark << " lower than expected\n";
        return 1;
    }

    float fracForcedDecays = nSignals ? float(nSignalGoodDecay) / nSignals : 0.0f;
    float uncFracForcedDecays = nSignals ? std::sqrt(fracForcedDecays * (1 - fracForcedDecays) / nSignals) / nSignals : 1.0f;
    if (std::abs(fracForcedDecays - 0.75) > uncFracForcedDecays) // we put some tolerance (e.g. due to oscillations which might change the final state)
    {
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    return 0;
}
