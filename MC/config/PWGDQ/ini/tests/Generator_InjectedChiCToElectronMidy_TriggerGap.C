int External()
{
    int checkPdgSignal[] = {20443,445};
    int checkPdgDecay = 11;
    int checkPdgDecayOther = 22;
    int checkPdgDecayFirst = 443;
    std::string path{"o2sim_Kine.root"};
    std::cout << "Check for\nsignal PDG " << checkPdgSignal[0] << " and "<< checkPdgSignal[1]   << "\ndecay PDG " << checkPdgDecayOther << "  and" << checkPdgDecayFirst << "\n";
    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    int hasElectron=0;
    int hasPositron=0;

    auto tree = (TTree*)file.Get("o2sim");
    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nPhotons{};
    int nLeptons{};
    int nSignalJpsi{};	
    int nAntileptons{};
    int nLeptonPairsChild0{};
    int nLeptonPairsChild0ToBeDone{};
    int nLeptonPairsChild1{};
    int nLeptonPairsChild1ToBeDone{};
    int nGammaJpsiPairs{};
    int nGammaJpsiPairsToBeDone{};
    int nSignalChiC1{};
    int nSignalChiC2{};
    int nSignalChiC1WithinAcc{};
    int nSignalChiC2WithinAcc{};
    auto nEvents = tree->GetEntries();
    o2::steer::MCKinematicsReader mcreader("o2sim", o2::steer::MCKinematicsReader::Mode::kMCKine);
    Bool_t isInjected = kFALSE;

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
            } else if(pdg == checkPdgDecayFirst) {
                // count  J/psi
                nSignalJpsi++;
            } else if(pdg == checkPdgDecayOther) {
                // count photons
                nPhotons++;
            } else if (pdg == checkPdgSignal[0] || pdg == checkPdgSignal[1]) {
                if(idMoth < 0){
		// count signal PDG 
		pdg == checkPdgSignal[0] ? nSignalChiC1++ : nSignalChiC2++;
                // count signal PDG within acceptance 
		if(std::abs(rapidity) < 1.0) { pdg == checkPdgSignal[0] ? nSignalChiC1WithinAcc++ : nSignalChiC2WithinAcc++;}
		}
		auto child0 = o2::mcutils::MCTrackNavigator::getDaughter0(track, *tracks);
                auto child1 = o2::mcutils::MCTrackNavigator::getDaughter1(track, *tracks);
                if (child0 != nullptr && child1 != nullptr) {
                    // check for parent-child relations
                    auto pdg0 = child0->GetPdgCode();
                    auto pdg1 = child1->GetPdgCode();
//                    std::cout << "First and last children of parent " << checkPdgSignal << " are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n";
                    if ( (std::abs(pdg0) == checkPdgDecayFirst && std::abs(pdg1) == checkPdgDecayOther ) ||  
                         (std::abs(pdg0) == checkPdgDecayOther && std::abs(pdg1) == checkPdgDecayFirst )   ) {
                        nGammaJpsiPairs++;


                       hasElectron=0;
                       hasPositron=0;

                       if (child0->getToBeDone() == 0) {

		           auto grandChild0FromChild0 = &(*tracks).at(child0-> getFirstDaughterTrackId());
                           auto grandChild1FromChild0 = &(*tracks).at(child0-> getLastDaughterTrackId());

                           for(int ii = child0-> getFirstDaughterTrackId() ; ii< child0-> getLastDaughterTrackId()+1 ;ii++){
                             auto grandChildFromChild0 = &(*tracks).at(ii);    
                             if ( grandChildFromChild0->GetPdgCode() == -checkPdgDecay ){
                               hasElectron = 1;
	                       auto grandChild0FromChild0 = &(*tracks).at(ii);
                             }
                             if ( grandChildFromChild0->GetPdgCode() ==  checkPdgDecay ){
                               hasPositron = 1;
                               auto grandChild1FromChild0 = &(*tracks).at(ii);

                             }
                           }
	                   if (hasElectron && hasPositron) {
        	              nLeptonPairsChild0++;
                	      if (grandChild0FromChild0->getToBeDone() && grandChild1FromChild0->getToBeDone()) {
                                nLeptonPairsChild0ToBeDone++;
                              }	
                           }	
                        }

                        hasElectron=0;
                        hasPositron=0;
 
                        if (child1->getToBeDone() == 0) {
                           auto grandChild0FromChild1 = &(*tracks).at(child1-> getFirstDaughterTrackId());
                           auto grandChild1FromChild1 = &(*tracks).at(child1-> getLastDaughterTrackId());

                           for(int ii = child1-> getFirstDaughterTrackId() ; ii< child1-> getLastDaughterTrackId()+1 ;ii++){
                             auto grandChildFromChild1 = &(*tracks).at(ii);    
                             if ( grandChildFromChild1->GetPdgCode() == -checkPdgDecay ){
                               hasElectron = 1;
                               auto grandChild0FromChild1 = &(*tracks).at(ii);
                             }
                             if ( grandChildFromChild1->GetPdgCode() ==  checkPdgDecay ){
                               hasPositron = 1;
                               auto grandChild1FromChild1 = &(*tracks).at(ii);

                             }
                           }
                            if (hasElectron && hasPositron) {
                                nLeptonPairsChild1++;
                                if (grandChild0FromChild1->getToBeDone() && grandChild1FromChild1->getToBeDone()) {
                                    nLeptonPairsChild1ToBeDone++;
                                }       
                            }    
                        }
                    }
                }
            }
        }
    }
    nGammaJpsiPairsToBeDone = nLeptonPairsChild0ToBeDone + nLeptonPairsChild1ToBeDone;

    std::cout << "#events: " << nEvents << "\n"
              << "#leptons: " << nLeptons << "\n"
              << "#antileptons: " << nAntileptons << "\n"
              << "#signal photon " << nPhotons <<  "\n"
              << "#signal (prompt Jpsi): " << nSignalJpsi  << "\n"
              << "#signal (prompt ChiC1): " << nSignalChiC1 << "; within acceptance (|y| < 1): " << nSignalChiC1WithinAcc << "\n"
              << "#signal (prompt ChiC2): " << nSignalChiC2 << "; within acceptance (|y| < 1): " << nSignalChiC2WithinAcc << "\n"
              << "#GammaJpsi pairs: " << nGammaJpsiPairs << "\n"
              << "#GammaJpsi pairs to be  done: " << nGammaJpsiPairsToBeDone   << "\n"
              << "#lepton pairs to be done from child0: " << nLeptonPairsChild0 << " "   << nLeptonPairsChild0ToBeDone  << "\n"
              << "#lepton pairs to be done from Child 1: " << nLeptonPairsChild1 << " "   << nLeptonPairsChild1ToBeDone  << "\n";



    if (nGammaJpsiPairs == 0 || nPhotons == 0 || nSignalJpsi == 0) {
        std::cerr << "Number of photons, number of J/psi  as well as number of  Gamma-Jpsi  pairs should all be greater than 1.\n";
        return 1;
    }
    if (nLeptonPairsChild0 != nLeptonPairsChild0ToBeDone){
        std::cerr << "The number of gamma J/psi pairs should be the same as the number of Gamma Jpsi pairs which should be transported.\n";
        return 1;
    }

    if (nLeptonPairsChild1 != nLeptonPairsChild1ToBeDone){
        std::cerr << "The number of gamma J/psi pairs should be the same as the number of Gamma Jpsi pairs which should be transported.\n";
        return 1;
    }


    if (nGammaJpsiPairs < nGammaJpsiPairsToBeDone) {
        std::cerr << "The number of gamma J/psi pairs should be the same as the number of Gamma Jpsi pairs which should be transported.\n";
        return 1;
    }

    return 0;
}
