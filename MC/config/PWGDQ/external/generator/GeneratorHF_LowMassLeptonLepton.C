// 
//o2-sim -j 1 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHFbb_lowMassEE.ini (GeneratorHFbb_lowMassMuMu.ini)  -> bb -> e+e- (bb -> mu+mu-)
//o2-sim -j 1 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHFcc_lowMassEE.ini (GeneratorHFbb_lowMassMuMu.ini) -> cc -> e+e- (cc -> mu+mu-)
//o2-sim -j 1 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHFbtoc_lowMassEE.ini (GeneratorHFbtoc_lowMassMuMu.ini) -> b->e, b->c->e (b->mu, b->c->mu) 
//

R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGHF/external/generator)
#include "GeneratorHF.C"

enum LMeeType { kBBtoLL=0, kCCtoLL, kBandCToLL}; 

FairGenerator*
GeneratorHF_LowMassLeptonLepton(Int_t kTypeLowMassHF = kBBtoLL, Bool_t isDielectron = kTRUE, double rapidityMin = -1.5, double rapidityMax = 1.5, bool ispp = true, bool verbose = false)
{

  //
  // generate LMee and LMmumu cocktails from HF. Different sources can be generated:
  // 1) kBBtoLL -> unlike sign lepton pairs from bb ( -> lepton^+ lepton^-)
  // 2) kCCtoLL -> unlike sign lepton pairs from cc ( -> lepton^+ lepton^-)
  // 3) kBandCToLL -> like / unlike sign lepton pairs from b->lepton + b->c->lepton
  // 
  auto gen = new o2::eventgen::GeneratorHF();
  
  if(kTypeLowMassHF == kBBtoLL || kTypeLowMassHF == kBandCToLL) gen->setPDG(5);
  else if(kTypeLowMassHF == kCCtoLL) gen->setPDG(4);
  else { printf("unknow case, please check! \n"); return 0x0; }
  
  gen->setRapidity(rapidityMin,rapidityMax);
  gen->setVerbose(verbose);

  TString pathO2 = gSystem->ExpandPathName("$O2DPG_ROOT/MC/config/PWGDQ/pythia8/decayer");

  TString decayTableType = "Muonic"; 
  if(isDielectron) decayTableType = "Electronic";

  if(kTypeLowMassHF == kBBtoLL) gen->readFile(Form("%s/force_semi%sB.cfg",pathO2.Data(),decayTableType.Data()));
  else if(kTypeLowMassHF == kCCtoLL) gen->readFile(Form("%s/force_semi%sC.cfg",pathO2.Data(),decayTableType.Data()));

  if(ispp) gen->setFormula("1");
  else gen->setFormula("max(1.,120.*(x<5.)+80.*(1.-x/20.)*(x>5.)*(x<11.)+240.*(1.-x/13.)*(x>11.))");
  
  return gen;
}


