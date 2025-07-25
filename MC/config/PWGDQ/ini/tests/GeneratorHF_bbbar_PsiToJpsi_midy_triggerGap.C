int External()
{
    int checkPdgSignal[] = {100443};
    int checkPdgDecay[] = {443, 211, -211}; 
    int leptonPdg = 11;
    Double_t rapidityWindow = 1.0;
    std::string path{"o2sim_Kine.root"};
    std::cout << "Check for\nsignal PDG " << checkPdgSignal[0] << "\n decay PDG " << checkPdgDecay[0] << ", " << checkPdgDecay[1] << ", " << checkPdgDecay[2] << "\n";
    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }
    auto tree = (TTree*)file.Get("o2sim");
    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

     int nLeptons{};
    int nAntileptons{};
    int nLeptonPairs{};
    int nLeptonPairsToBeDone{};
    int nSignalJpsi{};
    int nSignalPionsPos{};
    int nSignalPionsNeg{};
    int nSignalPsi2S{};
    int nSignalJpsiWithinAcc{};
    int nSignalPionsPosWithinAcc{};
    int nSignalPionsNegWithinAcc{};
    auto nEvents = tree->GetEntries();
    o2::steer::MCKinematicsReader mcreader("o2sim", o2::steer::MCKinematicsReader::Mode::kMCKine);
    Int_t  bpdgs[] = {511, 521, 531, 5112, 5122, 5232, 5132};
    Int_t sizePdg = sizeof(bpdgs)/sizeof(Int_t);
    Bool_t hasBeautyMoth = kFALSE;

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        for (auto& track : *tracks) {
            auto pdg = track.GetPdgCode();
            auto rapidity =  track.GetRapidity();
            auto idMoth = track.getMotherTrackId();
            int idJpsi = -1; int IdChild0 = -1; int IdChild1 = -1;
            if (pdg == leptonPdg) {
                // count leptons
                nLeptons++;
            } else if(pdg == -leptonPdg) {
                // count anti-leptons
                nAntileptons++;
            } else if (pdg == checkPdgSignal[0]) {
                hasBeautyMoth  = kFALSE;
                if(idMoth){ //  check beauty mother
                    auto tdM = mcreader.getTrack(i, idMoth);
                    for(int i=0; i<sizePdg; i++){ if (TMath::Abs(tdM->GetPdgCode()) == bpdgs[i] ) hasBeautyMoth = kTRUE; }
                }
                if(hasBeautyMoth){
                    nSignalPsi2S++;
                    for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                        auto pdgDau = tracks->at(j).GetPdgCode();
                        if(TMath::Abs(pdgDau) == checkPdgDecay[0] ) { nSignalJpsi++; if( std::abs(track.GetRapidity()) < rapidityWindow) nSignalJpsiWithinAcc++; idJpsi = j; }
                        if(pdgDau == checkPdgDecay[1] ) { nSignalPionsPos++; if( std::abs(track.GetRapidity()) < rapidityWindow) nSignalPionsPosWithinAcc++; }
                        if(pdgDau == checkPdgDecay[2] ) { nSignalPionsNeg++; if( std::abs(track.GetRapidity()) < rapidityWindow) nSignalPionsNegWithinAcc++; }
                    }

                    auto trackJpsi = tracks->at(idJpsi);
                    for (int j{trackJpsi.getFirstDaughterTrackId()}; j <= trackJpsi.getLastDaughterTrackId(); ++j) {
                        auto pdgDau = tracks->at(j).GetPdgCode();
                        if(pdgDau == leptonPdg ) IdChild0 = j;
                        if(pdgDau == -leptonPdg ) IdChild1 = j;
                    }
                    auto child0 = tracks->at(IdChild0);
                    auto child1 = tracks->at(IdChild1);
                    // check for parent-child relations
                    auto pdg0 = child0.GetPdgCode();
                    auto pdg1 = child1.GetPdgCode();
                    if (std::abs(pdg0) == leptonPdg && std::abs(pdg1) == leptonPdg && pdg0 == -pdg1) {
                        nLeptonPairs++;
                        if (child0.getToBeDone() && child1.getToBeDone()) {
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
              << "#signal (jpsi <- psi2S): " << nSignalJpsi << "; within acceptance (|y| < " << rapidityWindow << "): " << nSignalJpsiWithinAcc << "\n"
              << "#signal (pi+ <- psi2S): " << nSignalPionsPos << "; within acceptance (|y| < " << rapidityWindow << "): " << nSignalPionsPosWithinAcc << "\n"
              << "#signal (pi- <- psi2S): " << nSignalPionsNeg << "; within acceptance (|y| < " << rapidityWindow << "): " << nSignalPionsNegWithinAcc << "\n"
              << "#lepton pairs: " << nLeptonPairs << "\n"
              << "#lepton pairs to be done: " << nLeptonPairs << "\n";


    if (nLeptonPairs == 0 || nLeptons == 0 || nAntileptons == 0) {
        std::cerr << "Number of leptons, number of anti-leptons as well as number of lepton pairs should all be greater than 1.\n";
        return 1;
    }
    if (nLeptonPairs != nLeptonPairsToBeDone) {
        std::cerr << "The number of lepton pairs should be the same as the number of lepton pairs which should be transported.\n";
        return 1;
    }

    return 0;
}