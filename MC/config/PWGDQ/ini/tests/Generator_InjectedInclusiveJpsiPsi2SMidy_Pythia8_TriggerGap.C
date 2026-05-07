int External()
{
    int checkPdgSignal[] = {443};
    int checkPdgDecay = 11;
    int kaonPdg = 321;
    std::string path{"o2sim_Kine.root"};
    std::cout << "Check for\nsignal PDG " << checkPdgSignal[0] << "\ndecay PDG " << checkPdgDecay << "\n";
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
    int nSignalKaons{};
    int nSignalPsi2S{};
    int nSignalJpsiWithinAcc{};
    int nSignalKaonsWithinAcc{};
    auto nEvents = tree->GetEntries();
    o2::steer::MCKinematicsReader mcreader("o2sim", o2::steer::MCKinematicsReader::Mode::kMCKine);
    Int_t  bpdgs[] = {521};
    Int_t sizePdg = sizeof(bpdgs)/sizeof(Int_t);
    Bool_t hasBeautyMoth = kFALSE;

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        for (auto& track : *tracks) {
            auto pdg = track.GetPdgCode();
	    auto rapidity =  track.GetRapidity();
	    auto idMoth = track.getMotherTrackId();
            if (pdg == checkPdgDecay) {
                // count leptons
                nLeptons++;
            } else if(pdg == -checkPdgDecay) {
                // count anti-leptons
                nAntileptons++;
            } else if (pdg == checkPdgSignal[0]) {
		// check if mothers are beauty hadrons
		hasBeautyMoth  = kFALSE;
                if(idMoth){ //  check beauty mother
                auto tdM = mcreader.getTrack(i, idMoth);
                for(int i=0; i<sizePdg; i++){ if (TMath::Abs(tdM->GetPdgCode()) == bpdgs[i] ) hasBeautyMoth = kTRUE; }
		// check that it has 2 daughters, Jpsi + K
		auto child0b = o2::mcutils::MCTrackNavigator::getDaughter0(*tdM, *tracks);
                auto child1b = o2::mcutils::MCTrackNavigator::getDaughter1(*tdM, *tracks);
                if (child0b != nullptr && child1b != nullptr) {
		auto pdg0b = child0b->GetPdgCode();
                auto pdg1b = child1b->GetPdgCode();
                std::cout << "First and last children of parent B+ " << tdM->GetPdgCode() << " are PDG0: " << pdg0b << " PDG1: " << pdg1b << "\n";
                if(TMath::Abs(pdg0b) == kaonPdg ) { nSignalKaons++; if( std::abs(track.GetRapidity()) < 1.5) nSignalKaonsWithinAcc++; }
                if(TMath::Abs(pdg1b) == kaonPdg ) { nSignalKaons++; if( std::abs(track.GetRapidity()) < 1.5) nSignalKaonsWithinAcc++; }
		}	
                }
                if(hasBeautyMoth){
		// count signal PDG 
		pdg == checkPdgSignal[0] ? nSignalJpsi++ : nSignalPsi2S++;
                // count signal PDG within acceptance 
		if( (std::abs(rapidity) < 1.5) && pdg == checkPdgSignal[0] )  nSignalJpsiWithinAcc++;
		}
		auto child0 = o2::mcutils::MCTrackNavigator::getDaughter0(track, *tracks);
                auto child1 = o2::mcutils::MCTrackNavigator::getDaughter1(track, *tracks);
                if (child0 != nullptr && child1 != nullptr) {
                    // check for parent-child relations
                    auto pdg0 = child0->GetPdgCode();
                    auto pdg1 = child1->GetPdgCode();
                    std::cout << "First and last children of parent " << checkPdgSignal[0] << " are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n"; 
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
              << "#signal (jpsi <- B+): " << nSignalJpsi << "; within acceptance (|y| < 1.5): " << nSignalJpsiWithinAcc << "\n"
              << "#signal (K+ <- B+): " << nSignalKaons << "; within acceptance (|y| < 1.5): " << nSignalKaonsWithinAcc << "\n"
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
