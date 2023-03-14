int External()
{
    int checkPdgSignal = 4332;
    int checkPdgDecayPi = 211;
    int checkPdgDecayXi = 3312;
    int checkPdgDecayLambda = 3122;
    int checkPdgDecayP = 2212;
    std::string path{"o2sim_Kine.root"};
    std::cout << "Check for\nsignal PDG " << checkPdgSignal << "\ndecay PDG " << checkPdgDecayPi << " and " << checkPdgDecayPi << "\n";
    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree*)file.Get("o2sim");
    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nXi{}; //xi-
    int nAntiXi{}; //xi+
    int nPi{}; //pi+
    int nAntiPi{}; //pi-

    int nDauPairs{};
    int nDauPairsToBeDone{};

    int nSignal{};

    int nDecayOmegac{};
    int nDecayXi{};
    int nDecayLambda{};
    int nFullDecayChain{};

    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        for (auto& track : *tracks) {
            auto pdg = track.GetPdgCode();
            if (pdg == checkPdgDecayXi) {
                nXi++;
            } else if(pdg == -checkPdgDecayXi) {
                nAntiXi++;
            }else if(pdg == checkPdgDecayPi) {
                nPi++;
            }else if(pdg == -checkPdgDecayPi) {
                nAntiPi++;
            } else if (pdg == checkPdgSignal) {
                nSignal++;
                auto child0 = o2::mcutils::MCTrackNavigator::getDaughter0(track, *tracks);
                auto child1 = o2::mcutils::MCTrackNavigator::getDaughter1(track, *tracks);
                if (child0 != nullptr && child1 != nullptr) {
                    // check for parent-child relations
                    auto pdg0 = child0->GetPdgCode();
                    auto pdg1 = child1->GetPdgCode();
                    std::cout << "First and last children of parent " << checkPdgSignal << " are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n";
                    if ((std::abs(pdg0) == checkPdgDecayXi && std::abs(pdg1) == checkPdgDecayPi && pdg0>0 && pdg1>0) || (std::abs(pdg1) == checkPdgDecayXi && std::abs(pdg0) == checkPdgDecayPi && pdg0<0 && pdg1<0)) { //211 pi+ and 3312 xi- from MC numbering scheme
                        nDauPairs++;
                        nDecayOmegac++;
                        if (child0->getToBeDone() && child1->getToBeDone()) {
                            nDauPairsToBeDone++;
                        } 
                        auto cascade;
                        if(std::abs(pdg0) == checkPdgDecayXi) {
                            cascade = child0;
                        } else if (std::abs(pdg1) == checkPdgDecayXi) {
                            cascade = child1;
                        }
                        auto childCasc0 = o2::mcutils::MCTrackNavigator::getDaughter0(cascade, *tracks);
                        auto childCasc1 = o2::mcutils::MCTrackNavigator::getDaughter1(cascade, *tracks);
                        if (childCasc0 != nullptr && childCasc1 != nullptr) {
                            if ((std::abs(childCasc0->GetPdgCode()) == checkPdgDecayLambda && std::abs(childCasc1->GetPdgCode()) == checkPdgDecayPi) || (std::abs(childCasc1->GetPdgCode()) == checkPdgDecayLambda && std::abs(childCasc0->GetPdgCode()) == checkPdgDecayPi)) {
                                nDecayXi++;
                                auto lambda;
                                if(std::abs(childCasc0->GetPdgCode()) == checkPdgDecayLambda) {
                                    lambda = childCasc0;
                                } else if (std::abs(childCasc1->GetPdgCode()) == checkPdgDecayLambda) {
                                    lambda = childCasc1;
                                }
                                auto childLam0 = o2::mcutils::MCTrackNavigator::getDaughter0(lambda, *tracks);
                                auto childLam1 = o2::mcutils::MCTrackNavigator::getDaughter1(lambda, *tracks);
                                if (childLam0 != nullptr && childLam1 != nullptr) {
                                    if ((std::abs(childLam0->GetPdgCode()) == checkPdgDecayP && std::abs(childLam1->GetPdgCode()) == checkPdgDecayPi) || (std::abs(childLam1->GetPdgCode()) == checkPdgDecayP && std::abs(childLam0->GetPdgCode()) == checkPdgDecayPi)) {
                                        nDecayLambda++;
                                        nFullDecayChain++;
                                    }
                                }
                            }                   
                        }
                }
            }
        }
    }
    }
    std::cout << "#events: " << nEvents << "\n"
              << "#xi: " << nXi << "\n"
              << "#antixi: " << nAntiXi << "\n"
              << "#pi: " << nPi << "\n"
              << "#antipi: " << nAntiPi << "\n"
              << "#signal: " << nSignal << "\n"
              << "#Daughter pairs: " << nDauPairs << "\n"
              << "#Daughter pairs to be done: " << nDauPairsToBeDone << "\n"
              << "#Correct Omegac decays: " << nDecayOmegac << "\n"
              << "#Correct Xi decays: " << nDecayXi << "\n"
              << "#Correct Lambda decays: " << nDecayLambda << "\n"
              << "#Correct full decay chains: " << nFullDecayChain << "\n";


    if (nDauPairs == 0) {
        std::cerr << "Number of daughter pairs should be greater than 1.\n";
        return 1;
    }
    if (nDauPairs != nDauPairsToBeDone) {
        std::cerr << "The number of daughter pairs should be the same as the number of daughter pairs which should be transported.\n";
        return 1;
    }
    if (nSignal > nDauPairs) {
        std::cerr << "The number signals should be at least equaled to the number of the same as the number of daughter pairs.\n";
        return 1;
    }
    if (nXi == 0 && nAntiXi == 0) {
        std::cerr << "At least one among number of xi and number of anti-xi should be greater than 1.\n";
        return 1;
    }
    if (nPi == 0 && nAntiPi == 0) {
        std::cerr << "At least one among number of pi and number of anti-pi should be greater than 1.\n";
        return 1;
    }
    // check all the steps in the decay chain
    if (nDecayOmegac != nDecayXi) {
        std::cerr << "The Xi decay chain is not the expected one (Omegac -> Xi pi -> (Lambda pi) pi).\n";
        return 1;
    }
    if (nDecayOmegac != nDecayLambda) {
        std::cerr << "The Lambda decay chain is not the expected one (Omegac -> Xi pi -> (Lambda pi) pi -> ((p pi) pi) pi).\n";
        return 1;
    }
    if ((nDecayOmegac != nDecayXi) || (nDecayOmegac != nDecayLambda) || (nDecayXi != nDecayLambda) || (nDecayOmegac != nFullDecayChain)) {
        std::cerr << "The full OmegaC decay chain is not the expected one (Omegac -> Xi pi -> (Lambda pi) pi -> ((p pi) pi) pi).\n";
        return 1;
    }

    return 0;
}