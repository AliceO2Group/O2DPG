//o2-sim -j 1 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configKeyValues "GeneratorExternal.fileName=GeneratorBplusToJpsiKaon_EvtGen.C;GeneratorExternal.funcName=GeneratorBplusToJpsiKaon_EvtGen()" --configFile GeneratorHF_bbbarToBplus_midy.ini 
//
//
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGHF/external/generator)
#include "GeneratorEvtGen.C"
#include "GeneratorHF.C"

FairGenerator*
GeneratorBplusToJpsiKaon_EvtGen(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false, TString pdgs = "521")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorHF>(); 
  gen->setRapidity(rapidityMin,rapidityMax);
  gen->setPDG(5);

  gen->setVerbose(verbose);
  gen->setFormula("max(1.,120.*(x<5.)+80.*(1.-x/20.)*(x>5.)*(x<11.)+240.*(1.-x/13.)*(x>11.))");
  std::string spdg;
  TObjArray *obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for(int i=0; i<obj->GetEntriesFast(); i++) {
   spdg = obj->At(i)->GetName();
   gen->AddPdg(std::stoi(spdg),i);
   printf("PDG %d \n",std::stoi(spdg));
  }
 
  TString pathO2 = gSystem->ExpandPathName("$O2DPG_ROOT/MC/config/PWGDQ/EvtGen/DecayTablesEvtgen");
  gen->SetDecayTable(Form("%s/BPLUSTOKAONJPSITOELE.DEC",pathO2.Data()));
  // print debug
  //gen->PrintDebug();

  return gen;
}

