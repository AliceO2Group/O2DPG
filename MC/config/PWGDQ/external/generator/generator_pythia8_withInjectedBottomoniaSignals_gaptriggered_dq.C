#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include "GeneratorBottomonia.C"
#include <string>

using namespace o2::eventgen;
using namespace Pythia8;

class GeneratorPythia8BottomoniaInjectedGapTriggeredDQ : public o2::eventgen::GeneratorPythia8 {
public:

  /// default constructor
  GeneratorPythia8BottomoniaInjectedGapTriggeredDQ() = default;

  /// constructor
  GeneratorPythia8BottomoniaInjectedGapTriggeredDQ(int inputTriggerRatio = 5, int gentype = 0) {

    mGeneratedEvents = 0;
    mGeneratorParam = 0x0;
    mInverseTriggerRatio = inputTriggerRatio; 
    switch (gentype) {
      case 0: // generate bottomonia cocktail at forward rapidity
        mGeneratorParam = (Generator*)GeneratorCocktailBottomoniaToMuonEvtGen_pp13TeV(); 
        break;
    }
    mGeneratorParam->Init();  
  }

  ///  Destructor
  ~GeneratorPythia8BottomoniaInjectedGapTriggeredDQ() = default;

protected:

Bool_t importParticles() override
  {
    GeneratorPythia8::importParticles();
    bool genOk = false;
    if (mGeneratedEvents % mInverseTriggerRatio == 0) { // add injected prompt signals to the stack
      bool genOk = false;
      while (!genOk) {    
        genOk =  (mGeneratorParam->generateEvent() && mGeneratorParam->importParticles()) ? true : false ;
      }
      int originalSize = mParticles.size();
      for (int ipart=0; ipart < mGeneratorParam->getParticles().size(); ipart++) {
        TParticle part = TParticle(mGeneratorParam->getParticles().at(ipart));
        if(part.GetFirstMother() >= 0) part.SetFirstMother(part.GetFirstMother() + originalSize);
        if(part.GetFirstDaughter() >= 0) part.SetFirstDaughter(part.GetFirstDaughter() + originalSize);
        if(part.GetLastDaughter() >= 0) part.SetLastDaughter(part.GetLastDaughter() + originalSize);
        mParticles.push_back(part); 
        // encodeParticleStatusAndTracking method already called in GeneratorEvtGen.C 
      }	   
      mGeneratorParam->clearParticles(); 
    }

    mGeneratedEvents++;
    return true;
  }


private:
  Generator* mGeneratorParam; 
  // Control gap-triggering
  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;
};

// Predefined generators:
FairGenerator *GeneratorPythia8InjectedBottomoniaGapTriggered(int inputTriggerRatio, int gentype) {
  auto myGen = new GeneratorPythia8BottomoniaInjectedGapTriggeredDQ(inputTriggerRatio,gentype);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
