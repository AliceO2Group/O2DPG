#include "TFile.h"
#include "TTree.h"

#include <string>
#include <iostream>

int External() {
    std::string path{"/home/mattia/Documenti/cernbox/Documents/PostDoc/D2H/MC/corrBkgSigmaC/tf1/genevents_Kine.root"};

    int checkPdgQuarkOne{4};
    int checkPdgQuarkTwo{5};
    float ratioTrigger = 1./5.; // one event triggered out of 5
    std::array<std::array<int, 2>, 2> pdgReplParticles = {std::array{413, 14122}, std::array{413, 4124}};
    std::array<std::array<int, 2>, 2> pdgReplPartCounters = {std::array{0, 0}, std::array{0, 0}};
    std::array<float, 2> freqRepl = {0.5, 0.5};
    std::map<int, int> sumOrigReplacedParticles = {{413, 0}};

    std::array<int, 2> checkPdgHadron{14122, 4124};
    std::map<int, std::vector<std::vector<int>>> checkHadronDecays{ // sorted (!) pdg of daughters
        //{14122, {{4222, -211}, {4112, 211}, {4122, 211, -211}}}, // Lc(2595)+
        //{4124, {{4222, -211}, {4112, 211}, {4122, 211, -211}}} // Lc(2625)+
        {14122, {{-211, 4222}, {211, 4112}, {-211, 211, 4122}}}, // Lc(2595)+
        {4124, {{-211, 4222}, {211, 4112}, {-211, 211, 4122}}} // Lc(2625)+
    };

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

    int nEventsMB{}, nEventsInjOne{}, nEventsInjTwo{};
    int nSignals{}, nSignalGoodDecay{};
    auto nEvents = tree->GetEntries();

    for (int i = 0; i < nEvents; i++) {

        std::cout << std::endl;
        
        tree->GetEntry(i);

        // check subgenerator information
        int subGeneratorId{-1};
        if (eventHeader->hasInfo(o2::mcgenid::GeneratorProperty::SUBGENERATORID)) {
            bool isValid = false;
            subGeneratorId = eventHeader->getInfo<int>(o2::mcgenid::GeneratorProperty::SUBGENERATORID, isValid);
            if (subGeneratorId == 0) {
                nEventsMB++;
            } else if (subGeneratorId == checkPdgQuarkOne) {
                nEventsInjOne++;
            } else if (subGeneratorId == checkPdgQuarkTwo) {
                nEventsInjTwo++;
            }
        }

        for (auto &track : *tracks) {
            auto pdg = track.GetPdgCode();
            auto absPdg = std::abs(pdg);
            if (std::find(checkPdgHadron.begin(), checkPdgHadron.end(), absPdg) != checkPdgHadron.end()) { // found signal
                nSignals++; // count signal PDG
                std::cout << "==> signal " << absPdg << " found!" << std::endl;

                if (subGeneratorId == checkPdgQuarkOne) { // replacement only for prompt  ---> BUT ALSO NON-PROMPT D* SEEM TO BE REPLACED
                    for (int iRepl{0}; iRepl<2; ++iRepl) {
                        if (absPdg == pdgReplParticles[iRepl][0]) {
                            pdgReplPartCounters[iRepl][0]++;
                            sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]++;
                        } else if (absPdg == pdgReplParticles[iRepl][1]) {
                            pdgReplPartCounters[iRepl][1]++;
                            sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]++;
                        }
                    }
                } else if (subGeneratorId == checkPdgQuarkTwo) {
                    std::cout << "   NB: we have a " << absPdg << " also in event with quark " << checkPdgQuarkTwo << std::endl;
                    std::cout << "          ### mother indices: ";
                    int idFirstMother = track.getMotherTrackId();
                    int idSecondMother = track.getSecondMotherTrackId();
                    std::vector<int> motherIds = {};
                    for(int i=idFirstMother; i<=idSecondMother; i++) {
                        std::cout << i << " ";
                        motherIds.push_back(i);
                    }
                    bool partonicEventOn = false;
                    if(motherIds != std::vector<int>{-1, -1}) {
                        std::cout << "The " << absPdg << " particle has mothers. This should mean that it comes directly from parton hadronization, and that the partonic event was kept in the MC production " << std::endl;
                        partonicEventOn = true;
                    }
                    std::cout << "          ### mother PDG codes: ";
                    std::vector<int> motherPdgCodes = {};
                    if(partonicEventOn) {
                        for(int i=idFirstMother; i<=idSecondMother; i++) {
                            motherPdgCodes.push_back(tracks->at(i).GetPdgCode());
                            std::cout << motherPdgCodes.back() << " ";
                        }

                        /// check that among the mothers there is a c/cbar quark
                        /// This means that the charm hadron comes from the c-quark hadronization, where the c/cbar quark
                        /// comes from a c-cbar pair present in the current event, tagged with a b-bbar (e.g. double-parton scattering)
                        if(std::find(motherPdgCodes.begin(), motherPdgCodes.end(), 4) == motherPdgCodes.end() && std::find(motherPdgCodes.begin(), motherPdgCodes.end(), -4) == motherPdgCodes.end()) {
                            /// if the partinc event is not really saved and we arrive here, it means that  motherIds != {-1, -1} because 
                            /// the hadron comes from the decay of a beauty hadron. This can happen if and only if this is not a replaced one (i.e. native from Lambdab0 decay)
                            if (std::find(motherPdgCodes.begin(), motherPdgCodes.end(), 5122) == motherPdgCodes.end() && std::find(motherPdgCodes.begin(), motherPdgCodes.end(), -5122) == motherPdgCodes.end()) {
                                std::cerr << "The particle " << absPdg << " does not originate neither from a c/c-bar quark (replaced) nor from a Lambda_b0 decay. There is something wrong, aborting..." << std::endl;
                            return 1;
                            }
                        }
                    }
                    std::cout << std::endl;

                    /// only if we arrive here it means that everything is ok, and we can safely update the counters for the final statistics
                    for (int iRepl{0}; iRepl<2; ++iRepl) {
                        if (absPdg == pdgReplParticles[iRepl][0]) {
                            pdgReplPartCounters[iRepl][0]++;
                            sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]++;
                        } else if (absPdg == pdgReplParticles[iRepl][1]) {
                            pdgReplPartCounters[iRepl][1]++;
                            sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]++;
                        }
                    }
                }
                

                std::vector<int> pdgsDecay{};
                std::vector<int> pdgsDecayAntiPart{};
                if (track.getFirstDaughterTrackId() >= 0 && track.getLastDaughterTrackId() >= 0) {
                    for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j) {
                        auto pdgDau = tracks->at(j).GetPdgCode();
                        pdgsDecay.push_back(pdgDau);
                        std::cout << "   -- daughter " << j << ": " << pdgDau << std::endl;
                        if (pdgDau != 333) { // phi is antiparticle of itself
                            pdgsDecayAntiPart.push_back(-pdgDau);
                        } else {
                            pdgsDecayAntiPart.push_back(pdgDau);
                        }
                    }
                }

                std::sort(pdgsDecay.begin(), pdgsDecay.end());
                std::sort(pdgsDecayAntiPart.begin(), pdgsDecayAntiPart.end());

                for (auto &decay : checkHadronDecays[std::abs(pdg)]) {
                    if (pdgsDecay == decay || pdgsDecayAntiPart == decay) {
                        nSignalGoodDecay++;
                        std::cout << "     !!! GOOD DECAY FOUND !!!" << std::endl;
                        break;
                    }
                }
            }
        } // end loop over tracks
    }

    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    std::cout << "# MB events: " << nEventsMB << "\n";
    std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkOne) << nEventsInjOne << "\n";
    std::cout << Form("# events injected with %d quark pair: ", checkPdgQuarkTwo) << nEventsInjTwo << "\n";
    std::cout <<"# signal hadrons: " << nSignals << "\n";
    std::cout <<"# signal hadrons decaying in the correct channel: " << nSignalGoodDecay << "\n";

    if (nEventsMB < nEvents * (1 - ratioTrigger) * 0.95 || nEventsMB > nEvents * (1 - ratioTrigger) * 1.05) { // we put some tolerance since the number of generated events is small
        std::cerr << "Number of generated MB events different than expected\n";
        return 1;
    }
    if (nEventsInjOne < nEvents * ratioTrigger * 0.5 * 0.95 || nEventsInjOne > nEvents * ratioTrigger * 0.5 * 1.05) {
        std::cerr << "Number of generated events injected with " << checkPdgQuarkOne << " different than expected\n";
        return 1;
    }
    if (nEventsInjTwo < nEvents * ratioTrigger * 0.5 * 0.95 || nEventsInjTwo > nEvents * ratioTrigger * 0.5 * 1.05) {
        std::cerr << "Number of generated events injected with " << checkPdgQuarkTwo << " different than expected\n";
        return 1;
    }

    float fracForcedDecays = float(nSignalGoodDecay) / nSignals;
    if (fracForcedDecays < 0.9) { // we put some tolerance (e.g. due to oscillations which might change the final state)
        std::cerr << "Fraction of signals decaying into the correct channel " << fracForcedDecays << " lower than expected\n";
        return 1;
    }

    for (int iRepl{0}; iRepl<2; ++iRepl) {

        std::cout << " --- pdgReplPartCounters[" << iRepl << "][1] = " << pdgReplPartCounters[iRepl][1] << ", freqRepl[" << iRepl <<"] = " << freqRepl[iRepl] << ", sumOrigReplacedParticles[pdgReplParticles[" << iRepl << "][0]] =" << sumOrigReplacedParticles[pdgReplParticles[iRepl][0]] << std::endl; 
        
        if (std::abs(pdgReplPartCounters[iRepl][1] - freqRepl[iRepl] * sumOrigReplacedParticles[pdgReplParticles[iRepl][0]]) > 2 * std::sqrt(freqRepl[iRepl] * sumOrigReplacedParticles[pdgReplParticles[iRepl][0]])) { // 2 sigma compatibility
            float fracMeas = 0.;
            if (sumOrigReplacedParticles[pdgReplParticles[iRepl][0]] > 0.) {
                fracMeas = float(pdgReplPartCounters[iRepl][1]) / sumOrigReplacedParticles[pdgReplParticles[iRepl][0]];
            } 
            std::cerr << "Fraction of replaced " << pdgReplParticles[iRepl][0] << " into " << pdgReplParticles[iRepl][1] << " is " << fracMeas <<" (expected "<< freqRepl[iRepl] << ")\n";
            return 1;    
        }
    }

    return 0;
}
