R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGUD/external/generator)
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
#include "GeneratorCocktail.C"
#include "GeneratorStarlight.C"
#include "GeneratorEvtGen.C"
#include <string>

namespace
{
o2::eventgen::GeneratorStarlight_class* makeStarlightGenerator(std::string configuration,
                                                               float energyCM,
                                                               int beam1Z,
                                                               int beam1A,
                                                               int beam2Z,
                                                               int beam2A,
                                                               std::string extraParams = "",
                                                               std::string dpmjetconf = "")
{
  auto generator = new o2::eventgen::GeneratorStarlight_class();
  generator->selectConfiguration(configuration);
  generator->setCollisionSystem(energyCM, beam1Z, beam1A, beam2Z, beam2A);
  generator->setExtraParams(extraParams);
  generator->setupDpmjet(dpmjetconf);
  return generator;
}
} // namespace

FairGenerator* GeneratorCocktailStarlightMidy_PbPb5TeV(float energyCM = 5360, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "",std::string dpmjetconf = "")
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();
  auto genCohJpsi = makeStarlightGenerator("kCohJpsiToElRad", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genCohJpsi, 1);
  auto genIncohJpsi = makeStarlightGenerator("kIncohJpsiToElRad", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genIncohJpsi, 1);
  auto genTwoGammaToEl = makeStarlightGenerator("kTwoGammaToElLow", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genTwoGammaToEl, 1);
  auto genCohPsi2S = makeStarlightGenerator("kCohPsi2sToElPi", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genCohPsi2S, 1);
  auto genIncohPsi2S = makeStarlightGenerator("kIncohPsi2sToElPi", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genIncohPsi2S, 1);

  TString pdgs = "443;100443";
  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  genCocktailEvtGen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    genCocktailEvtGen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  genCocktailEvtGen->SetForceDecay(kEvtPsiPrimeJpsiDiElectron);
  return genCocktailEvtGen;
}