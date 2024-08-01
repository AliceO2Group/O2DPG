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
    auto nEvents = tree->GetEntries();
    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);
        bool found_b = false;
        bool found_bbar = false;
        for (auto& track : *tracks) {
            int pdg = track.GetPdgCode();
            if (pdg == 5){
                found_b = true;
            }
            if (pdg == -5){
                found_bbar = true;
            }
            if ( abs(pdg) == 411 || abs(pdg) == 421 || abs(pdg) == 431 || abs(pdg) == 4122 || abs(pdg) == 4232 || abs(pdg) == 4132 || abs(pdg) == 4332){
                int ifirstdaughter = track.getFirstDaughterTrackId();
                int ilastdaughter = track.getLastDaughterTrackId();
                if (ifirstdaughter == -1 || ilastdaughter == -1){
                    std::cerr << "Found charm hadron that does not have daughters" << "\n";
                    return 1;
                }
                bool found_electron = false;
                for (int j = ifirstdaughter; j<= ilastdaughter; j++){
                    auto track2 = (*tracks)[j];
                    if ( abs(track2.GetPdgCode())==11){
                        found_electron = true;
                        if (!(track2.getWeight() < 0.999)){
                            std::cerr << "Found electron from forced decay with weight 1" << "\n";
                            return 1;
                        }
                        if (!track2.getToBeDone()){
                            std::cerr << "Found electron from forced decay that is not transported" << "\n";
                            return 1;
                        }
                    }
                }
                if (!found_electron){
                    std::cerr << "Found charm hadron that does not decay to electron" << "\n";
                    return 1;
                }
            }
        }
        if ((!found_b) || (!found_bbar)){
            std::cerr << "Found event without b-bbar pair" << "\n";
            return 1;
        }
    }
    return 0;
}
