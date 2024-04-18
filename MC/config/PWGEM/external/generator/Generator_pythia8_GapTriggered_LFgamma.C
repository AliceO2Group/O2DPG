R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/external/generator)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGEM/external/generator)
R__LOAD_LIBRARY(libpythia6)
R__LOAD_LIBRARY(libEGPythia6)
#include "GeneratorCocktailWithGap.C"
#include "GeneratorEvtGen.C"

using namespace std;
using namespace Pythia8;

namespace o2 {
namespace eventgen {

class CocktailParam : public GeneratorTGenerator {
public:
 CocktailParam(GeneratorParam *thisGenerator)
    //: GeneratorTGenerator("thisGenerator") {
    : GeneratorTGenerator(thisGenerator->GetName()) {
   setTGenerator(thisGenerator);
 };

  ~CocktailParam() { delete thisGenerator; };

private:
   GeneratorParam *thisGenerator = nullptr;
};

} // close eventgen
} // close o2

// Predefined generators:
// this function should be called in ini file.
FairGenerator *GeneratorPythia8GapTriggeredLFgamma_ForEM(TString configsignal = "$O2DPG_ROOT/MC/config/PWGEM/pythia8/generator/pythia8_MB_gapevent.cfg", int inputTriggerRatio = 5, float yMin=-1.2, float yMax=1.2, int nPart = 1) {
  printf("configsignal = %s\n", configsignal.Data());

  //create cocktail generator : mb pythia8, pi0, eta, eta', rho, omega, phi, j/psi, psi(2s)
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktailWithGap>();
  genCocktailEvtGen->setInputTriggerRatio(inputTriggerRatio);

  // // EXODUS decayer
  TString O2DPG_ROOT = TString(getenv("O2DPG_ROOT"));
  auto decayer = new PythiaDecayerConfig();
  decayer->SetDecayerExodus();
  TString useLMeeDecaytable = "$O2DPG_ROOT/MC/config/PWGEM/decaytables/decaytable_LMee.dat";
  useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("$O2DPG_ROOT",O2DPG_ROOT);
  useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("${O2DPG_ROOT}",O2DPG_ROOT);
  decayer->SetDecayTableFile(useLMeeDecaytable.Data());
  decayer->ReadDecayTable();

  // pythia8
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  o2::eventgen::GeneratorPythia8* mb_p8 = new o2::eventgen::GeneratorPythia8("mb_p8", "mb_p8");
  configsignal = configsignal.ReplaceAll("$O2DPG_ROOT",O2DPG_ROOT);
  configsignal = configsignal.ReplaceAll("${O2DPG_ROOT}",O2DPG_ROOT);
  mb_p8->readFile(configsignal.Data());
  mb_p8->readString("Random:setSeed on");
  mb_p8->readString("Random:seed " + std::to_string(seed));
  mb_p8->Init();

  cout << "add mb pythia8 for gap" << endl;
  genCocktailEvtGen->addGeneratorGap(mb_p8, 1);

  cout << "add mb pythia8 for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(mb_p8, 1);

  //Param
  GeneratorParamEMlib *emlib = new GeneratorParamEMlib();

  // LMee cocktail settings:
  float minPt  = 0;
  float maxPt  = 25;
  float minRap = yMin;
  float maxRap = yMax;
  float phiMin = 0.;
  float phiMax = 360.;
  Weighting_t weightMode = kNonAnalog;

  // pi0
  auto genPizero = new GeneratorParam(nPart, emlib, GeneratorParamEMlib::kPizero, "pizero"); // 111
  genPizero->SetName("pizero");
  genPizero->SetMomentumRange(0., 1.e6);
  genPizero->SetPtRange(minPt, maxPt);
  genPizero->SetYRange(minRap, maxRap);
  genPizero->SetPhiRange(phiMin, phiMax);
  genPizero->SetWeighting(weightMode); // flat pt, y and v2 zero 
  genPizero->SetDecayer(decayer); // EXODUS
  genPizero->SetForceDecay(kAll);
  genPizero->SetForceGammaConversion(kFALSE);
  genPizero->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
  genPizero->Init();
  CocktailParam *newgenpizero = new CocktailParam(genPizero);	

  // eta
  auto geneta = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kEta,"eta"); // 221
  geneta->SetName("eta");
  geneta->SetMomentumRange(0., 1.e6);
  geneta->SetPtRange(minPt, maxPt);
  geneta->SetYRange(minRap, maxRap);
  geneta->SetPhiRange(phiMin, phiMax);
  geneta->SetWeighting(weightMode); // flat pt, y and v2 zero 
  geneta->SetDecayer(decayer); // EXODUS
  geneta->SetForceDecay(kAll);
  geneta->SetForceGammaConversion(kFALSE);
  geneta->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
  geneta->Init();
  CocktailParam *newgeneta = new CocktailParam(geneta);

  cout << "add pi0 for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(newgenpizero, 1);
  cout << "add eta for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(newgeneta, 1);

  // print debug
  genCocktailEvtGen->PrintDebug();

  return genCocktailEvtGen;
}

