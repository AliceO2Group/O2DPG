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

    int nMesons{};
    int nMesonsDiMuonDecay{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        for (auto& track : *tracks) {
            auto pdg = track.GetPdgCode();
            auto y = track.GetRapidity();
            if ((pdg == 221) || (pdg == 331) || (pdg == 223) || (pdg == 113) || (pdg == 333)) {
               if ((y>-4.3) && (y<-2.2)) { 
                  nMesons++;
                  Int_t counterel = 0;
                  Int_t counterpos = 0;
                  int k1 = track.getFirstDaughterTrackId();
                  int k2 = track.getLastDaughterTrackId();
                  // k1 < k2 and no -1 for k2
                  for (int d=k1; d <= k2; d++) {
                      if (d>0) {
                         auto decay = (*tracks)[d];
                         int pdgdecay = decay.GetPdgCode();
                         if (pdgdecay == 13) {
                            counterel++;
                         }
                         if (pdgdecay == -13) {
                            counterpos++;
                         }
                      }
                  }
                  if ((counterel>0) && (counterpos>0)) nMesonsDiMuonDecay++;
              }
           }
        }
    }	
    
    std::cout << "#events: " << nEvents << "\n"
              << "#mesons: " << nMesons << "\n";

    if (nMesons < (nEvents*5)) {
        std::cerr << "One should have at least one mesons in forward region per 5 events.\n";
        return 1;
    }
    //if (nMesonsDiMuonDecay < nEvents) {
        //std::cerr << "One meson to dimuon decay per event should be produced.\n";
        //return 1;
    //}

    return 0;
}
