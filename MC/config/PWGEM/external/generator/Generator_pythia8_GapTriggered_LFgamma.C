R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/external/generator)
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGEM/external/generator)
R__LOAD_LIBRARY(libpythia6)
R__LOAD_LIBRARY(libEGPythia6)
#include "GeneratorEvtGen.C"
#include "GeneratorCocktail.C"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"

using namespace std;
using namespace Pythia8;

namespace o2 {
namespace eventgen {

class CocktailParam : public GeneratorTGenerator {
public:
 CocktailParam(GeneratorParam *thisGenerator)
    : GeneratorTGenerator(thisGenerator->GetName()) {
   setTGenerator(thisGenerator);
 };

  ~CocktailParam() { delete thisGenerator; };

private:
   GeneratorParam *thisGenerator = nullptr;
};

//my generator class
class GeneratorPythia8GapTriggeredLFgamma : public GeneratorPythia8 {

  public:
    GeneratorPythia8GapTriggeredLFgamma() : GeneratorPythia8() {
      mGeneratedEvents = 0;
      mInverseTriggerRatio = 1;
      fGeneratorCocktail = 0x0;
    };

    GeneratorPythia8GapTriggeredLFgamma(int lInputTriggerRatio, float yMin, float yMax, int nPart) : GeneratorPythia8() {
      mGeneratedEvents = 0;
      mInverseTriggerRatio = lInputTriggerRatio;
      // LMee cocktail settings:
      float minPt  = 0;
      float maxPt  = 25;
      float phiMin = 0.;
      float phiMax = 360.;
      Weighting_t weightMode = kNonAnalog;

      //create cocktail generator : pi0, eta
      fGeneratorCocktail = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

      auto decayer = new PythiaDecayerConfig();

      //Param
      GeneratorParamEMlib *emlib = new GeneratorParamEMlib();

      // pi0
      auto genPizero = new GeneratorParam(nPart, emlib, GeneratorParamEMlib::kPizero, "pizero"); // 111
      genPizero->SetName("pizero");
      genPizero->SetMomentumRange(0., 25.);
      genPizero->SetPtRange(minPt, maxPt);
      genPizero->SetYRange(yMin, yMax);
      genPizero->SetPhiRange(phiMin, phiMax);
      genPizero->SetWeighting(weightMode); // flat pt, y and v2 zero 
      genPizero->SetSelectAll(kTRUE);
      genPizero->SetDecayer(decayer);
      genPizero->Init();
      CocktailParam *newgenpizero = new CocktailParam(genPizero);	

      // eta
      auto geneta = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kEta,"eta"); // 221
      geneta->SetName("eta");
      geneta->SetMomentumRange(0., 25.);
      geneta->SetPtRange(minPt, maxPt);
      geneta->SetYRange(yMin, yMax);
      geneta->SetPhiRange(phiMin, phiMax);
      geneta->SetWeighting(weightMode); // flat pt, y and v2 zero 
      geneta->SetSelectAll(kTRUE);
      geneta->SetDecayer(decayer);
      geneta->Init();
      CocktailParam *newgeneta = new CocktailParam(geneta);

      // eta
      auto genk0s = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kK0s,"k0s"); // 310 for feed down
      genk0s->SetName("k0s");
      genk0s->SetMomentumRange(0., 25.);
      genk0s->SetPtRange(minPt, maxPt);
      genk0s->SetYRange(yMin, yMax);
      genk0s->SetPhiRange(phiMin, phiMax);
      genk0s->SetWeighting(weightMode); // flat pt, y and v2 zero 
      genk0s->SetSelectAll(kTRUE);
      genk0s->SetDecayer(decayer);
      genk0s->Init();
      CocktailParam *newgenk0s = new CocktailParam(genk0s);

      cout << "add pi0 for signal" << endl;
      fGeneratorCocktail->AddGenerator(newgenpizero, 1);
      cout << "add eta for signal" << endl;
      fGeneratorCocktail->AddGenerator(newgeneta, 1);
      cout << "add k0s for signal" << endl;
      fGeneratorCocktail->AddGenerator(newgenk0s, 1);

      // print debug
      fGeneratorCocktail->PrintDebug();
      fGeneratorCocktail->Init();

      addSubGenerator(0, "gap mb pythia");
      addSubGenerator(1, "event with injected signals");

    };

    ~GeneratorPythia8GapTriggeredLFgamma() = default;

  protected:
    bool generateEvent() override
    {
      GeneratorPythia8::generateEvent();

      if (mGeneratedEvents % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
        fGeneratorCocktail->generateEvent();
        notifySubGenerator(1);
      } else { // gap event
        notifySubGenerator(0);
      }
      mGeneratedEvents++;
      return true;
    }

    bool importParticles() override
    {
      GeneratorPythia8::importParticles();

      bool genOk = false;
      if ((mGeneratedEvents-1) % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
        fGeneratorCocktail->importParticles();
        int originalSize = mParticles.size();
        for(int ipart=0; ipart < fGeneratorCocktail->getParticles().size(); ipart++){
          TParticle part = TParticle(fGeneratorCocktail->getParticles().at(ipart));
          if(part.GetFirstMother() >= 0) part.SetFirstMother(part.GetFirstMother() + originalSize);
          if(part.GetFirstDaughter() >= 0) part.SetFirstDaughter(part.GetFirstDaughter() + originalSize);
          if(part.GetLastDaughter() >= 0) part.SetLastDaughter(part.GetLastDaughter() + originalSize);
          mParticles.push_back(part);
          // encodeParticleStatusAndTracking method already called in GeneratorEvtGen.C
        }
        fGeneratorCocktail->clearParticles();
      }

      return true;
    }

  private:
    GeneratorEvtGen<GeneratorCocktail> *fGeneratorCocktail;
    // Control gap-triggering
    unsigned long long mGeneratedEvents;
    int mInverseTriggerRatio;
};

} // close eventgen
} // close o2

// Predefined generators: // this function should be called in ini file.
FairGenerator *GeneratorPythia8GapTriggeredLFgamma_ForEM(int inputTriggerRatio = 5, float yMin=-1.2, float yMax=1.2, int nPart = 1) {
  auto myGen = new GeneratorPythia8GapTriggeredLFgamma(inputTriggerRatio, yMin, yMax, nPart);
  return myGen;
}
