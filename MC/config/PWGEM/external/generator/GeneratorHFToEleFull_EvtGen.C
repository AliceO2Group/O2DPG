//
//
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
#include "GeneratorEvtGen.C"


FairGenerator*
GeneratorHFToEleFull_EvtGen(bool forcedecay = true, bool allHF = true)
{

  TString pdgs;
  if (allHF) {
     pdgs = "511;521;531;541;5112;5122;5232;5132;5332;411;421;431;4122;4132;4232;4332";
  } else {
     pdgs = "411;421;431;4122;4132;4232;4332";
  }
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8>();
  TString pathO2table;
  if (allHF) {
     pathO2table  = gSystem->ExpandPathName("$O2DPG_ROOT/MC/config/PWGDQ/pythia8/decayer/switchOffCBhadrons.cfg");
  } else {
     pathO2table  = gSystem->ExpandPathName("$O2DPG_ROOT/MC/config/PWGDQ/pythia8/decayer/switchOffChadrons.cfg");
  }
  gen->readFile(pathO2table.Data());

  std::string spdg;
  TObjArray *obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for(int i=0; i<obj->GetEntriesFast(); i++) {
   spdg = obj->At(i)->GetName();
   gen->AddPdg(std::stoi(spdg),i);
   printf("PDG %d \n",std::stoi(spdg));
  }
  if(forcedecay) gen->SetForceDecay(kEvtSemiElectronic);
  else gen->SetForceDecay(kEvtAll);
  // print debug
  // gen->PrintDebug();

  return gen;
}

