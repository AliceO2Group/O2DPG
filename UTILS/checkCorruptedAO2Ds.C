#include <TFile.h>
#include <TDirectoryFile.h>
#include <TTree.h>
#include <TTreeReader.h>
#include <TGrid.h>
#include <iostream>
#include <TError.h>
#include <cstring>

bool gWarningDetected = false; // Global flag to track the warning

void MyErrorHandler(int level, Bool_t abort, const char *location, const char *msg) {
    if (strstr(msg, "repair") != nullptr) {
        gWarningDetected = true;
    }
    DefaultErrorHandler(level, abort, location, msg); // Call ROOT’s default handler
}

int checkCorruptedAO2Ds(TString infileName = "/alice/sim/2024/LHC24h2/535545/AOD/005/AO2D.root", bool fromAlien = true) {
    
    SetErrorHandler(MyErrorHandler);

    if (fromAlien) {
        TGrid::Connect("alien://");
        if (!infileName.Contains("alien://")) {
            infileName = "alien://" + infileName;
        }
    }

    auto inFile = TFile::Open(infileName.Data());
    if (!inFile || inFile->IsZombie()) {
        return -1;
    }

    // all VLA branches in the AO2Ds.root
    std::map<std::string, std::vector<std::string>> branchesToCheck = {
        {"O2mcparticle_001", std::vector<std::string>{"fIndexArray_Mothers", "fVx", "fIndexMcCollisions"}},
        {"O2ft0", std::vector<std::string>{"fAmplitudeA", "fChannelA", "fAmplitudeC", "fChannelC"}},
        {"O2fv0a", std::vector<std::string>{"fAmplitude", "fChannel"}},
        {"O2mccalolabel_001", std::vector<std::string>{"fIndexArrayMcParticles", "fAmplitudeA"}},
        {"O2zdc_001", std::vector<std::string>{"fEnergy", "fChannelE", "fAmplitude", "fTime", "fChannelT"}}
    };

    for (auto const& dirKey : *inFile->GetListOfKeys()) {
        if (TString(dirKey->GetName()).Contains("DF")) {
            auto df = static_cast<TDirectoryFile*>(inFile->Get(dirKey->GetName()));
            std::cout << dirKey->GetName() << std::endl;
            for (auto const& pair : branchesToCheck) {
                auto tree = static_cast<TTree*>(df->Get(pair.first.data()));
                for (auto const& branchName : pair.second) {
                    auto leaf = static_cast<TLeaf*>(tree->GetLeaf(branchName.data()));

                    for (int iEntry{0}; iEntry<tree->GetEntries(); ++iEntry) {
                        if (tree->GetEntry(iEntry) < 0) {
                            std::cout << "Found corrupted file! DF: " << dirKey->GetName() << " Tree:" << pair.first.data() << " Branch:" << branchName.data() << std::endl;
                            return -1;
                        }
                        if (gWarningDetected) {
                            std::cout << "Found file in need of repair! DF: " << dirKey->GetName() << " Tree:" << pair.first.data() << " Branch:" << branchName.data() << std::endl;
                            return -2;
                        }
                    }
                }
            }
        }
    }

    return 0;
}
