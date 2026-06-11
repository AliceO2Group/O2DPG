int External() {
    std::string path{"~/test_evtgen/tf3/genevents_Kine.root"};//{"o2sim_Kine.root"};

    int checkPdgQuark{5};
    float ratioTrigger = 1./5; // one event triggered out of 5

    std::vector<int> checkPdgHadron{443, 511, 521, 531, 5122};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{ // sorted pdg of daughters
        {443, {{-11, 11}, {-13, 13}}}, // J/psi
        {511, {{313, 443}}}, // B0
        {521, {{321, 443}}}, // B+
        {531, {{333, 443}}}, // Bs0
        {5122, {{321, 443, 2212}}} // Lb0
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
    int nSignals{}, nSignalGoodDecay{};
    int nJPsiToEE{}, nJPsiToMuMu{};
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
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), std::abs(pdg)) != checkPdgHadron.end()) { // found signal
                nSignals++; // count signal PDG

                std::vector<int> pdgsDecay{};
                std::vector<int> pdgsDecayAntiPart{};
                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    if (pdg == 443 && pdgDau == 22) {
                        continue;
                    }
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
                        if (pdg == 443) {
                            if (decay == std::vector{-11, 11}) {
                                nJPsiToEE++;
                            } else if (decay == std::vector{-13, 13}) {
                                nJPsiToMuMu++;
                            }
                        }
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
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying in the correct channel: " << nSignalGoodDecay << "\n";
    std::cout <<"# J/Psi decaying to e+e-: " << nJPsiToEE << "\n";
    std::cout <<"# J/Psi decaying to mu+mu-: " << nJPsiToMuMu << "\n";

    if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 || nEventsMB > nEvents * (1 - ratioTrigger) * 1.05) { // we put some tolerance since the number of generated events is small
        std::cerr << "Number of generated MB events different than expected\n";
        return 1;
    }
    if (nEventsInj < nEvents * ratioTrigger * 0.95 || nEventsInj > nEvents * ratioTrigger * 1.05) {
        std::cerr << "Number of generated events injected with " << checkPdgQuark << " different than expected\n";
        return 1;
    }

    float fracForcedDecays = nSignals ? float(nSignalGoodDecay) / nSignals : 0.0f;
    float uncFracForcedDecays = nSignals ? std::sqrt(fracForcedDecays * (1 - fracForcedDecays) / nSignals) : 1.0f;
    if (1 - fracForcedDecays > 0.5 + uncFracForcedDecays) { // at least 50% in the main decay channels (we also have correlated backgrounds, mostly from other B decays)
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    return 0;
}
