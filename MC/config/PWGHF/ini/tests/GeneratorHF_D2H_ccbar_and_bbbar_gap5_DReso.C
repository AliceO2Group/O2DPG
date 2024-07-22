int External() {
    std::string path{"/home/luca/alice/Ds_reso/MCReso/07_22_16-59-12/tf1/genevents_Kine.root"};

    int checkPdgQuarkOne{4};
    int checkPdgQuarkTwo{5};
    float ratioTrigger = 1./5.; // one event triggered out of 5

    std::vector<int> checkPdgHadron{411, 415, 421, 425, 431, 435, 511, 521, 531, 4122, 10411, 10421, 10433, 20423, 20433};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{ // sorted pdg of daughters
        {411, {{-321, 211, 211}, {-313, 211}, {211, 311}, {211, 333}}}, // D+
        {415, {{211, 421}}}, // D2*(2460)+
        {421, {{-321, 211}, {-321, 111, 211}}}, // D0
        {425, {{-211, 413},{-211, 411}}}, // D2*(2460)0
        {431, {{211, 333}, {-313, 321}}}, // Ds+
        {425, {{311, 413}, {311, 411}, {321,421}}}, // Ds2*(2573)
        {511, {{-415, -11, 12}, {-10411, -11, 12}, {-415, -13, 14}, {-10411, -13, 14}, {-415, -15, 16}, {-10411, -15, 16},
               {-10411, 211}, {-10421, 211}, {-415, 433}, { -415, 431}, {-415, 211}, {-415, 213} }}, // B0
        {521, {{-20423, -11, 12}, {-425, -11, 12}, {-10421, -11, 12}, {-20423, -13, 14}, {-425, -13, 14}, {-10421, -13, 14},
               {-20423, -15, 16}, {-425, -15, 16}, {-10421, -15, 16}, {-20423, 211}, {-20423, 213}, {-20423, 431}, {-20423, 433}, 
               {-425, 211}, {-425, 213}, {-425, 431}, {-425, 433}}}, // B+
        {531, {{-435, -11, 12}, {-10433, -11, 12}, {-435, -13, 14}, {-10433, -13, 14}, {-435, -15, 16}, {-10433, -15, 16},
               {-435, 211}, {-20433, 211}, {-20433, 213}}},// Bs0
        {4122, {{-313, 2212}, {-321, 2224}, {211, 3124}, {-321, 211, 2212}, {311, 2212}}}, // Lc+
        {10411, {{211, 421}}}, // D0*+
        {10421, {{-211, 411}}}, // D0*0
        {10433, {{311, 413}}}, // Ds1(2536)
        {20423, {{-211, 413}}}, // D1(2430)0
        {20433, {{22, 431}, {-211, 211, 431} }} // Ds1 (2460)
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
    std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkOne) << nEventsInjOne << "\n";
    std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkTwo) << nEventsInjTwo << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuarkOne) << nQuarksOne << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuarkTwo) << nQuarksTwo << "\n";
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying in the correct channel: " << nSignalGoodDecay << "\n";

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

    return 0;
}
