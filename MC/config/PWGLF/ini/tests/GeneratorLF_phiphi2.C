#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "TDatabasePDG.h"
#include "TFile.h"
#include "TMath.h"
#include "TSystem.h"
#include "TTree.h"
#include "SimulationDataFormat/MCTrack.h"
#include <iostream>
#include <vector>
#include <algorithm>
#endif

// Include the underlying rapidity generator header/macro
#include "generator_pythia8_LF_rapidity.C"

/// Entry point to configure the particle gun generator for resonance simulation
FairGenerator *generatePhiResonanceGun(int pdg = 999999, // Custom PDG or specific target PDG
                                       float ptMin = 0.0,
                                       float ptMax = 50.0,
                                       float yMin = -1.0,
                                       float yMax = 1.0,
                                       std::string pythiaCfg = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/pythia8_inel_136tev.cfg",
                                       int nInject = 3)
{
    // Configure particle parameters (PDG, count, ptMin, ptMax, yMin, yMax)
    GeneratorPythia8LFRapidity::ConfigContainer cfg(pdg, nInject, ptMin, ptMax, yMin, yMax);

    std::vector<GeneratorPythia8LFRapidity::ConfigContainer> cfgVec;
    std::vector<GeneratorPythia8LFRapidity::ConfigContainer> cfgVecGenDecayed;

    // Let Pythia generator handle decays internally
    cfgVecGenDecayed.push_back(cfg);

    return generateLFRapidity(cfgVec, cfgVecGenDecayed,
                              /*injectOnePDGPerEvent=*/true,
                              /*gapBetweenInjection=*/0,
                              /*useTrigger=*/false,
                              /*useRapidity=*/true,
                              /*pythiaCfgMb=*/pythiaCfg,
                              /*pythiaCfgSignal=*/"");
}

/// Validation function to analyze o2sim_Kine.root post-simulation
int External()
{
    std::string path{"o2sim_Kine.root"};
    int numberOfGapEvents{0};
    int numberOfEventsProcessed{0};
    int numberOfEventsProcessedWithoutInjection{0};

    // Target PDG state and decaying daughters (e.g. Phi -> K+ K-)
    std::vector<int> injectedPDGs = {999999}; 
    std::vector<std::vector<int>> decayDaughters = {
        {333, 333} // Decaying into phi-phi (PDG 333, 333)
    };

    auto nInjection = injectedPDGs.size();

    TFile file(path.c_str(), "READ");
    if (file.IsZombie())
    {
        std::cerr << "Cannot open ROOT file " << path << "\n";
        return 1;
    }

    auto tree = (TTree *)file.Get("o2sim");
    if (!tree)
    {
        std::cerr << "Cannot find tree o2sim in file " << path << "\n";
        return 1;
    }

    std::vector<o2::MCTrack> *tracks{};
    tree->SetBranchAddress("MCTrack", &tracks);

    std::vector<int> nSignal(nInjection, 0);
    std::vector<std::vector<int>> nDecays;
    std::vector<int> nNotDecayed(nInjection, 0);

    for (size_t i = 0; i < nInjection; i++)
    {
        nDecays.push_back(std::vector<int>(decayDaughters[i].size(), 0));
    }

    auto nEvents = tree->GetEntries();
    bool hasInjection = false;

    for (int i = 0; i < nEvents; i++)
    {
        hasInjection = false;
        numberOfEventsProcessed++;
        tree->GetEntry(i);

        for (size_t idxMCTrack = 0; idxMCTrack < tracks->size(); ++idxMCTrack)
        {
            auto track = tracks->at(idxMCTrack);
            auto pdg = track.GetPdgCode();
            auto it = std::find(injectedPDGs.begin(), injectedPDGs.end(), pdg);

            if (it != injectedPDGs.end())
            {
                int index = std::distance(injectedPDGs.begin(), it);
                nSignal[index]++;

                if (track.getFirstDaughterTrackId() < 0)
                {
                    nNotDecayed[index]++;
                    continue;
                }

                for (int j{track.getFirstDaughterTrackId()}; j <= track.getLastDaughterTrackId(); ++j)
                {
                    auto pdgDau = tracks->at(j).GetPdgCode();
                    bool foundDau = false;

                    for (size_t idxDaughter = 0; idxDaughter < decayDaughters[index].size(); ++idxDaughter)
                    {
                        if (pdgDau == decayDaughters[index][idxDaughter])
                        {
                            nDecays[index][idxDaughter]++;
                            foundDau = true;
                            hasInjection = true;
                            break;
                        }
                    }
                    if (!foundDau)
                    {
                        std::cerr << "Decay daughter not found: " << pdg << " -> " << pdgDau << "\n";
                    }
                }
            }
        }
        if (!hasInjection)
        {
            numberOfEventsProcessedWithoutInjection++;
        }
    }

    std::cout << "--------------------------------\n";
    std::cout << "# Events: " << nEvents << "\n";
    for (size_t i = 0; i < nInjection; i++)
    {
        std::cout << "# Mother PDG " << injectedPDGs[i] << " generated: "
                  << nSignal[i] << ", " << nNotDecayed[i] << " did not decay\n";
        for (size_t j = 0; j < decayDaughters[i].size(); j++)
        {
            std::cout << "# Daughter PDG " << decayDaughters[i][j] << ": " << nDecays[i][j] << "\n";
        }
    }
    std::cout << "--------------------------------\n";

    return 0;
}

void GeneratorLF_phiphi2() { External(); }