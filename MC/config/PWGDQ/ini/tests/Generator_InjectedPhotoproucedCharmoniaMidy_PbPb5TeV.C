int External() {
    std::string path{"o2sim_Kine.root"};
    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }
    auto tree = (TTree *)file.Get("o2sim");
    if (!tree)
    {
        std::cerr << "Cannot find tree o2sim in file " << path << "\n";
        return 1;
    }
    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int checkPdgSignal[2] = {443, 100443};
    int checkPdgDecay = 11;
    double rapiditymin = -1.5; double rapiditymax = 1.5;

    int nLeptons{};
    int nAntileptons{};
    int nLeptonPairs{};
    int nPrimaryLepton{};
    int nPrimaryAntilepton{};
    int nLeptonPairsToBeDone{};
    int nSignalJpsi{};
    int nSignalPsi2S{};
    int nPions{};
    int nPhotonsFromPsi{};
    int nPhotonsFromJPsi{};
    int nSignalJpsiWithinAcc{};
    int nSignalPsi2SWithinAcc{};

    auto nEvents = tree->GetEntries();
    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        for (auto& track : *tracks) {
            auto pdg = track.GetPdgCode();
            auto rapidity = track.GetRapidity();
            auto idMoth = track.getMotherTrackId();
            if (pdg == checkPdgDecay) {
                // count leptons
                nLeptons++;
                if (idMoth == -1) nPrimaryLepton++;
            } else if (pdg == -checkPdgDecay) {
                // count anti-leptons
                nAntileptons++;
                if (idMoth == -1) nPrimaryAntilepton++;
            } else if (pdg == checkPdgSignal[0] || pdg == checkPdgSignal[1]) {
                if (idMoth < 0) {
                    // count signal PDG
                    pdg == checkPdgSignal[0] ? nSignalJpsi++ : nSignalPsi2S++;
                    // count signal PDG within acceptance
                    if (rapidity > rapiditymin && rapidity < rapiditymax) {
                        pdg == checkPdgSignal[0] ? nSignalJpsiWithinAcc++ : nSignalPsi2SWithinAcc++;
                    }
                }
                int child0Id = track.getFirstDaughterTrackId();
                int child1Id = track.getLastDaughterTrackId();
                for (int iDaugh = child0Id; iDaugh <= child1Id; iDaugh++) {
                    auto daugh = tracks->at(iDaugh);
                    if (daugh.GetPdgCode() == 22) {
                        if (pdg == checkPdgSignal[0]) {
                            nPhotonsFromJPsi++;
                        } else if (pdg == checkPdgSignal[1]) {
                            nPhotonsFromPsi++;
                        }
                    }
                    if (TMath::Abs(daugh.GetPdgCode()) == 211) nPions++;
                }
                auto child0 = o2::mcutils::MCTrackNavigator::getDaughter0(track, *tracks);
                auto child1 = o2::mcutils::MCTrackNavigator::getDaughter1(track, *tracks);
                if (child0 != nullptr && child1 != nullptr) {
                    // check for parent-child relations
                    auto pdg0 = child0->GetPdgCode();
                    auto pdg1 = child1->GetPdgCode();
                    // std::cout << "First and last children of parent " << checkPdgSignal << " are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n";
                    if (pdg == checkPdgSignal[0]) std::cout << "First and last children of parent Jpsi are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n";
                    if (pdg == checkPdgSignal[1]) std::cout << "First and last children of parent Psi(2S) are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n";
                    if (std::abs(pdg0) == checkPdgDecay && std::abs(pdg1) == checkPdgDecay && pdg0 == -pdg1) {
                        nLeptonPairs++;
                        if (child0->getToBeDone() && child1->getToBeDone()) {
                            nLeptonPairsToBeDone++;
                        }
                    }
                }
            }
        }
    }

    std::cout << "#events: " << nEvents << "\n"
              << "#leptons: " << nLeptons << "\n"
              << "#antileptons: " << nAntileptons << "\n"
              << "#primary leptons: " << nPrimaryLepton << "\n"
              << "#primary antileptons: " << nPrimaryAntilepton << "\n"
              << "#signal (prompt Jpsi): " << nSignalJpsi << "; within acceptance " << rapiditymin << " < y < " << rapiditymax << " : " << nSignalJpsiWithinAcc << "\n"
              << "#signal (prompt Psi(2S)): " << nSignalPsi2S << "; within acceptance " << rapiditymin << " < y < " << rapiditymax << " : " << nSignalPsi2SWithinAcc << "\n"
              << "#photons from Jpsi: " << nPhotonsFromJPsi  <<" #photons from Psi(2S): "<< nPhotonsFromPsi<<"\n"
              << "#pions from Psi(2S): "<< nPions<<"\n"
              << "#lepton pairs: " << nLeptonPairs  <<" #lepton pairs to be done: "<< nLeptonPairsToBeDone<<"\n";
    
    return 0;
}