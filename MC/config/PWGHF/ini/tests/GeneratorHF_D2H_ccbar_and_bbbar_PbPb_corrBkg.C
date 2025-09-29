int External() {
    std::string path{"o2sim_Kine.root"};
    //std::string path{"tf1/sgn_1_Kine.root"};

    int checkPdgQuarkOne{4};
    int checkPdgQuarkTwo{5};
    float ratioTrigger = 1.; // one event triggered out of 1

    std::vector<int> checkPdgHadron{411, 421, 431, 4122, 4232};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{ // sorted pdg of daughters
        {421, {
			{-321, 211},              // D0 -> K-, pi+
			{-321, 211, 111},         // D0 -> K-, pi+, pi0
			{213, -321},              // D0 -> rho(770)+, K-
			{-313, 111},              // D0 -> Kbar^*(892)0, pi0
			{-323, 211},              // D0 -> K^*(892)-, pi+
			{-211, 211},              // D0 -> pi-, pi+
			{213, -211},              // D0 -> rho(770)+, pi-
			{-211, 211, 111},         // D0 -> pi-, pi+, pi0
			{-321, 321},              // D0 -> K-, K+
		}},

		{411, {
			{-321, 211, 211},         // D+ -> K-, pi+, pi+
			{-10311, 211},            // D+ -> Kbar0^*(1430)0, pi+
			{-313, 211},              // D+ -> Kbar^*(892)0, pi+
			{-321, 211, 211, 111},    // D+ -> K-, pi+, pi+, pi0
			{333, 211},               // D+ -> phi(1020)0, pi+
			{-313, 321},              // D+ -> Kbar^*(892)0, K+
			{-10311, 321},            // D+ -> Kbar0^*(1430)0, K+
			{-321, 321, 211},         // D+ -> K-, K+, pi+
			{113, 211},               // D+ -> rho(770)0, pi+
			{225, 211},               // D+ -> f2(1270)0, pi+
			{-211, 211, 211},         // D+ -> pi-, pi+, pi+
		}},

		{431, {
			{333, 211},               // Ds+ -> phi(1020)0, pi+
			{-313, 321},              // Ds+ -> Kbar^*(892)0, K+
			{333, 213},               // Ds+ -> phi(1020)0, rho(770)+
			{113, 211},               // Ds+ -> rho(770)0, pi+
			{225, 211},               // Ds+ -> f2(1270)0, pi+
			{-211, 211, 211},         // Ds+ -> pi-, pi+, pi+
			{313, 211},               // Ds+ -> K^*(892)0, pi+
			{10221, 321},             // Ds+ -> f0(1370)0, K+
			{113, 321},               // Ds+ -> rho(770)0, K+
			{-211, 321, 211},         // Ds+ -> pi-, K+, pi+
			{221, 211},               // Ds+ -> eta, pi+
		}},

		{4122, {
			{2212, -321, 211},        // Lambdac+ -> p, K-, pi+
			{2212, -313},             // Lambdac+ -> p, Kbar^*(892)0
			{2224, -321},             // Lambdac+ -> Delta(1232)++, K-
			{102134, 211},            // Lambdac+ -> 102134, pi+
			{2212, 311},              // Lambdac+ -> p, K0
			{2212, -321, 211, 111},   // Lambdac+ -> p, K-, pi+, pi0
			{2212, -211, 211},        // Lambdac+ -> p, pi-, pi+
			{2212, 333},              // Lambdac+ -> p, phi(1020)0
		}},

		{4232, {
			{2212, -321, 211},        // Xic+ -> p, K-, pi+
			{2212, -313},             // Xic+ -> p, Kbar^*(892)0
			{3312, 211, 211},         // Xic+ -> Xi-, pi+, pi+
			{2212, 333},              // Xic+ -> p, phi(1020)0
			{3222, -211, 211},        // Xic+ -> Sigma+, pi-, pi+
			{3324, 211},              // Xic+ -> Xi(1530)0, pi+
		}},
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
        //if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
        //    bool isValid = false;
        //    int subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
        //    if (subGeneratorId == 0) {
        //        nEventsMB++;
        //    } else if (subGeneratorId == checkPdgQuarkOne) {
        //        nEventsInjOne++;
        //    } else if (subGeneratorId == checkPdgQuarkTwo) {
        //        nEventsInjTwo++;
        //    }
        //}

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
                    if (pdgDau != 333 && pdgDau != 111 && pdgDau != 221 && pdgDau != 113 && pdgDau != 225) { // phi is antiparticle of itself
                        pdgsDecayAntiPart.push_back(-pdgDau);
                    } else {
                        pdgsDecayAntiPart.push_back(pdgDau);
                    }
                }

                std::sort(pdgsDecay.begin(), pdgsDecay.end());
                std::sort(pdgsDecayAntiPart.begin(), pdgsDecayAntiPart.end());

                for (auto &decay : checkHadronDecays[std::abs(pdg)]) {
                    std::sort(decay.begin(), decay.end());
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
    //std::cout << "# MB events: " << nEventsMB << "\n";
    //std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkOne) << nEventsInjOne << "\n";
    //std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkTwo) << nEventsInjTwo << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuarkOne) << nQuarksOne << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuarkTwo) << nQuarksTwo << "\n";
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying in the correct channel: " << nSignalGoodDecay << "\n";

    //if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 || nEventsMB > nEvents * (1 - ratioTrigger) * 1.05) { // we put some tolerance since the number of generated events is small
    //    std::cerr << "Number of generated MB events different than expected\n";
    //    return 1;
    //}
    //if (nEventsInjOne < nEvents * ratioTrigger * 0.5 * 0.95 || nEventsInjOne > nEvents * ratioTrigger * 0.5 * 1.05) {
    //    std::cerr << "Number of generated events injected with " << checkPdgQuarkOne << " different than expected\n";
    //    return 1;
    //}
    //if (nEventsInjTwo < nEvents * ratioTrigger * 0.5 * 0.95 || nEventsInjTwo > nEvents * ratioTrigger * 0.5 * 1.05) {
    //    std::cerr << "Number of generated events injected with " << checkPdgQuarkTwo << " different than expected\n";
    //    return 1;
    //}

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
