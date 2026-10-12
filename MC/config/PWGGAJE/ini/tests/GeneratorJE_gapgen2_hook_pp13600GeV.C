int External() {
    std::string path{"o2sim_Kine.root"};

    float ratioTrigger = 1./2; // one event triggered out of 2


    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);
    o2::dataformats::MCEventHeader *eventHeader = nullptr;
    tree->SetBranchAddress("MCEventHeader.", &eventHeader);

    int nEventsMB{}, nEventsJetJet{};
    float sumWeightsMB{}, sumWeightsJetJet{};
    int sumTracks{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);

        // check subgenerator information and event weights
        if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
            bool isValid = false;
            int subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
            if (eventHeader->hasInfo(o2::dataformats::MCInfoKeys::weight)) {
                float weight = eventHeader->getInfo<float>(o2::dataformats::MCInfoKeys::weight,isValid);
                if (subGeneratorId == 0) {
                    nEventsMB++;
                    sumWeightsMB += weight;
                } 
                else if (subGeneratorId == 1) {
                    nEventsJetJet++;
                    sumWeightsJetJet += weight;
                }
            }
        }
        sumTracks += tracks->size();
    }

    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << "# MB events: " << nEventsMB << "\n";
    std::cout << "  sum of weights for MB events: " << sumWeightsMB << "\n";
    std::cout << "# Jet-jet events " << nEventsJetJet << "\n";
    std::cout << "  sum of weights jet-jet events: " << sumWeightsJetJet << "\n";
    std::cout << "# tracks summed over all events (jet-jet + MB): " << sumTracks << "\n";

    if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 || nEventsMB > nEvents * (1 - ratioTrigger) * 1.05) { // we put some tolerance since the number of generated events is small
        std::cerr << "Number of generated MB events different than expected\n";
        return 1;
    }
    if (nEventsJetJet < nEvents * ratioTrigger * 0.95 || nEventsJetJet > nEvents * ratioTrigger * 1.05) {
        std::cerr << "Number of jet-jet generated events different than expected\n";
        return 1;
    }
    if(nEventsMB < sumWeightsMB * 0.95 || nEventsMB > sumWeightsMB * 1.05) {
        std::cerr << "Weights of MB events do not = 1 as expected\n";
        return 1;
    }
    if(sumTracks < 1) {
        std::cerr << "No tracks in simulated events\n";
        return 1;
    }
    return 0;
}
