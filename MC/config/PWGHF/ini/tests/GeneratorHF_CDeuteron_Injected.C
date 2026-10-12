int External() {
    std::string path{"o2sim_Kine.root"};

    int pdgCDeuteron{2010010020};
    int checkNumberOfCDeuteronPerEvent{10};
    float checkLifetimeCDeuteron{0.05f};
    std::map<int, std::vector<std::vector<int>>> checkDecays{
        {2010010020, {{-321, 211, 1000010020}}} // c-deuteron -> K- + pi+ + deuteron
    };
    float checkFracCDeuteronFromBeauty{0.25};

    TFile file(path.c_str(), "READ");
    if (file.IsZombie()) {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    int nCDeuteron{}, nCDeuteronGoodDecay{}, nCDeuteronFromBeauty{};
    std::array<float, 2> averageLifetimeCDeuteron{0.f, 0.f}; // prompt and non-prompt
    float massCDeuteron = 3.226f;
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {
        tree->GetEntry(i);

        for (auto &track : *tracks) {
            auto pdg = track.GetPdgCode();
            auto absPdg = std::abs(pdg);
            // std::cout << "Event " << i << ": found particle with PDG " << pdg << std::endl;

            if (absPdg == pdgCDeuteron) { // found signal
                nCDeuteron++; // count signal PDG

                // std::cout << "Event " << i << ": found c-deuteron with PDG " << pdg << std::endl;

                std::vector<int> pdgsDecay{};
                std::vector<int> pdgsDecayAntiPart{};
                if (track.getFirstDaughterTrackId() >= 0 && track.getLastDaughterTrackId() >= 0) {
                    for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                        // std::cout << "Fetching daughter track with ID " << j << std::endl;
                        auto pdgDau = tracks->at(j).GetPdgCode();
                        // std::cout << "PDG of daughter track " << j << ": " << pdgDau << std::endl;
                        pdgsDecay.push_back(pdgDau);
                        if (pdgDau != 333 && pdgDau != 111) { // phi and pi0 are antiparticles of themselves
                            pdgsDecayAntiPart.push_back(-pdgDau);
                        } else {
                            pdgsDecayAntiPart.push_back(pdgDau);
                        }
                    }
                }
                // std::cout << "Daughters fetched" << std::endl;

                auto mother = track.getMotherTrackId();
                bool isFromBeauty{false};
                if (mother >= 0 && std::abs(tracks->at(mother).GetPdgCode()) == 5122) { // check if c-deuteron comes from Lb
                    nCDeuteronFromBeauty++;
                    isFromBeauty = true;
                }

                auto dauTrack = tracks->at(track.getFirstDaughterTrackId());
                float decayLength = std::sqrt((track.GetStartVertexCoordinatesX() - dauTrack.GetStartVertexCoordinatesX()) * (track.GetStartVertexCoordinatesX() - dauTrack.GetStartVertexCoordinatesX()) + (track.GetStartVertexCoordinatesY() - dauTrack.GetStartVertexCoordinatesY()) * (track.GetStartVertexCoordinatesY() - dauTrack.GetStartVertexCoordinatesY()) + (track.GetStartVertexCoordinatesZ() - dauTrack.GetStartVertexCoordinatesZ()) * (track.GetStartVertexCoordinatesZ() - dauTrack.GetStartVertexCoordinatesZ()));
                if (!isFromBeauty) {
                    averageLifetimeCDeuteron[0] += decayLength * massCDeuteron / track.GetP();
                } else {
                    averageLifetimeCDeuteron[1] += decayLength * massCDeuteron / track.GetP();
                }

                std::sort(pdgsDecay.begin(), pdgsDecay.end());
                std::sort(pdgsDecayAntiPart.begin(), pdgsDecayAntiPart.end());

                for (auto &decay : checkDecays[std::abs(pdg)]) {
                    if (pdgsDecay == decay || pdgsDecayAntiPart == decay) {
                        nCDeuteronGoodDecay++;
                        break;
                    }
                }
                // std::cout << "Daughters checked " << std::endl;
            }
        }
    }

    averageLifetimeCDeuteron[0] /= nCDeuteron - nCDeuteronFromBeauty;
    averageLifetimeCDeuteron[1] /= nCDeuteronFromBeauty;

    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout <<"# signal c-deuteron: " << nCDeuteron << "\n";
    std::cout <<"# signal c-deuteron decaying in the correct channel: " << nCDeuteronGoodDecay << "\n";
    std::cout <<"# signal c-deuteron from beauty: " << nCDeuteronFromBeauty << "\n";
    std::cout <<"Average lifetime of c-deuteron (prompt): " << averageLifetimeCDeuteron[0] << " (cm) \n";
    std::cout <<"Average lifetime of c-deuteron (non-prompt): " << averageLifetimeCDeuteron[1] << " (cm) \n";

    float numberOfCDeuteronPerEvent = float(nCDeuteron) / nEvents;
    float fracCDeuteronGoodDecay = float(nCDeuteronGoodDecay) / nCDeuteron;
    float fracCDeuteronFromBeauty = float(nCDeuteronFromBeauty) / nCDeuteron;

    if (std::abs(numberOfCDeuteronPerEvent - checkNumberOfCDeuteronPerEvent) / numberOfCDeuteronPerEvent > 0.05) { // we put some tolerance since the number of generated events is small
        std::cerr << "Number of C-deuterons per event " << numberOfCDeuteronPerEvent << " different than expected " << checkNumberOfCDeuteronPerEvent << "\n";
        return 1;
    }

    if (fracCDeuteronGoodDecay < 0.95) { // we put some tolerance since the number of generated events is small
        std::cerr << "Fraction of signals decaying into the correct channel " << fracCDeuteronGoodDecay << " lower than expected\n";
        return 1;
    }

    if (std::abs(fracCDeuteronFromBeauty - checkFracCDeuteronFromBeauty) / checkFracCDeuteronFromBeauty > 0.10) { // we put some tolerance since the number of generated events is small
        std::cerr << "Fraction of signals from beauty " << fracCDeuteronFromBeauty << " different than expected " << checkFracCDeuteronFromBeauty << "\n";
        return 1;
    }

    if (std::abs(averageLifetimeCDeuteron[0] - checkLifetimeCDeuteron) / checkLifetimeCDeuteron > 0.10) { // we put some tolerance since the number of generated events is small
        std::cerr << "Lifetime for prompt c-deuteron " << averageLifetimeCDeuteron[0] << " different than expected " << checkLifetimeCDeuteron << "\n";
        return 1;
    }

    if (std::abs(averageLifetimeCDeuteron[1] - checkLifetimeCDeuteron) / checkLifetimeCDeuteron > 0.10) { // we put some tolerance since the number of generated events is small
        std::cerr << "Lifetime for non-prompt c-deuteron " << averageLifetimeCDeuteron[1] << " different than expected " << checkLifetimeCDeuteron << "\n";
        return 1;
    }

    return 0;
}
