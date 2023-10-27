int External()
{
    int checkPdgSignal[] = {443,100443};
    int checkPdgDecay = 11;
    std::string path{"o2sim_Kine.root"};
    std::cout << "Check for\nsignal PDG " << checkPdgSignal << "\ndecay PDG " << checkPdgDecay << "\n";
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
    int nSignalPsi2S{};
    int nSignalJpsiWithinAcc{};
    int nSignalPsi2SWithinAcc{};
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
            } else if (pdg == checkPdgSignal[0] || pdg == checkPdgSignal[1]) {
                if(idMoth < 0){
		// count signal PDG 
		pdg == checkPdgSignal[0] ? nSignalJpsi++ : nSignalPsi2S++;
                // count signal PDG within acceptance 
		if(std::abs(rapidity) < 1.0) { pdg == checkPdgSignal[0] ? nSignalJpsiWithinAcc++ : nSignalPsi2SWithinAcc++;}
		}
		auto child0 = o2::mcutils::MCTrackNavigator::getDaughter0(track, *tracks);
                auto child1 = o2::mcutils::MCTrackNavigator::getDaughter1(track, *tracks);
                if (child0 != nullptr && child1 != nullptr) {
                    // check for parent-child relations
                    auto pdg0 = child0->GetPdgCode();
                    auto pdg1 = child1->GetPdgCode();
                    std::cout << "First and last children of parent " << checkPdgSignal << " are PDG0: " << pdg0 << " PDG1: " << pdg1 << "\n";
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
              << "#signal (prompt Jpsi): " << nSignalJpsi << "; within acceptance (|y| < 1): " << nSignalJpsiWithinAcc << "\n"
              << "#signal (prompt Psi(2S)): " << nSignalPsi2S << "; within acceptance (|y| < 1): " << nSignalPsi2SWithinAcc << "\n"
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
