#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/HeavyIons.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include "GeneratorCocktailStarlight_PbPb5TeV.C"
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

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
        mNumSignals = 0;
        switch (gentype) {
            case 0: // generate photoproduced charmonia cocktail at mid rapidity at 5TeV
                mGeneratorParam = (Generator*)GeneratorCocktailStarlightMidy_PbPb5TeV();
                break;
            case 1: // generate coherent charmonia cocktail at mid rapidity at 5TeV
                mGeneratorParam = (Generator*)GeneratorCocktailStarlightCoherentMidy_PbPb5TeV();
                break;
            case 2: // generate incoherent charmonia cocktail at mid rapidity at 5TeV
                mGeneratorParam = (Generator*)GeneratorCocktailStarlightIncoherentMidy_PbPb5TeV();
                break;
            case 3: // generate coherent charmonia cocktail at forward rapidity at 5TeV
                mGeneratorParam = (Generator*)GeneratorCocktailStarlightCoherentFwdy_PbPb5TeV();
                break;
            case 4: // generate incoherent charmonia cocktail at forward rapidity at 5TeV
                mGeneratorParam = (Generator*)GeneratorCocktailStarlightIncoherentFwdy_PbPb5TeV();
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
        mNumSignals = 0;
        bool genOk = false;
        if (mGeneratedEvents % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
            std::cout<<"generating event with injected signals"<<std::endl;
            while (!genOk){ 
                genOk = GeneratorPythia8::generateEvent();
            }
            double impactParameter = -1.;
            if (mPythia.info.hiInfo) {
                impactParameter = mPythia.info.hiInfo->b();
                mNumSignals = getNumSignalsForImpactParameter(impactParameter);
            } else {
                std::cout<<"no heavy-ion info available; embedding no signal events"<<std::endl;
            }
            std::cout<<"MB event impact parameter: "<<impactParameter<<", embedding "<<mNumSignals<<" signal events"<<std::endl;
            notifySubGenerator(mNumSignals > 0 ? 1 : 0);
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

        if ((mGeneratedEvents-1) % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
            for (int isig = 0; isig < mNumSignals; isig++) {
                bool found = false;
                while (!found) {
                    if (!mGeneratorParam->generateEvent()) {
                        continue;
                    }
                    if (!mGeneratorParam->importParticles()) {
                        mGeneratorParam->clearParticles();
                        continue;
                    }
                    found = findSignalInAcceptance();
                    if (found) {
                        appendCurrentSignalParticles(isig);
                    }
                    mGeneratorParam->clearParticles();
                }
            }
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
        }
        std::cout<<"generated signal in acceptance"<<std::endl;
        return true;
    }

    int getNumSignalsForImpactParameter(double impactParameter) const
    {
        const double photoproductionImpactParameterCut = 4.0; // tmp cut to embed signal > 10% centrality
        if (impactParameter < photoproductionImpactParameterCut) {
            std::cout<<"impact parameter: "<<impactParameter<<" fm, below photoproduction cut "
                     <<photoproductionImpactParameterCut<<" fm; embedding no signal events"<<std::endl;
            return 0;
        }
        return std::max(0, static_cast<int>(std::lround(5.0 + 0.886202881 * std::pow(std::max(0.0, 17.5 - impactParameter), 1.7))));
    }

    void appendCurrentSignalParticles(int signalIndex)
    {
        int originalSize = mParticles.size();
        std::cout<<"adding "<<mGeneratorParam->getParticles().size()<<" particles from signal event "<<signalIndex<<" to the stack"<<std::endl;
        for(size_t ipart=0; ipart < mGeneratorParam->getParticles().size(); ipart++){
            TParticle part = TParticle(mGeneratorParam->getParticles().at(ipart));
            if(part.GetFirstMother() >= 0) part.SetFirstMother(part.GetFirstMother() + originalSize);
            if(part.GetSecondMother() >= 0) part.SetLastMother(part.GetSecondMother() + originalSize);
            if(part.GetFirstDaughter() >= 0) part.SetFirstDaughter(part.GetFirstDaughter() + originalSize);
            if(part.GetLastDaughter() >= 0) part.SetLastDaughter(part.GetLastDaughter() + originalSize);
            mParticles.push_back(part);
            // encodeParticleStatusAndTracking method already called in GeneratorEvtGen.C
        }
    }

private:
    Generator* mGeneratorParam = nullptr;
    unsigned long long mGeneratedEvents = 0;
    int mInverseTriggerRatio = 1;
    int mNumSignals = 0;
    // Pythia8::Pythia pythiaMBgen; // minimum bias event
    std::vector<int> mSignalsPDGs;
    double mHadronRapidityMin;
    double mHadronRapidityMax;
};
}
}

FairGenerator*
  GeneratorPhotoproduction(int triggerGap, int gentype = 0, double rapidityMin = -1.5, double rapidityMax = 1.5)
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