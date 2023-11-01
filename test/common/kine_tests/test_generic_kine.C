int test_generic_kine()
{
    std::string path{"o2sim_Kine.root"};
    TFile file(path.c_str(), "READ");
    if (file.IsZombie())
    {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);
    bool hasParticlesForTransport{};

    for (int i = 0; i < tree->GetEntries(); i++) {
        tree->GetEntry(i);
        int iTrack{};
        for (auto &track : *tracks) {
            iTrack++;
            if (track.getToBeDone()) {
                hasParticlesForTransport = true;
            }

            if (!o2::mcgenstatus::isEncoded(track.getStatusCode())) {
                std::cerr << "Particle " << iTrack << " has invalid status encoding, make sure you set the status code correctly (see https://aliceo2group.github.io/simulation/docs/generators/).\n";
                return 1;
            }
        }
    }
    if (!hasParticlesForTransport) {
        std::cerr << "No particles marked to be transported. Make sure they are marked correctly (see https://aliceo2group.github.io/simulation/docs/generators/).\n";
        return 1;
    }
    return 0;
}
