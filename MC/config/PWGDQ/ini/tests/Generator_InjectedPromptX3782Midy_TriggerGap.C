int External()
{
    int checkPdgSignal[] = {9920443}; // pdg code X3872
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
    int nSignalX3872{};
    int nSignalPionsPos{};
    int nSignalPionsNeg{};
    int nSignalPsi2S{};
    int nSignalX3872WithinAcc{};
    int nSignalPionsPosWithinAcc{};
    int nSignalPionsNegWithinAcc{};
    auto nEvents = tree->GetEntries();
    o2::steer::MCKinematicsReader mcreader("o2sim", o2::steer::MCKinematicsReader::Mode::kMCKine);
    Bool_t hasPsi2SMoth = kFALSE;

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        for (auto& track : *tracks) {
            auto pdg = track.GetPdgCode();
	    auto rapidity =  track.GetRapidity();
	    auto idMoth = track.getMotherTrackId();
	    int idX3872 = -1; int IdChild0 = -1; int IdChild1 = -1;
            if (pdg == leptonPdg) {
                // count leptons
                nLeptons++;
            } else if(pdg == -leptonPdg) {
                // count anti-leptons
                nAntileptons++;
            } else if (pdg == checkPdgSignal[0]) {
		// check daughters
                  std::cout << "Signal PDG: " << pdg << "\n";
                  for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                  auto pdgDau = tracks->at(j).GetPdgCode();
                  std::cout << "Daughter " << j << " is: " << pdgDau << "\n";
                    if(TMath::Abs(pdgDau) == checkPdgDecay[0] ) { nSignalX3872++; if( std::abs(track.GetRapidity()) < rapidityWindow) nSignalX3872WithinAcc++; idX3872 = j; }
                    if(pdgDau == checkPdgDecay[1] ) { nSignalPionsPos++; if( std::abs(track.GetRapidity()) < rapidityWindow) nSignalPionsPosWithinAcc++; }
                    if(pdgDau == checkPdgDecay[2] ) { nSignalPionsNeg++; if( std::abs(track.GetRapidity()) < rapidityWindow) nSignalPionsNegWithinAcc++; }
		  }
                
		  auto trackX3872 = tracks->at(idX3872);
		  for (int j{trackX3872.getFirstDaughterTrackId()}; j <= trackX3872.getLastDaughterTrackId(); ++j) {
                  auto pdgDau = tracks->at(j).GetPdgCode();
		   if(pdgDau == leptonPdg ) IdChild0 = j;
		   if(pdgDau == -leptonPdg ) IdChild1 = j;
		  }
         	auto child0 = tracks->at(IdChild0);
         	auto child1 = tracks->at(IdChild1);
                    // check for parent-child relations
                    auto pdg0 = child0.GetPdgCode();
                    auto pdg1 = child1.GetPdgCode();
                    std::cout << "Lepton daughter particles of mother  " << trackX3872.GetPdgCode() << " are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n"; 
                    if (std::abs(pdg0) == leptonPdg && std::abs(pdg1) == leptonPdg && pdg0 == -pdg1) {
                        nLeptonPairs++;
                        if (child0.getToBeDone() && child1.getToBeDone()) {
                            nLeptonPairsToBeDone++;
                        }
                    }
                //} 
            }
        }
    }
    std::cout << "#events: " << nEvents << "\n"
              << "#leptons: " << nLeptons << "\n"
              << "#antileptons: " << nAntileptons << "\n"
              << "#signal (jpsi <- X3872): " << nSignalX3872 << "; within acceptance (|y| < " << rapidityWindow << "): " << nSignalX3872WithinAcc << "\n"
              << "#signal (pi+ <- X3872): " << nSignalPionsPos << "; within acceptance (|y| < " << rapidityWindow << "): " << nSignalPionsPosWithinAcc << "\n"
              << "#signal (pi- <- X3872): " << nSignalPionsNeg << "; within acceptance (|y| < " << rapidityWindow << "): " << nSignalPionsNegWithinAcc << "\n"
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
