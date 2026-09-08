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
  // generator->setupDpmjet(dpmjetconf);
  return generator;
}
o2::eventgen::GeneratorEvtGen* makeStarlightToEvtGenGenerator(std::string configuration,
                                                               float energyCM,
                                                               int beam1Z,
                                                               int beam1A,
                                                               int beam2Z,
                                                               int beam2A,
                                                               std::string extraParams = "",
                                                               std::string dpmjetconf = "")
{
  auto generator = makeStarlightGenerator(configuration, energyCM, beam1Z, beam1A, beam2Z, beam2A, extraParams, dpmjetconf);
  generator->SetPolarization(1); //Transversal
  generator->SetSizePdg(2);
  generator->AddPdg(443,0);
  generator->AddPdg(100443,1);
  TString pathO2 = gSystem->ExpandPathName("$O2DPG_MC_CONFIG_ROOT/MC/config/PWGUD/external/generator/DecayTablesEvtGen");
  if      (configuration.find("Psi2sToMuPi") != std::string::npos) generator->SetDecayTable(Form("%s/PSI2S.MUMUPIPI.DEC",pathO2.Data()));
  else if (configuration.find("Psi2sToElPi") != std::string::npos) generator->SetDecayTable(Form("%s/PSI2S.EEPIPI.DEC",pathO2.Data()));
  else if (configuration.find("JpsiToElRad") != std::string::npos) gen->SetDecayTable(Form("%s/JPSI.EE.DEC",pathO2.Data()));
  return generator;
}
} // namespace

FairGenerator* GeneratorCocktailStarlightMidy_PbPb5TeV(float energyCM = 5360, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "",std::string dpmjetconf = "")
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();
  auto genCohJpsi = makeStarlightToEvtGenGenerator("kCohJpsiToElRad", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genCohJpsi, 1);
  auto genIncohJpsi = makeStarlightToEvtGenGenerator("kIncohJpsiToElRad", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genIncohJpsi, 1);
  auto genTwoGammaToEl = makeStarlightGenerator("kTwoGammaToElLow", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genTwoGammaToEl, 1);
  auto genCohPsi2S = makeStarlightToEvtGenGenerator("kCohPsi2sToElPi", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genCohPsi2S, 1);
  auto genIncohPsi2S = makeStarlightToEvtGenGenerator("kIncohPsi2sToElPi", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genIncohPsi2S, 1);

  return genCocktailEvtGen;
}

FairGenerator* GeneratorCocktailStarlightCoherentMidy_PbPb5TeV(float energyCM = 5360, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "",std::string dpmjetconf = "")
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();
  auto genCohJpsi = makeStarlightToEvtGenGenerator("kCohJpsiToElRad", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genCohJpsi, 1);
  auto genTwoGammaToEl = makeStarlightGenerator("kTwoGammaToElLow", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genTwoGammaToEl, 1);
  auto genCohPsi2S = makeStarlightToEvtGenGenerator("kCohPsi2sToElPi", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genCohPsi2S, 1);

  return genCocktailEvtGen;
}

FairGenerator* GeneratorCocktailStarlightIncoherentMidy_PbPb5TeV(float energyCM = 5360, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "",std::string dpmjetconf = "")
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();
  auto genIncohJpsi = makeStarlightToEvtGenGenerator("kIncohJpsiToElRad", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genIncohJpsi, 1);
  auto genIncohPsi2S = makeStarlightToEvtGenGenerator("kIncohPsi2sToElPi", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genIncohPsi2S, 1);

  return genCocktailEvtGen;
}

FairGenerator* GeneratorCocktailStarlightCoherentFwdy_PbPb5TeV(float energyCM = 5360, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "",std::string dpmjetconf = "")
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();
  auto genCohJpsi = makeStarlightGenerator("kCohJpsiToMu", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genCohJpsi, 1);
  auto genTwoGammaToEl = makeStarlightGenerator("kTwoGammaToMuLow", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genTwoGammaToEl, 1);
  auto genCohPsi2S = makeStarlightToEvtGenGenerator("kCohPsi2sToMuPi", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genCohPsi2S, 1);

  return genCocktailEvtGen;
}

FairGenerator* GeneratorCocktailStarlightIncoherentFwdy_PbPb5TeV(float energyCM = 5360, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "",std::string dpmjetconf = "")
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();
  auto genIncohJpsi = makeStarlightGenerator("kIncohJpsiToMu", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genIncohJpsi, 1);
  auto genIncohPsi2S = makeStarlightToEvtGenGenerator("kIncohPsi2sToMuPi", energyCM, beam1Z, beam1A, beam2Z, beam2A, extrapars, dpmjetconf);
  genCocktailEvtGen->AddGenerator(genIncohPsi2S, 1);

  return genCocktailEvtGen;
}