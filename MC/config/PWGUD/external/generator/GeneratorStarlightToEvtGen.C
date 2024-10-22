// usage (fwdy) :
// o2-sim -j 4 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHF_bbbar_fwdy.ini
// usage (midy) :
// o2-sim -j 4 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHF_bbbar_midy.ini
//
//
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGUD/external/generator)
#include "GeneratorEvtGen.C"
#include "GeneratorStarlight.C"

FairGenerator*
  GeneratorStarlightToEvtGen(std::string configuration = "empty",float energyCM = 5020, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208)
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorStarlight_class>();
  gen->selectConfiguration(configuration);
  gen->setCollisionSystem(energyCM, beam1Z, beam1A, beam2Z, beam2A);
  
  gen->SetSizePdg(5);
  gen->AddPdg(443,0);
  gen->AddPdg(100443,1);
  gen->AddPdg(223,2);
  gen->AddPdg(15,3);
  gen->AddPdg(-15,4);
  if (configuration.find("kTau") == std::string::npos) gen->SetPolarization(1); //Transversal
  
  TString pathO2 = gSystem->ExpandPathName("$O2DPG_ROOT/MC/config/PWGUD/external/generator/DecayTablesEvtGen");
  if      (configuration.find("Psi2sToMuPi") != std::string::npos) gen->SetDecayTable(Form("%s/PSI2S.MUMUPIPI.DEC",pathO2.Data()));
  else if (configuration.find("Psi2sToElPi") != std::string::npos) gen->SetDecayTable(Form("%s/PSI2S.EEPIPI.DEC",pathO2.Data()));
  else if (configuration.find("RhoPrime") != std::string::npos)    gen->SetDecayTable(Form("%s/RHOPRIME.RHOPIPI.DEC",pathO2.Data()));
  else if (configuration.find("OmegaTo3Pi") != std::string::npos)  gen->SetDecayTable(Form("%s/OMEGA.3PI.DEC",pathO2.Data()));
  else if (configuration.find("JpsiToElRad") != std::string::npos) gen->SetDecayTable(Form("%s/JPSI.EE.DEC",pathO2.Data()));
  else if (configuration.find("ToEl3Pi") != std::string::npos) gen->SetDecayTable(Form("%s/TAUTAU.EL3PI.DEC",pathO2.Data()));
  else if (configuration.find("ToPo3Pi") != std::string::npos) gen->SetDecayTable(Form("%s/TAUTAU.PO3PI.DEC",pathO2.Data()));
 
  return gen;
}
