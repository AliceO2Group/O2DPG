int External()
{
    int checkPdgSignal = 4132;
    int checkPdgDecayPi = 211;
    int checkPdgDecayXi = 3312;
    int checkPdgQuark = 4;
    float ratioTrigger = 1./3; // one event triggered out of 3

    std::string path{"o2sim_Kine.root"};
    std::cout << "Check for\nsignal PDG " << checkPdgSignal << "\ndecay PDG " << checkPdgDecayXi << " and " << checkPdgDecayPi << "\n";
    TFile file(path.c_str(), "READ");
    if (file.IsZombie())
    {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nQuark{}; // charm quark
    int nXi{};     // xi-
    int nAntiXi{}; // xi+
    int nPi{};     // pi+
    int nAntiPi{}; // pi-

    int nDauPairs{};

    int nSignalTot{};
    int nSignalPart{};
    int nSignalAntiPart{};

    int nDecayXic{};
    int nFullDecayChain{};

    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++)
    {
        tree->GetEntry(i);
        for (auto &track : *tracks)
        {    
            auto pdg = track.GetPdgCode();
            if (std::abs(pdg) == checkPdgQuark) {
                nQuark++;
                continue;
            }
            if (pdg == checkPdgDecayXi)
            {
                nXi++;
            }
            else if (pdg == -checkPdgDecayXi)
            {
                nAntiXi++;
            }
            else if (pdg == checkPdgDecayPi)
            {
                nPi++;
            }
            else if (pdg == -checkPdgDecayPi)
            {
                nAntiPi++;
            }
            else if (std::abs(pdg) == checkPdgSignal)
            {
                nSignalTot++;

                if(pdg == checkPdgSignal){
                    nSignalPart++;
                } else if (pdg == -checkPdgSignal) {
                    nSignalAntiPart++;
                }

                auto child0 = o2::mcutils::MCTrackNavigator::getDaughter0(track, *tracks);
                auto child1 = o2::mcutils::MCTrackNavigator::getDaughter1(track, *tracks);
                if (child0 != nullptr && child1 != nullptr)
                {
                    nDauPairs++;

                    // check for parent-child relations
                    auto pdg0 = child0->GetPdgCode();
                    auto pdg1 = child1->GetPdgCode();
                    std::cout << "First and last children of parent " << pdg << " are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n";
                    if ((std::abs(pdg0) == checkPdgDecayXi && std::abs(pdg1) == checkPdgDecayPi) || (std::abs(pdg1) == checkPdgDecayXi && std::abs(pdg0) == checkPdgDecayPi))
                    { // 211 pi+ and 3312 xi- from MC numbering scheme
                        nDecayXic++;
                        // ------------- cascade is child0 -------------
                        if (std::abs(pdg0) == checkPdgDecayXi)
                        {
                            auto childCasc0 = o2::mcutils::MCTrackNavigator::getDaughter0(*child0, *tracks);
                            auto childCasc1 = o2::mcutils::MCTrackNavigator::getDaughter1(*child0, *tracks);
                            nFullDecayChain++;
                        }

                        else if (std::abs(pdg1) == checkPdgDecayXi)
                        { // ------------- cascade is child1 -------------
                            auto childCasc0 = o2::mcutils::MCTrackNavigator::getDaughter0(*child1, *tracks);
                            auto childCasc1 = o2::mcutils::MCTrackNavigator::getDaughter1(*child1, *tracks);
                            nFullDecayChain++;
                        }
                    }
                }
            }
        }
    }


    std::cout << "#events: " << nEvents << "\n"
              <<"#charm quark: " << nQuark << "\n"
              << "#xi: " << nXi << "\n"
              << "#antixi: " << nAntiXi << "\n"
              << "#pi: " << nPi << "\n"
              << "#antipi: " << nAntiPi << "\n"
              << "#signal tot: " << nSignalTot << "\n"
              << "#signal particles: " << nSignalPart << "\n"
              << "#signal anti-particles: " << nSignalAntiPart << "\n"
              << "#Daughter pairs: " << nDauPairs << "\n"
              << "#Correct Xic decays: " << nDecayXic << "\n"
              << "#Correct full decay chain: " << nFullDecayChain << "\n";

    if (nDauPairs == 0)
    {
        std::cerr << "Number of daughter pairs should be greater than 0.\n";
        return 1;
    }
    if (nSignalTot == 0)
    {
        std::cerr << "Number of Xic + Anti-Xic should be greater than 0.\n";
        return 1;
    }
    if (nXi == 0 && nAntiXi == 0)
    {
        std::cerr << "At least one among number of xi and number of anti-xi should be greater than 1.\n";
        return 1;
    }
    if (nPi == 0 && nAntiPi == 0)
    {
        std::cerr << "At least one among number of pi and number of anti-pi should be greater than 1.\n";
        return 1;
    }
    if (nDecayXic != nFullDecayChain)
    {
        std::cerr << "The full OmegaC decay chain is not the expected one (Xic -> Xi pi).\n";
        return 1;
    }
    if (nQuark < 2 * nEvents * ratioTrigger) // we expect anyway more because the same quark is repeated several time, after each gluon radiation
    {
        std::cerr << "Number of generated (anti)quarks " << checkPdgQuark << " lower than expected\n";
        return 1;
    }

    return 0;

}
