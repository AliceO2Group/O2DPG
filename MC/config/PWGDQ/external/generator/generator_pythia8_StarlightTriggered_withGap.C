#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include "GeneratorCocktailStarlight_PbPb5TeV.C"
#include <string>

using namespace o2::eventgen;
using namespace Pythia8;

namespace o2
{
namespace eventgen
{


class GeneratorPythia8StarlightTriggeredWithGap : public o2::eventgen::GeneratorPythia8 {
public: 

    /// default constructor
    GeneratorPythia8StarlightTriggeredWithGap() = default;

    /// constructor
    GeneratorPythia8StarlightTriggeredWithGap(int inputTriggerRatio = 5, int gentype = 0) {
        mGeneratedEvents = 0;
        mInverseTriggerRatio = inputTriggerRatio; 
        switch (gentype) {
            case 0: // generate prompt charmonia cocktail at mid rapidity at 5TeV
                mGeneratorParam = (Generator*)GeneratorCocktailStarlightMidy_PbPb5TeV();
                break;
        }
        mGeneratorParam->Init();  

        addSubGenerator(0, "Minimum bias");
        addSubGenerator(1, "event with injected signals");
    }

    /// Deconstructor
    ~GeneratorPythia8StarlightTriggeredWithGap() = default;

    void addSignalPDGs(int pdg) { mSignalsPDGs.push_back(pdg); };

    void setRapidityRange(double valMin, double valMax)
    {
        mHadronRapidityMin = valMin;
        mHadronRapidityMax = valMax;
    };

protected: 
    Bool_t generateEvent() override
    {
        // GeneratorPythia8::generateEvent();
        bool genOk = false;
        if (mGeneratedEvents % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
            // bool found = false;
            std::cout<<"generating event with injected signals"<<std::endl;
            while (!genOk){ 
                genOk = GeneratorPythia8::generateEvent();
                bool found = false;
                while (!found) {
                    mGeneratorParam->generateEvent();
                    found = findSignalInAcceptance();
                }
            }
            notifySubGenerator(1);
        } else { // gap event
            while (!genOk) {
                genOk = GeneratorPythia8::generateEvent();
            }
            notifySubGenerator(0);
        }
        mGeneratedEvents++;
        std::cout<<"generated events: "<<mGeneratedEvents<<std::endl;
        return true;
    }

    Bool_t importParticles() override
    {
        GeneratorPythia8::importParticles();

        bool genOk = false;
        if ((mGeneratedEvents-1) % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
            mGeneratorParam->importParticles();
            int originalSize = mParticles.size();
            for(int ipart=0; ipart < mGeneratorParam->getParticles().size(); ipart++){
                TParticle part = TParticle(mGeneratorParam->getParticles().at(ipart));
                if(part.GetFirstMother() >= 0) part.SetFirstMother(part.GetFirstMother() + originalSize);
                if(part.GetFirstDaughter() >= 0) part.SetFirstDaughter(part.GetFirstDaughter() + originalSize);
                if(part.GetLastDaughter() >= 0) part.SetLastDaughter(part.GetLastDaughter() + originalSize);
                mParticles.push_back(part); 
                // encodeParticleStatusAndTracking method already called in GeneratorEvtGen.C 
            }	   
            mGeneratorParam->clearParticles(); 
        }

        return true;
    }

    bool findSignalInAcceptance() {
        std::cout<<"loop over" << mGeneratorParam->getParticles().size()<<" particles"<<std::endl;
        for (int pdg : mSignalsPDGs) {
            std::cout<<"signal pdg: "<<pdg<<std::endl;
        }
        for (int ipart = 0; ipart < mGeneratorParam->getParticles().size(); ipart++) {
            TParticle part = TParticle(mGeneratorParam->getParticles().at(ipart));
            // make sure all signals are in the acceptance
            for (int pdg : mSignalsPDGs) {
                if (part.GetPdgCode() == pdg) {
                    std::cout<<"found signal with pdg: "<<part.GetPdgCode()<<", mother: "<<part.GetFirstMother()<<std::endl;
                    if (part.GetFirstMother() == -1) {
                        if (part.Y() < mHadronRapidityMin || part.Y() > mHadronRapidityMax) {
                            return false;
                        }
                    }
                }
            }
            // if (std::find(mSignalsPDGs.begin(), mSignalsPDGs.end(), part.GetPdgCode()) != mSignalsPDGs.end()) {
            //     std::cout<<"found signal with pdg: "<<part.GetPdgCode()<<", mother: "<<part.GetFirstMother()<<std::endl;
            //     if (part.GetFirstMother() == -1) {
            //         std::cout<<"found signal with pdg: "<<part.GetPdgCode()<<", rapidity: "<<part.Y()<<std::endl;
            //         if (part.Y() < mHadronRapidityMin || part.Y() > mHadronRapidityMax) {
            //             return false;
            //         }
            //     }
            // }
        }
        std::cout<<"generated signal in acceptance"<<std::endl;
        return true;
    }

private:
    Generator* mGeneratorParam;
    unsigned long long mGeneratedEvents;
    int mInverseTriggerRatio;
    // Pythia8::Pythia pythiaMBgen; // minimum bias event
    std::vector<int> mSignalsPDGs;
    double mHadronRapidityMin;
    double mHadronRapidityMax;
};
}
}

FairGenerator*
  GeneratorPhotoproduction_Midy(int triggerGap, int gentype = 0, double rapidityMin = -1.5, double rapidityMax = 1.5)
{
  auto gen = new o2::eventgen::GeneratorPythia8StarlightTriggeredWithGap(triggerGap, gentype);
  gen->setRapidityRange(rapidityMin, rapidityMax);
  gen->addSignalPDGs(443); // J/Psi
  gen->addSignalPDGs(100443); // Psi(2S)
  gen->addSignalPDGs(11); // e
//   auto seed = (gRandom->TRandom::GetSeed() % 900000000);
//   gen->readString("Random:setSeed on");
//   gen->readString("Random:seed " + std::to_string(seed));
  return gen;
}