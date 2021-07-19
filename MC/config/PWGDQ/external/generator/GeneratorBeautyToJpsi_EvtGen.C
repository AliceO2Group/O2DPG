// usage (fwdy) :
//o2-sim -j 4 -n 10 -g external -m "PIPE ITS TPC" -o sgn --configKeyValues "GeneratorExternal.fileName=GeneratorBeautyToJpsi_EvtGen.C;GeneratorExternal.funcName=GeneratorBeautyToJpsi_EvtGenFwdY()" --configFile GeneratorHF_bbbar_fwdy.ini 
// usage (midy) :
//o2-sim -j 4 -n 10 -g external -m "PIPE ITS TPC" -o sgn --configKeyValues "GeneratorExternal.fileName=GeneratorBeautyToJpsi_EvtGen.C;GeneratorExternal.funcName=GeneratorBeautyToJpsi_EvtGenMidY()" --configFile GeneratorHF_bbbar_midy.ini 
//
//
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGHF/external/generator)
#include "GeneratorEvtGen.C"
#include "GeneratorHF.C"

FairGenerator*
GeneratorBeautyToJpsi_EvtGenMidY(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false, TString pdgs = "511;521;531;5112;5122;5232;5132")
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
  gen->SetForceDecay(kEvtBJpsiDiElectron);
  // print debug
  // gen->PrintDebug();

  return gen;
}

FairGenerator*
GeneratorBeautyToJpsi_EvtGenFwdY(double rapidityMin = -4.3, double rapidityMax = -2.2, bool verbose = false, TString pdgs = "511;521;531;5112;5122;5232;5132")
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
  gen->SetForceDecay(kEvtBJpsiDiMuon);
  // print debug
  // gen->PrintDebug();

  return gen;
}

