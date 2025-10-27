R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGUD/external/generator)
#include "GeneratorEvtGen.C"
#include "GeneratorStarlight.C"

FairGenerator*
  GeneratorStarlightToEvtGen(std::string configuration = "empty",float energyCM = 5020, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "", std::string dpmjetconf = "")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorStarlight_class>();
  gen->selectConfiguration(configuration);
  gen->setCollisionSystem(energyCM, beam1Z, beam1A, beam2Z, beam2A);
  gen->setExtraParams(extrapars);
  gen->setupDpmjet(dpmjetconf);

  if (configuration.find("kTau") != std::string::npos){
    gen->SetSizePdg(2);
    gen->AddPdg(15,0);
    gen->AddPdg(-15,1);
  }
  else if(configuration.find("kDpmjet") != std::string::npos){
    gen->SetSizePdg(14);
    gen->AddPdg( 411,0);
    gen->AddPdg(-411,1);
    gen->AddPdg( 421,2);
    gen->AddPdg(-421,3);
    gen->AddPdg( 413,4);
    gen->AddPdg(-413,5);
    gen->AddPdg( 431,6);
    gen->AddPdg(-431,7);
    gen->AddPdg( 4122,8);
    gen->AddPdg(-4122,9);
    gen->AddPdg( 333,10);
    gen->AddPdg(-333,11);
    gen->AddPdg( 313,12);
    gen->AddPdg(-313,13);
  }
  else{
    gen->SetPolarization(1); //Transversal
    gen->SetSizePdg(3);
    gen->AddPdg(443,0);
    gen->AddPdg(100443,1);
    gen->AddPdg(223,2);
  }

  TString pathO2 = gSystem->ExpandPathName("$O2DPG_MC_CONFIG_ROOT/MC/config/PWGUD/external/generator/DecayTablesEvtGen");
  if      (configuration.find("Psi2sToMuPi") != std::string::npos) gen->SetDecayTable(Form("%s/PSI2S.MUMUPIPI.DEC",pathO2.Data()));
  else if (configuration.find("Psi2sToElPi") != std::string::npos) gen->SetDecayTable(Form("%s/PSI2S.EEPIPI.DEC",pathO2.Data()));
  else if (configuration.find("RhoPrime") != std::string::npos)    gen->SetDecayTable(Form("%s/RHOPRIME.RHOPIPI.DEC",pathO2.Data()));
  else if (configuration.find("OmegaTo3Pi") != std::string::npos)  gen->SetDecayTable(Form("%s/OMEGA.3PI.DEC",pathO2.Data()));
  else if (configuration.find("JpsiToElRad") != std::string::npos) gen->SetDecayTable(Form("%s/JPSI.EE.DEC",pathO2.Data()));
  else if (configuration.find("ToEl3Pi") != std::string::npos) gen->SetDecayTable(Form("%s/TAUTAU.EL3PI.DEC",pathO2.Data()));
  else if (configuration.find("ToPo3Pi") != std::string::npos) gen->SetDecayTable(Form("%s/TAUTAU.PO3PI.DEC",pathO2.Data()));
  else if (configuration.find("ToElMu") != std::string::npos) gen->SetDecayTable(Form("%s/TAUTAU.ELMU.DEC",pathO2.Data()));
  else if (configuration.find("ToElPiPi0") != std::string::npos) gen->SetDecayTable(Form("%s/TAUTAU.ELPI.DEC",pathO2.Data()));
  else if (configuration.find("ToPoPiPi0") != std::string::npos) gen->SetDecayTable(Form("%s/TAUTAU.POPI.DEC",pathO2.Data()));
  else if (configuration.find("Jpsi4Prong") != std::string::npos) gen->SetDecayTable(Form("%s/JPSI.4PRONG.DEC",pathO2.Data()));
  else if (configuration.find("Jpsi6Prong") != std::string::npos) gen->SetDecayTable(Form("%s/JPSI.6PRONG.DEC",pathO2.Data()));
  else if (configuration.find("Dpmjet") != std::string::npos) gen->SetDecayTable(Form("%s/OPENCHARM.DEC",pathO2.Data()));

  return gen;
}
