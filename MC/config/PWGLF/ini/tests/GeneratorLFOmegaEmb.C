int External()
{
    std::string path{"o2sim_Kine.root"};
    int checkPdgSignal{3334};
    std::cout << "Check for signal PDG " << checkPdgSignal << "\n";
    std::cout << "Check only the mother, decay entrusted to GEANT4\n";

    TFile file(path.c_str(), "READ");
    if (file.IsZombie())
    {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nSignal{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++)
    {
        tree->GetEntry(i);
        for (auto &track : *tracks)
        {
            auto pdg = track.GetPdgCode();
            if (abs(pdg) == checkPdgSignal)
            {
                // count signal PDG
                nSignal++;
            }
        }
    }
    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << "# Mother " << checkPdgSignal << ": " << nSignal << "\n";


    if (nSignal != nEvents * 3)
    {
        std::cerr << "Number of generated " << checkPdgSignal << " lower than expected\n";
        return 1;
    }
    return 0;
}