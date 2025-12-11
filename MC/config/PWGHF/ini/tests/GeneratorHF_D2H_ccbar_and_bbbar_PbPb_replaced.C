int External() {
    std::string path{"o2sim_Kine.root"};
    //std::string path{"tf1/sgn_Kine.root"};

    // Particle replacement configuration: {original, replacement}, frequencies
    std::array<std::array<int, 2>, 3> pdgReplParticles = {
        std::array{423, 4132},   // D*0 -> Xic0
        std::array{423, 4232},   // D*0 -> Xic+
        std::array{4212, 4332}   // Sigmac+ -> Omegac0
    };
    std::array<std::array<int, 2>, 3> pdgReplPartCounters = {
        std::array{0, 0}, 
        std::array{0, 0}, 
        std::array{0, 0}
    };
    std::array<float, 3> freqRepl = {0.5, 0.5, 1.0};
    std::map<int, int> sumOrigReplacedParticles = {{423, 0}, {4212, 0}};

    // Signal hadrons to check (only final charm baryons after replacement)
    std::array<int, 4> checkPdgHadron{4122, 4132, 4232, 4332};
    
    // Expected decay channels - will be sorted automatically
    // Define both particle and antiparticle versions
    std::map<int, std::vector<std::vector<int>>> checkHadronDecaysRaw{
        // Λc+ decays (from cfg: 4122:addChannel + resonance decays)
        {4122, {
            {2212, 311}, {-2212, -311},                           // p K0s
            {2212, -321, 211}, {-2212, 321, -211},                // p K- π+ (non-resonant)
            {2212, 313}, {-2212, -313},                           // p K*0 (not decayed)
            {2212, 321, 211}, {-2212, -321, -211},                // p K*0 -> p (K- π+) [K*0 decayed]
            {2224, -321}, {-2224, 321},                           // Delta++ K- (not decayed)
            {2212, 211, -321}, {-2212, -211, 321},                // Delta++ K- -> (p π+) K- [Delta decayed]
            {102134, 211}, {-102134, -211},                       // Lambda(1520) π+ (not decayed)
            {2212, 321, 211}, {-2212, -321, -211},                // Lambda(1520) π+ -> (p K-) π+ [Lambda* decayed]
            {2212, -321, 211, 111}, {-2212, 321, -211, 111},      // p K- π+ π0
            {2212, -211, 211}, {-2212, 211, -211},                // p π- π+ (cfg line 61: 2212 -211 211)
            {2212, 333}, {-2212, 333},                            // p φ (not decayed)
            {2212, 321, -321}, {-2212, -321, 321}                 // p φ -> p (K+ K-) [φ decayed]
        }},
        // Ξc0 decays (from cfg: 4132:onIfMatch)
        {4132, {
            {3312, 211}, {-3312, -211},                           // Ξ- π+
            {3334, 321}, {-3334, -321}                            // Ω- K+
        }},
        // Ξc+ decays (from cfg: 4232:onIfMatch + resonance decays)
        {4232, {
            {2212, -321, 211}, {-2212, 321, -211},                // p K- π+
            {2212, -313}, {-2212, 313},                           // p K̄*0 (not decayed)
            {2212, -321, 211}, {-2212, 321, -211},                // p K̄*0 -> p (K+ π-) [K*0 decayed]
            {2212, 333}, {-2212, 333},                            // p φ (not decayed)
            {2212, 321, -321}, {-2212, -321, 321},                // p φ -> p (K+ K-) [φ decayed]
            {3222, -211, 211}, {-3222, 211, -211},                // Σ+ π- π+
            {3324, 211}, {-3324, -211},                           // Ξ*0 π+
            {3312, 211, 211}, {-3312, -211, -211}                 // Ξ- π+ π+
        }},
        // Ωc0 decays (from cfg: 4332:onIfMatch)
        {4332, {
            {3334, 211}, {-3334, -211},                           // Ω- π+
            {3312, 211}, {-3312, -211},                           // Ξ- π+
            {3334, 321}, {-3334, -321}                            // Ω- K+
        }}
    };
    
    // Sort all decay channels
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays;
    for (auto &[pdg, decays] : checkHadronDecaysRaw) {
        for (auto decay : decays) {
            std::sort(decay.begin(), decay.end());
            checkHadronDecays[pdg].push_back(decay);
        }
    }

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
    std::map<int, int> failedDecayCount{{4122, 0}, {4132, 0}, {4232, 0}, {4332, 0}};
    std::map<int, std::set<std::vector<int>>> unknownDecays;
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++)
    {
        tree->GetEntry(i);
        for (auto &track : *tracks)
        {
            auto pdg = track.GetPdgCode();
            auto absPdg = std::abs(pdg);
            
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), absPdg) != checkPdgHadron.end())
            {
                nSignals++; // count signal PDG

                // Count replacement particles (single-match per track)
                int matchedIdx = -1;
                bool matchedIsReplacement = false;
                for (int iRepl{0}; iRepl < 3; ++iRepl) {
                    if (absPdg == pdgReplParticles[iRepl][0]) {
                        matchedIdx = iRepl;
                        matchedIsReplacement = false;
                        break;
                    }
                    if (absPdg == pdgReplParticles[iRepl][1]) {
                        matchedIdx = iRepl;
                        matchedIsReplacement = true;
                        break;
                    }
                }
                if (matchedIdx >= 0) {
                    if (matchedIsReplacement) {
                        pdgReplPartCounters[matchedIdx][1]++;
                    } else {
                        pdgReplPartCounters[matchedIdx][0]++;
                    }
                    // Count the original-particle population once for this matched group
                    sumOrigReplacedParticles[pdgReplParticles[matchedIdx][0]]++;
                }

                // Collect decay products
                std::vector<int> pdgsDecay{};
                if (track.getFirstDaughterTrackId() >= 0 && track.getLastDaughterTrackId() >= 0) {
                    for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                        auto pdgDau = tracks->at(j).GetPdgCode();
                        pdgsDecay.push_back(pdgDau);
                    }
                }

                std::sort(pdgsDecay.begin(), pdgsDecay.end());

                // Check if decay matches expected channels
                bool foundMatch = false;
                for (auto &decay : checkHadronDecays[absPdg]) {
                    if (pdgsDecay == decay) {
                        nSignalGoodDecay++;
                        foundMatch = true;
                        break;
                    }
                }
                
                // Record failed decays for debugging
                if (!foundMatch && pdgsDecay.size() > 0) {
                    failedDecayCount[absPdg]++;
                    unknownDecays[absPdg].insert(pdgsDecay);
                }
            }
        }
    }

    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << "# signal charm baryons: " << nSignals << "\n";
    std::cout << "# signal charm baryons decaying in the correct channel: " << nSignalGoodDecay << "\n";
    
    // Print failed decay statistics
    std::cout << "\nFailed decay counts:\n";
    for (auto &[pdg, count] : failedDecayCount) {
        if (count > 0) {
            std::cout << "PDG " << pdg << ": " << count << " failed decays\n";
            std::cout << "  Unknown decay channels (first 5):\n";
            int printed = 0;
            for (auto &decay : unknownDecays[pdg]) {
                if (printed++ >= 5) break;
                std::cout << "    [";
                for (size_t i = 0; i < decay.size(); ++i) {
                    std::cout << decay[i];
                    if (i < decay.size()-1) std::cout << ", ";
                }
                std::cout << "]\n";
            }
        }
    }
    std::cout << "\n";
    
    std::cout << "# D*0 (original): " << pdgReplPartCounters[0][0] << "\n";
    std::cout << "# Xic0 (replaced from D*0): " << pdgReplPartCounters[0][1] << "\n";
    std::cout << "# Xic+ (replaced from D*0): " << pdgReplPartCounters[1][1] << "\n";
    std::cout << "# Sigmac+ (original): " << pdgReplPartCounters[2][0] << "\n";
    std::cout << "# Omegac0 (replaced from Sigmac+): " << pdgReplPartCounters[2][1] << "\n";

    // Check forced decay fraction
    float fracForcedDecays = nSignals ? float(nSignalGoodDecay) / nSignals : 0.0f;
    std::cout << "# fraction of signals decaying into the correct channel: " << fracForcedDecays
              << " (" << fracForcedDecays * 100.0f << "%)\n";
    if (fracForcedDecays < 0.9f) { // 90% threshold with tolerance
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    // Check particle replacement ratios (2-sigma statistical compatibility)
    for (int iRepl{0}; iRepl < 3; ++iRepl) {
        if (sumOrigReplacedParticles[pdgReplParticles[iRepl][0]] == 0) {
            continue; // Skip if no original particles found
        }
        
        float expectedCount = freqRepl[iRepl] * sumOrigReplacedParticles[pdgReplParticles[iRepl][0]];
        float sigma = std::sqrt(freqRepl[iRepl] * sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]);
        
        if (std::abs(pdgReplPartCounters[iRepl][1] - expectedCount) > 2 * sigma) {
            float fracMeas = float(pdgReplPartCounters[iRepl][1]) / sumOrigReplacedParticles[pdgReplParticles[iRepl][0]];
            std::cerr << "Fraction of replaced " << pdgReplParticles[iRepl][0] 
                      << " into " << pdgReplParticles[iRepl][1] 
                      << " is " << fracMeas << " (expected " << freqRepl[iRepl] << ")\n";
            return 1;
        }
    }

    return 0;
}
