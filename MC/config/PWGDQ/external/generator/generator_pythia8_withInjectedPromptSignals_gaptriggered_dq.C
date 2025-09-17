#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include "GeneratorPromptCharmonia.C"
#include <string>

using namespace o2::eventgen;
using namespace Pythia8;

class GeneratorPythia8PromptInjectedGapTriggeredDQ : public o2::eventgen::GeneratorPythia8 {
public:

  /// default constructor
  GeneratorPythia8PromptInjectedGapTriggeredDQ() = default;

  /// constructor
  GeneratorPythia8PromptInjectedGapTriggeredDQ(int inputTriggerRatio = 5, int gentype = 0) {

    mGeneratedEvents = 0;
    mGeneratorParam = 0x0;
    mInverseTriggerRatio = inputTriggerRatio; 
    switch (gentype) {
      case 0: // generate prompt jpsi + psi2s cocktail at midrapidity
        mGeneratorParam = (Generator*)GeneratorCocktailPromptCharmoniaToElectronEvtGen_pp13TeV(); 
        break;
      case 1: // generate prompt jpsi at midrapidity
        mGeneratorParam = (Generator*)GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV("443"); 
        break;
      case 2: // generate prompt psi2S at midrapidity
        mGeneratorParam = (Generator*)GeneratorParamPromptPsiToElectronEvtGen_pp13TeV("100443"); 
        break;
      case 3: // generate prompt jpsi + psi2s cocktail at forward rapidity
        mGeneratorParam = (Generator*)GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp13TeV();
        break;
      case 4: // generate prompt jpsi at forward rapidity
        mGeneratorParam = (Generator*)GeneratorParamPromptJpsiToMuonEvtGen_pp13TeV("443");
        break;
      case 5: // generate prompt psi2S at forward rapidity
        mGeneratorParam = (Generator*)GeneratorParamPromptPsiToMuonEvtGen_pp13TeV("100443");
        break;
      case 6: // generate prompt ChiC1 + ChiC2 cocktail at midrapidity
        mGeneratorParam = (Generator*)GeneratorCocktailChiCToElectronEvtGen_pp13TeV(); 
        break;
      case 7: // generate prompt charmonia cocktail at forward rapidity at 5TeV
        mGeneratorParam = (Generator*)GeneratorCocktailPromptCharmoniaToMuonEvtGen_PbPb5TeV(); 
        break;
      case 8: // generate prompt X_1(3872) to Jpsi pi pi at midrapidity
        mGeneratorParam = (Generator*)GeneratorParamX3872ToJpsiEvtGen_pp13TeV("9920443");
        break;
      case 9: // generate prompt psi2S to Jpsi pi pi at midrapidity
        mGeneratorParam = (Generator*)GeneratorParamPromptPsiToJpsiPiPiEvtGen_pp13TeV("100443");
        break;
      case 10: // generate cocktail of prompt X_1(3872) and psi2S to Jpsi pi pi at midrapidity
        mGeneratorParam = (Generator*)GeneratorCocktailX3872AndPsi2StoJpsi_pp13TeV();
        break;
      case 11: // generate prompt charmonium at forward rapidity at 5TeV
        mGeneratorParam = (Generator*)GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp5TeV();
        break; 
      case 12: // generate prompt charmonia cocktail at mid rapidity at 5TeV
        mGeneratorParam = (Generator*)GeneratorCocktailPromptCharmoniaToElectronEvtGen_pp5TeV();
        break; 
      case 13: // generate prompt charmonia cocktail at fwd rapidity at 9.6TeV
        mGeneratorParam = (Generator*)GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp96TeV();
        break; 
      case 14: // generate prompt charmonia cocktail at mid rapidity at 9.6TeV
        mGeneratorParam = (Generator*)GeneratorCocktailPromptCharmoniaToElectronEvtGen_pp96TeV();
        break; 
      }
    mGeneratorParam->Init();  
  }

  ///  Destructor
  ~GeneratorPythia8PromptInjectedGapTriggeredDQ() = default;

protected:

Bool_t importParticles() override
  {
    GeneratorPythia8::importParticles();
    bool genOk = false;
    if (mGeneratedEvents % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
    bool genOk = false;
    while (!genOk){    
    genOk =  (mGeneratorParam->generateEvent() && mGeneratorParam->importParticles()) ? true : false ;
    }
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
FairGenerator *GeneratorPythia8InjectedPromptCharmoniaGapTriggered(int inputTriggerRatio, int gentype) {
  auto myGen = new GeneratorPythia8PromptInjectedGapTriggeredDQ(inputTriggerRatio,gentype);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
