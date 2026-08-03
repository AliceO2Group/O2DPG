R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGUD/external/generator)
#include "GeneratorCocktail.C"
#include "GeneratorStarlightToEvtGen.C"

#include <string>

FairGenerator* GeneratorCocktailStarlightMidy_PbPb5TeV()
{
  float energyCM = 5360;
  int beam1Z = 82;
  int beam1A = 208;
  int beam2Z = 82;
  int beam2A = 208;
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorCocktail>();
  auto genCohJpsi = new o2::eventgen::GeneratorStarlightToEvtGen("kCohJpsiToElRad", energyCM, beam1Z, beam1A, beam2Z, beam2A);
  genCocktailEvtGen->AddGenerator(genCohJpsi, 1);
  auto genIncohJpsi = new o2::eventgen::GeneratorStarlightToEvtGen("kIncohJpsiToElRad", energyCM, beam1Z, beam1A, beam2Z, beam2A);
  genCocktailEvtGen->AddGenerator(genIncohJpsi, 1);
  auto genTwoGammaToEl = new o2::eventgen::GeneratorStarlight("kTwoGammaToElLow", energyCM, beam1Z, beam1A, beam2Z, beam2A);
  genCocktailEvtGen->AddGenerator(genTwoGammaToEl, 1);
  auto genCohPsi2S = new o2::eventgen::GeneratorStarlightToEvtGen("kCohPsi2sToElPi", energyCM, beam1Z, beam1A, beam2Z, beam2A);
  genCocktailEvtGen->AddGenerator(genCohPsi2S, 1);
  auto genIncohPsi2S = new o2::eventgen::GeneratorStarlightToEvtGen("kIncohPsi2sToElPi", energyCM, beam1Z, beam1A, beam2Z, beam2A);
  genCocktailEvtGen->AddGenerator(genIncohPsi2S, 1);
  return genCocktailEvtGen;
}