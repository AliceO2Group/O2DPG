int External() {
    std::string path{"o2sim_Kine.root"};

    int checkPdgQuark{5};
    float ratioTrigger = 1./5; // one event triggered out of 5

    std::vector<int> checkPdgHadron{411, 421, 431, 4122, 4132, 4232, 4332, 511, 521, 531, 5122};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{ // sorted pdg of daughters
        {411, {{-321, 211, 211}, {-313, 211}, {211, 311}, {211, 333}}}, // D+
        {421, {{-321, 211}, {-321, 111, 211}}}, // D0
        {431, {{211, 333}, {-313, 321}}}, // Ds+
        {4122, {{-313, 2212}, {-321, 2224}, {211, 102134}, {-321, 211, 2212}, {311, 2212}}}, // Lc+
        {4132, {{211, 3312}}}, // Xic0
        {4232, {{-313, 2212}, {-321, 3324}, {211, 211, 3312}, {-321, 211, 2212}}}, // Xic+
        {4332, {{211, 3334}}}, // Omegac+
        {511, {{-411, 211}, {-411, 321}}}, // B0
        {521, {{-421, 211}, {-421, 321}}}, // B+
        {531, {{-431, 211}, {-431, 321}}}, // Bs0
        {5122, {{4122, -211}, {4122, -321}}} // Lb0
    };

    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);
    o2::dataformats::MCEventHeader *eventHeader = nullptr;
    tree->SetBranchAddress("MCEventHeader.", &eventHeader);

    int nEventsMB{}, nEventsInj{};
    int nQuarks{}, nSignals{}, nSignalGoodDecay{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);

        // check subgenerator information
        if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
            bool isValid = false;
            int subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
            if (subGeneratorId == 0) {
                nEventsMB++;
            } else if (subGeneratorId == checkPdgQuark) {
                nEventsInj++;
            }
        }

        for (auto &track : *tracks) {
            auto pdg = track.GetPdgCode();
            if (std::abs(pdg) == checkPdgQuark) {
                nQuarks++;
                continue;
            }
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), std::abs(pdg)) != checkPdgHadron.end()) { // found signal
                nSignals++; // count signal PDG

                std::vector<int> pdgsDecay{};
                std::vector<int> pdgsDecayAntiPart{};
                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
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
    std::cout << "# MB events: " << nEventsMB << "\n";
    std::cout << Form("# events injected with %d quark pair: ", checkPdgQuark) << nEventsInj << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuark) << nQuarks << "\n";
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying in the correct channel: " << nSignalGoodDecay << "\n";

    if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 || nEventsMB > nEvents * (1 - ratioTrigger) * 1.05) { // we put some tolerance since the number of generated events is small
        std::cerr << "Number of generated MB events different than expected\n";
        return 1;
    }
    if (nEventsInj < nEvents * ratioTrigger * 0.95 || nEventsInj > nEvents * ratioTrigger * 1.05) {
        std::cerr << "Number of generated events injected with " << checkPdgQuark << " different than expected\n";
        return 1;
    }

    if (nQuarks < nEvents * ratioTrigger) { // we expect anyway more because the same quark is repeated several time, after each gluon radiation
        std::cerr << "Number of generated (anti)quarks " << checkPdgQuark << " lower than expected\n";
        return 1;
    }

    float fracForcedDecays = float(nSignalGoodDecay) / nSignals;
    if (fracForcedDecays < 0.85) { // we put some tolerance (e.g. due to oscillations which might change the final state)
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    return 0;
}
