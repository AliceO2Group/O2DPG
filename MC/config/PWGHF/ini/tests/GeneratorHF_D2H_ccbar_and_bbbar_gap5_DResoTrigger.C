int External() {
    std::string path{"o2sim_Kine.root"};

    int checkPdgQuarkOne{4};
    int checkPdgQuarkTwo{5};
    float ratioTrigger = 1./5.; // one event triggered out of 5
    std::array<std::array<int, 2>, 6> pdgReplParticles = {std::array{10433, 30433}, std::array{10433, 437}, std::array{435, 4325}, std::array{435, 4326}, std::array{425, 4315}, std::array{425, 4316}};
    std::array<std::array<int, 2>, 6> pdgReplPartCounters = {std::array{0, 0}, std::array{0, 0}, std::array{0, 0}, std::array{0, 0}, std::array{0, 0}, std::array{0, 0}};
    std::array<float, 6> freqRepl = {0.1, 0.1, 0.1, 0.1, 0.5, 0.5};
    std::map<int, int> sumOrigReplacedParticles = {{10433, 0}, {435, 0}, {425, 0}};

    std::array<int, 11> checkPdgHadron{411, 421, 10433, 30433, 435, 437, 4325, 4326, 4315, 4316, 531};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{ // sorted pdg of daughters
        {411, {{-321, 211, 211}, {-313, 211}, {211, 311}, {211, 333}}}, // D+
        {421, {{-321, 211}, {-321, 211, 111}}}, // D0
        {435, {{311, 413}, {311, 411}}}, // Ds2*(2573)
        {10433, {{311, 413}}}, // Ds1(2536)
        {30433, {{311, 413}}}, // Ds1*(2700)
        {437, {{311, 413}}}, // Ds3*(2860)
        {4325, {{411, 3122}}}, // Xic(3055)+
        {4326, {{411, 3122}}}, // Xic(3080)+
        {4315, {{421, 3122}}}, // Xic(3055)+
        {4316, {{421, 3122}}}, // Xic(3080)+
        {531, {{-435, -11, 12}, {-10433, -11, 12}, {-435, -13, 14}, {-10433, -13, 14}, {-435, -15, 16}, {-10433, -15, 16}, {-435, 211}}}// Bs0
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
    int nSignals{}, nSignalGoodDecay{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);

        // check subgenerator information
        int subGeneratorId{-1};
        if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
            bool isValid = false;
            subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
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
            auto absPdg = std::abs(pdg);
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), absPdg) != checkPdgHadron.end()) { // found signal
                nSignals++; // count signal PDG

                if (subGeneratorId == checkPdgQuarkOne) { // replacement only for prompt
                    for (int iRepl{0}; iRepl<6; ++iRepl) {
                        if (absPdg == pdgReplParticles[iRepl][0]) {
                            pdgReplPartCounters[iRepl][0]++;
                            sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]++;
                        } else if (absPdg == pdgReplParticles[iRepl][1]) {
                            pdgReplPartCounters[iRepl][1]++;
                            sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]++;
                        }
                    }
                }

                std::vector<int> pdgsDecay{};
                std::vector<int> pdgsDecayAntiPart{};
                if (track.getFirstDaughterTrackId() >= 0 && track.getLastDaughterTrackId() >= 0) {
                    for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                        auto pdgDau = tracks->at(j).GetPdgCode();
                        pdgsDecay.push_back(pdgDau);
                        if (pdgDau != 333) { // phi is antiparticle of itself
                            pdgsDecayAntiPart.push_back(-pdgDau);
                        } else {
                            pdgsDecayAntiPart.push_back(pdgDau);
                        }
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

    float fracForcedDecays = float(nSignalGoodDecay) / nSignals;
    if (fracForcedDecays < 0.9) { // we put some tolerance (e.g. due to oscillations which might change the final state)
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    for (int iRepl{0}; iRepl<6; ++iRepl) {
        if (std::abs(pdgReplPartCounters[iRepl][1] - freqRepl[iRepl] * sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]) > 2 * std::sqrt(freqRepl[iRepl] * sumOrigReplacedParticles[pdgReplParticles[iRepl][0]])) { // 2 sigma compatibility
            float fracMeas = 0.;
            if (sumOrigReplacedParticles[pdgReplParticles[iRepl][0]] > 0.) {
                fracMeas = float(pdgReplPartCounters[iRepl][1]) / sumOrigReplacedParticles[pdgReplParticles[iRepl][0]];
            } 
            std::cerr << "Fraction of replaced " << pdgReplParticles[iRepl][0] << " into " << pdgReplParticles[iRepl][1] << " is " << fracMeas <<" (expected "<< freqRepl[iRepl] << ")\n";
            return 1;    
        }
    }

    return 0;
}
