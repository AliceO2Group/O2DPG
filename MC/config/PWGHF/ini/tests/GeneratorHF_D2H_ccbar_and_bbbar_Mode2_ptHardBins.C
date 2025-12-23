int External() {
    std::string path{"o2sim_Kine.root"};

    int checkPdgQuarkOne{4};
    int checkPdgQuarkTwo{5};
    float ratioTrigger = 1.; // each event triggered
    float averagePt = 0.;

    std::vector<int> checkPdgHadron{411, 421, 431, 4122, 4132, 4232, 4332};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{ // sorted pdg of daughters
        {411, {{-321, 211, 211}, {-313, 211}, {211, 311}, {211, 333}}}, // D+
        {421, {{-321, 211}, {-321, 111, 211}}}, // D0
        {431, {{211, 333}, {-313, 321}}}, // Ds+
        {4122, {{-313, 2212}, {-321, 2224}, {211, 102134}, {-321, 211, 2212}, {311, 2212}}}, // Lc+
        {4132, {{211, 3312}}}, // Xic0
        {4232, {{-313, 2212}, {-321, 3324}, {211, 211, 3312}, {-321, 211, 2212}}}, // Xic+
        {4332, {{211, 3334}}} // Omegac+
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

    int nEventsMB{}, nEventsInjOne{}, nEventsInjTwo{};
    int nQuarksOne{}, nQuarksTwo{}, nSignals{}, nSignalGoodDecay{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);

        // check subgenerator information
        if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
            bool isValid = false;
            int subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
            if (subGeneratorId == 0) {
                nEventsMB++;
            } else if (subGeneratorId == checkPdgQuarkOne) {
                nEventsInjOne++;
            } else if (subGeneratorId == checkPdgQuarkTwo) {
                nEventsInjTwo++;
            }
        }

        for (auto &track : *tracks) {
            auto pdg = track.GetPdgCode();
            if (std::abs(pdg) == checkPdgQuarkOne) {
                nQuarksOne++;
                continue;
            }
            if (std::abs(pdg) == checkPdgQuarkTwo) {
                nQuarksTwo++;
                continue;
            }
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), std::abs(pdg)) != checkPdgHadron.end()) { // found signal
                nSignals++; // count signal PDG
                averagePt += track.GetPt();

                std::vector<int> pdgsDecay{};
                std::vector<int> pdgsDecayAntiPart{};
                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    pdgsDecay.push_back(pdgDau);
                    if (pdgDau != 333  && pdgDau != 111) { // phi is antiparticle of itself
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

    averagePt /= nSignals; 

    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << "# MB events: " << nEventsMB << "\n";
    std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkOne) << nEventsInjOne << "\n";
    std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkTwo) << nEventsInjTwo << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuarkOne) << nQuarksOne << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuarkTwo) << nQuarksTwo << "\n";
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying in the correct channel: " << nSignalGoodDecay << "\n";
    std::cout <<"average pT of signal hadrons: " << averagePt << "\n";

    if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 || nEventsMB > nEvents * (1 - ratioTrigger) * 1.05) { // we put some tolerance since the number of generated events is small
        std::cerr << "Number of generated MB events different than expected\n";
        return 1;
    }
    if (nEventsInjOne < nEvents * ratioTrigger * 0.5 * 0.95 || nEventsInjOne > nEvents * ratioTrigger * 0.5 * 1.05) {
        std::cerr << "Number of generated events injected with " << checkPdgQuarkOne << " different than expected\n";
        return 1;
    }
    if (nEventsInjTwo < nEvents * ratioTrigger * 0.5 * 0.95 || nEventsInjTwo > nEvents * ratioTrigger * 0.5 * 1.05) {
        std::cerr << "Number of generated events injected with " << checkPdgQuarkTwo << " different than expected\n";
        return 1;
    }

    if (nQuarksOne < nEvents * ratioTrigger) { // we expect anyway more because the same quark is repeated several time, after each gluon radiation
        std::cerr << "Number of generated (anti)quarks " << checkPdgQuarkOne << " lower than expected\n";
        return 1;
    }
    if (nQuarksTwo < nEvents * ratioTrigger) { // we expect anyway more because the same quark is repeated several time, after each gluon radiation
        std::cerr << "Number of generated (anti)quarks " << checkPdgQuarkTwo << " lower than expected\n";
        return 1;
    }

    float fracForcedDecays = float(nSignalGoodDecay) / nSignals;
    if (fracForcedDecays < 0.9) { // we put some tolerance (e.g. due to oscillations which might change the final state)
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    if (averagePt < 6.5) { // by testing locally it should be around 8.5 GeV/c with pthard bin 20-200 (contrary to 2-2.5 GeV/c of SoftQCD)
        std::cerr << "Average pT of charmed hadrons " << averagePt << " lower than expected\n";
        return 1;
    }

    return 0;
}
