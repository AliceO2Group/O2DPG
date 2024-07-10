// usage (fwdy) :
//o2-sim -j 4 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHF_bbbar_fwdy.ini 
// usage (midy) :
//o2-sim -j 4 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHF_bbbar_midy.ini 
//
//
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGHF/external/generator)
#include "GeneratorEvtGen.C"
#include "GeneratorHF.C"


FairGenerator*
GeneratorCharmToEle_EvtGen(double rapidityMin = -2., double rapidityMax = 2., bool ispp = true, bool verbose = false, TString pdgs = "411;421;431;4122;4132;4232;4332")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorHF>();
  gen->setRapidity(rapidityMin,rapidityMax);
  gen->setPDG(4);
  TString pathO2table = gSystem->ExpandPathName("$O2DPG_ROOT/MC/config/PWGDQ/pythia8/decayer/switchOffChadrons.cfg");
  gen->readFile(pathO2table.Data());

  gen->setVerbose(verbose);
  if(ispp) gen->setFormula("1");
  else gen->setFormula("max(1.,120.*(x<5.)+80.*(1.-x/20.)*(x>5.)*(x<11.)+240.*(1.-x/13.)*(x>11.))");
  std::string spdg;
  TObjArray *obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for(int i=0; i<obj->GetEntriesFast(); i++) {
   spdg = obj->At(i)->GetName();
   gen->AddPdg(std::stoi(spdg),i);
   printf("PDG %d \n",std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtSemiElectronic);
  // print debug
  // gen->PrintDebug();

  return gen;
}

