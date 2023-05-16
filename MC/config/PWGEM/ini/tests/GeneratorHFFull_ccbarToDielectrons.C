int External()
{
    	
    int checkPdgDecay = -11;
    std::string path{"o2sim_Kine.root"};
    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree*)file.Get("o2sim");
    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nLeptonsInAcceptance{};
    int nLeptons{};
    int nAntileptons{};
    int nAntileptonsInAcceptance{};
    int nLeptonsToBeDone{};
    int nAntileptonsToBeDone{};
    int nSignalPairs{};
    int nLeptonPairs{};
    int nLeptonPairsToBeDone{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
	int nElectrons = 0;
	int nPositrons = 0;
	int nElectronsToBeDone = 0;
        int nPositronsToBeDone = 0;
	int nOpenCharmPos = 0;
	int nOpenCharmNeg = 0;
        for (auto& track : *tracks) {
            auto pdg = track.GetPdgCode();
	    auto y = track.GetRapidity();
            if (pdg == checkPdgDecay) {
                 int igmother = track.getMotherTrackId();
                 if (igmother > 0) {
                     auto gmTrack = (*tracks)[igmother];
                     int gmpdg = gmTrack.GetPdgCode();
		     if (int(std::abs(gmpdg)/100.) == 4 || int(std::abs(gmpdg)/1000.) == 4) {
                         nLeptons++;
			 nElectrons++;
			 if (-1 < y && y < 1) nLeptonsInAcceptance++;
			 if (track.getToBeDone()) {
			     nLeptonsToBeDone++;
			     nElectronsToBeDone++;
			 }
		    }
	         }    
            } else if (pdg == -checkPdgDecay) {
                int igmother = track.getMotherTrackId();
                if (igmother > 0) {
                    auto gmTrack = (*tracks)[igmother];
                    int gmpdg = gmTrack.GetPdgCode();
                    if (int(TMath::Abs(gmpdg)/100.) == 4 || int(TMath::Abs(gmpdg)/1000.) == 4) {
                        nAntileptons++;
			nPositrons++;
			if (-1 < y && y < 1) nAntileptonsInAcceptance++;
			if (track.getToBeDone()) {
			    nAntileptonsToBeDone++;
			    nPositronsToBeDone++;
			}
                    }
                 }
            } else if (pdg == 411 || pdg == 421 || pdg == 431 || pdg == 4122 || pdg == 4132 || pdg == 4232 || pdg == 4332) {
		nOpenCharmPos++;
	    }  else if (pdg == -411 || pdg == -421 || pdg == -431 || pdg == -4122 || pdg == -4132 || pdg == -4232 || pdg == -4332) {
                nOpenCharmNeg++;
	    }
        }
	if (nOpenCharmPos > 0 && nOpenCharmNeg > 0) nSignalPairs++;
	if (nElectrons > 0 && nPositrons > 0) nLeptonPairs++;
	if (nElectronsToBeDone > 0 && nPositronsToBeDone > 0) nLeptonPairsToBeDone++;
    }
    std::cout << "#events: " << nEvents << "\n"
	      << "#leptons: " << nLeptons << "\n"
              << "#leptons in acceptance: " << nLeptonsInAcceptance << "\n"
              << "#antileptons: " << nAntileptons << "\n"
	      << "#antileptons in acceptance: " << nAntileptonsInAcceptance << "\n"
              << "#leptons to be done: " << nLeptonsToBeDone << "\n"
              << "#antileptons to be done: " << nAntileptonsToBeDone << "\n"
              << "#signal pairs: " << nSignalPairs << "\n"
	      << "#lepton pairs: " << nLeptonPairs << "\n"
              << "#lepton pairs to be done: " << nLeptonPairsToBeDone << "\n";
    int nTotalLeptonsInAcceptance = nLeptonsInAcceptance + nAntileptonsInAcceptance;
    if (nLeptons == 0 && nAntileptons == 0) {
        std::cerr << "Number of leptons, number of anti-leptons should all be greater than 1.\n";
        return 1;
    }
    if (nLeptonPairs < nSignalPairs) {
        std::cerr << "Number of lepton pairs should be at least equaled to the number of open charm hadron pairs\n";
        return 1;
    }
    if (nLeptonPairs != nLeptonPairsToBeDone) {
        std::cerr << "The number of lepton pairs should be the same as the number of lepton pairs which should be transported.\n";
        return 1;
    }
    if (nLeptons != nLeptonsToBeDone) {
        std::cerr << "The number of leptons should be the same as the number of leptons which should be transported.\n";
        return 1;
    }
    if (nTotalLeptonsInAcceptance <  nEvents) {
        std::cerr << "The number of leptons in acceptance should be at least equaled to the number of events.\n";
        return 1;
    }
    if (nLeptons != nLeptonsInAcceptance) {
        std::cerr << "The number of leptons in acceptance should be the same as the number of leptons.\n";
        return 1;
    }
    if (nAntileptons != nAntileptonsInAcceptance) {
        std::cerr << "The number of anti-leptons in acceptance should be the same as the number of anti-leptons.\n";
        return 1;
    }

    return 0;
}
