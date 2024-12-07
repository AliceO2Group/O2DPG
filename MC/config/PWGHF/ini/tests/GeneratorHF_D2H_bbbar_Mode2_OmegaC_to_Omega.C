int External() {
    std::string path{"o2sim_Kine.root"};

    int checkPdgQuarkOne = 5;

    int checkPdgHadron{4332};
    int checkHadronDecays{3334};

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

    int nEventsInj{};
    int nQuarks{}, nSignals{}, nSignalGoodDecay{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);

        // check subgenerator information
        if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
            bool isValid = false;
            int subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
            if (subGeneratorId == checkPdgQuark) {
                nEventsInj++;
            }
        }

        for (auto &track : *tracks) {
            auto pdg = track.GetPdgCode();
            if (std::abs(pdg) == checkPdgQuark) {
                nQuarks++;
                continue;
            }
            if (std::abs(pdg) == checkPdgHadron) { // found signal
                nSignals++; // count signal PDG

                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    if (std::abs(pdgDau) == checkHadronDecays) {
                        nSignalGoodDecay;
                        break;
                    }
                }
            }
        }
    }

    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << Form("# events injected with %d quark pair: ", checkPdgQuark) << nEventsInj << "\n";
    std::cout << Form("# %d (anti)quarks: ", checkPdgQuark) << nQuarks << "\n";
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying in the correct channel: " << nSignalGoodDecay << "\n";

    if (nEventsInj < nEvents) {
        std::cerr << "Number of generated events with triggered events different than expected\n";
        return 1;
    }

    if (nQuarks < nEvents) { // we expect anyway more because the same quark is repeated several time, after each gluon radiation
        std::cerr << "Number of generated (anti)quarks " << checkPdgQuark << " lower than expected\n";
        return 1;
    }

    if (nSignals < nEvents) {
        std::cerr << "Number of generated signals lower than expected\n";
        return 1;
    }

    float fracForcedDecays = float(nSignalGoodDecay) / nSignals;
    if (fracForcedDecays < 0.9) { // we put some tolerance (it should not happen, but to be conservative)
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    return 0;
}
