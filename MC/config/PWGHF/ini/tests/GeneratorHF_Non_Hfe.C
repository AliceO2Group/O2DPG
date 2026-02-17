int Hybrid() {
    std::string path{"o2sim_Kine.root"};

    const int pdgPi0 = 111;
    const int pdgEta = 221;
    const double yMin = -1.5;
    const double yMax = 1.5;
    const int minNb = 1;

    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree*)file.Get("o2sim");
    if (!tree) {
        std::cerr << "Cannot find tree o2sim\n";
        return 1;
    }

    std::vector<o2::MCTrack>* tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nEvents = tree->GetEntries();
    int nAccepted = 0;
    int totalPi0 = 0, totalEta = 0;

    for (int i = 0; i < nEvents; ++i) {
        tree->GetEntry(i);

        int count = 0;
        for (auto& track : *tracks) {
            int pdg = std::abs(track.GetPdgCode());
            double y = track.GetRapidity();

            if ((pdg == pdgPi0 || pdg == pdgEta) && y >= yMin && y <= yMax) {
                count++;
                if (pdg == pdgPi0) totalPi0++;
                if (pdg == pdgEta) totalEta++;
            }
        }

        if (count < minNb) {
            std::cerr << " Trigger violation in event " << i
                      << " (found " << count << " π0/η in rapidity window)\n";
            return 1;
        }

        nAccepted++;
    }

    std::cout << "--------------------------------------\n";
    std::cout << "Trigger test: π0/η within rapidity window\n";
    std::cout << "Events tested: " << nEvents << "\n";
    std::cout << "Events accepted: " << nAccepted << "\n";
    std::cout << "# π0: " << totalPi0 << ", # η: " << totalEta << "\n";
    std::cout << "Trigger test PASSED\n";

    return 0;
}
