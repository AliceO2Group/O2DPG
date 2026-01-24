int ExternalLc() {
    std::string path{"o2sim_Kine.root"};

    int checkPdgQuarkOne{4};  // c quark injection
    int checkPdgQuarkTwo{5};  // b quark injection
    float ratioTrigger = 1./5.; // one event triggered out of 5

    // PDG replacements: Λc(4122) -> resonances
    std::array<std::array<int, 2>, 4> pdgReplParticles = {
        std::array{4122, 34122},   // Λc -> Λc(2860)
        std::array{4122, 44122},   // Λc -> Λc(2880)
        std::array{4122, 54122},   // Λc -> Λc(2940)
        std::array{4122, 9422111}  // Λc -> Tc(3100)
    };

    // Counters for replacements
    std::array<std::array<int, 2>, 4> pdgReplPartCounters = { 
        std::array{0,0}, std::array{0,0}, std::array{0,0}, std::array{0,0} 
    };

    std::array<float, 4> freqRepl = {0.2, 0.2, 0.2, 0.2};
    std::map<int,int> sumOrigReplacedParticles = {{4122,0}};

    // Hadrons to check
    std::array<int, 5> checkPdgHadron{34122, 44122, 54122, 9422111, 5122};

    // Correct decays
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{
        {34122, {{421, 2212}}},    
        {44122, {{421, 2212}}},    
        {54122, {{421, 2212}}},    
        {9422111, {{413, 2212}}},  
        {5122, {{421, 2212, -211}, {41221, -211}, {34122, -211}, {44122, -211}, {54122, -211}}} 
    };

    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) { std::cerr << "Cannot open ROOT file " << path << "\n"; return 1; }

    auto tree = (TTree*)file.Get("o2sim");
    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);
    o2::dataformats::MCEventHeader* eventHeader = nullptr;
    tree->SetBranchAddress("MCEventHeader.", &eventHeader);

    int nEventsMB{}, nEventsInjOne{}, nEventsInjTwo{};
    int nSignals{}, nSignalGoodDecay{};
    auto nEvents = tree->GetEntries();

    std::map<int,int> signalHadronsPerType;
    std::map<int,int> signalGoodDecayPerType;
    for (auto pdg : checkPdgHadron) { signalHadronsPerType[pdg] = 0; signalGoodDecayPerType[pdg] = 0; }

    for (int i=0; i<nEvents; i++) {
        tree->GetEntry(i);

        int subGeneratorId{-1};
        if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
            bool isValid=false;
            subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
            if (subGeneratorId==0) nEventsMB++;
            else if (subGeneratorId==checkPdgQuarkOne) nEventsInjOne++;
            else if (subGeneratorId==checkPdgQuarkTwo) nEventsInjTwo++;
        }

        for (auto& track : *tracks) {
            int pdg = track.GetPdgCode();
            int absPdg = std::abs(pdg);

            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), absPdg) != checkPdgHadron.end()) {
                nSignals++;
                signalHadronsPerType[absPdg]++;

                if (subGeneratorId==checkPdgQuarkOne) {
                    for (int iRepl=0; iRepl<3; ++iRepl) {
                        if (absPdg == pdgReplParticles[iRepl][0]) { pdgReplPartCounters[iRepl][0]++; sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]++; }
                        else if (absPdg == pdgReplParticles[iRepl][1]) { pdgReplPartCounters[iRepl][1]++; sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]++; }
                    }
                }

                std::vector<int> pdgsDecay;
                std::vector<int> pdgsDecayAnti;
                if (track.getFirstDaughterTrackId()>=0) {
                    for (int j=track.getFirstDaughterTrackId(); j<=track.getLastDaughterTrackId(); ++j) {
                        int pdgDau = tracks->at(j).GetPdgCode();
                        pdgsDecay.push_back(pdgDau);
                        pdgsDecayAnti.push_back((pdgDau==111||pdgDau==333)? pdgDau : -pdgDau);
                    }
                }

                std::sort(pdgsDecay.begin(), pdgsDecay.end());
                std::sort(pdgsDecayAnti.begin(), pdgsDecayAnti.end());

                bool matchedDecay = false;
                for (auto& decay : checkHadronDecays[absPdg]) {
                    std::vector<int> decayCopy = decay;
                    std::sort(decayCopy.begin(), decayCopy.end());
                    if (pdgsDecay == decayCopy || pdgsDecayAnti == decayCopy) {
                        matchedDecay = true;
                        nSignalGoodDecay++;
                        signalGoodDecayPerType[absPdg]++;
                        break;
                    }
                }

                // Print daughters
                std::cout << "Particle " << absPdg << " daughters: ";
                for (auto d : pdgsDecay) std::cout << d << " ";
                if (matchedDecay) std::cout << "(matches expected decay)";
                else std::cout << "(does NOT match expected decay)";
                std::cout << "\n";
            }
        }
    }

    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << "# MB events: " << nEventsMB << "\n";
    std::cout << "# events injected with " << checkPdgQuarkOne << ": " << nEventsInjOne << "\n";
    std::cout << "# events injected with " << checkPdgQuarkTwo << ": " << nEventsInjTwo << "\n";
    std::cout << "# signal hadrons: " << nSignals << "\n";
    std::cout << "# signal hadrons decaying in correct channels: " << nSignalGoodDecay << "\n";

    for (auto& [pdg, count] : signalHadronsPerType) {
        int good = signalGoodDecayPerType[pdg];
        float frac = count>0 ? float(good)/count : 0.;
        std::cout << "Particle " << pdg << ": " << count << " signals, " << good << " good decays, fraction: " << frac << "\n";
    }

    // Optional: sanity checks...
    return 0;
}
