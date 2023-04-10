int External()
{
    	
    std::string path{"o2sim_Kine.root"};
    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree*)file.Get("o2sim");
    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nElectrons = 0;
    int nPositrons = 0;
    int nPions = 0;
    int nEtas = 0;
    int nEtaPrimes = 0;
    int nRhos = 0;
    int nPhis = 0;
    int nOmegas = 0;
    int nJPsis = 0;
    int nPhotons = 0;
    int nElectronsFromPion = 0;
    int nElectronsFromEta = 0;
    int nElectronsFromEtaPrime = 0;
    int nElectronsFromOmega = 0;
    int nElectronsFromRho = 0;
    int nElectronsFromPhi = 0;
    int nElectronsFromJPsi = 0;
    int nLeptonsToBeDone = 0;
    auto nEvents = tree->GetEntries();
    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        for (auto& track : *tracks) {
            bool hasMother = track.getMotherTrackId()>-1;
            auto pdg = track.GetPdgCode();
            switch (pdg){
                case 11:
                    nElectrons++;
                    if (track.getToBeDone()){
                        nLeptonsToBeDone++;
                    }
                    break;
                case -11:
                    nPositrons++;
                    if (track.getToBeDone()){
                        nLeptonsToBeDone++;
                    }
                    break;
                case 111:
                    if (!hasMother)
                        nPions++;
                    break;
                case 221:
                    if (!hasMother)
                        nEtas++;
                    break;
                case 331:
                    if (!hasMother)
                        nEtaPrimes++;
                  break;
                case 113:
                    if (!hasMother)
                        nRhos++;
                  break;
                case 223:
                    if (!hasMother)
                        nOmegas++;
                  break;
                case 333:
                    if (!hasMother)
                        nPhis++;
                  break;
                case 443:
                    if (!hasMother)
                        nJPsis++;
                  break;
                case 22:
                    nPhotons++;
            }
            if (pdg == 11){
                int imother = track.getMotherTrackId();
                 if (imother > -1) {
                     auto mother = (*tracks)[imother];
                     int mpdg = mother.GetPdgCode();
                     switch (mpdg){
                        case 111:
                            nElectronsFromPion++;
                            break;
                        case 221:
                            nElectronsFromEta++;
                            break;
                        case 331:
                            nElectronsFromEtaPrime++;
                          break;
                        case 113:
                            nElectronsFromRho++;
                          break;
                        case 223:
                            nElectronsFromOmega++;
                          break;
                        case 333:
                            nElectronsFromPhi++;
                          break;
                        case 443:
                            nElectronsFromJPsi++;
                          break;
                        default:
                            std::cout << "Found electron with mother pdg " << mpdg << "\n";
                    }
                } else {
                    std::cerr << "Found electron with no mother" << "\n";
                    return 1;
                }
            }
	   }
    }
    int nMothers = nPions+nEtas+nEtaPrimes+nRhos+nOmegas+nPhis+nJPsis;
    std::cout << "#Events: " << nEvents << "\n"
	      << "#Electrons: " << nElectrons << "\n"
          << "#Positrons: " << nPositrons << "\n"
          << "#Leptons: " << nElectrons+nPositrons << ", #LeptonsToDone: " << nLeptonsToBeDone << "\n"
          << "#Photons: " << nPhotons << "\n"
          << "#Pions: " << nPions << ", #ElectronsFromPion: " << nElectronsFromPion << "\n"
          << "#Etas: " << nEtas << ", #ElectronsFromEta: " << nElectronsFromEta << "\n"
          << "#EtaPrimes: " << nEtaPrimes << ", #ElectronsFromEtaPrime: " << nElectronsFromEtaPrime << "\n"
          << "#Rhos: " << nRhos << ", #ElectronsFromRho: " << nElectronsFromRho << "\n"
          << "#Omegas: " << nOmegas << ", #ElectronsFromOmega: " << nElectronsFromOmega << "\n"
          << "#Phis: " << nPhis << ", #ElectronsFromPhi: " << nElectronsFromPhi << "\n"
          << "#JPsis: " << nJPsis << ", #ElectronsFromJPsi: " << nElectronsFromJPsi << "\n";
    if (nElectrons == 0) {
        std::cerr << "No electrons found\n";
        return 1;
    }
    if (nElectrons != nPositrons) {
        std::cerr << "Number of electrons should match number of positrons\n";
        return 1;
    }
    if (nLeptonsToBeDone != nElectrons+nPositrons) {
        std::cerr << "The number of leptons should be the same as the number of leptons which should be transported.\n";
        return 1;
    }
    if (nMothers < nEvents) {
        std::cerr << "The number of mother particles (pi0, eta, etaprime, rho, omega, phi, JPsi) must be at least the number of events\n";
        return 1;
    }
    if (nElectronsFromPion < nPions) {
        std::cerr << "Number of of electrons from pions has to be at least the number of pions\n";
        return 1;
    }
    if (nElectronsFromEta < nEtas) {
        std::cerr << "Number of of electrons from etas has to be at least the number of etas\n";
        return 1;
    }
    if (nElectronsFromEtaPrime < nEtaPrimes) {
        std::cerr << "Number of of electrons from etaprimes has to be at least the number of etaprimes\n";
        return 1;
    }
    if (nElectronsFromRho < nRhos) {
        std::cerr << "Number of of electrons from rhos has to be at least the number of rhos\n";
        return 1;
    }
    if (nElectronsFromOmega < nOmegas) {
        std::cerr << "Number of of electrons from omegas has to be at least the number of omegas\n";
        return 1;
    }
    if (nElectronsFromPhi < nPhis) {
        std::cerr << "Number of of electrons from phis has to be at least the number of phis\n";
        return 1;
    }
    if (nElectronsFromJPsi < nJPsis) {
        std::cerr << "Number of of electrons from JPsis has to be at least the number of JPsis\n";
        return 1;
    }

    return 0;
}
