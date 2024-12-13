// usage (fwdy) :
//o2-sim -j 4 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHF_bbbar_fwdy.ini 
// usage (midy) :
//o2-sim -j 4 -n 10 -g external -t external -m "PIPE ITS TPC" -o sgn --configFile GeneratorHF_bbbar_midy.ini 
//
//
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGHF/external/generator)
#include "GeneratorEvtGen.C"
#include "GeneratorHF.C"


FairGenerator*
GeneratorBeautyToEle_EvtGen(double rapidityMin = -2., double rapidityMax = 2., bool ispp = true, bool forcedecay = true, bool verbose = false, TString pdgs = "511;521;531;541;5112;5122;5232;5132;5332;411;421;431;4122;4132;4232;4332")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorHF>();
  gen->setRapidity(rapidityMin,rapidityMax);
  gen->setPDG(5);
  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffCBhadrons.cfg");
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
  if(forcedecay) gen->SetForceDecay(kEvtSemiElectronic);
  else gen->SetForceDecay(kEvtAll);
   //}
  // set random seed
  gen->readString("Random:setSeed on");
  uint random_seed;
  unsigned long long int random_value = 0; 
  ifstream urandom("/dev/urandom", ios::in|ios::binary);
  urandom.read(reinterpret_cast<char*>(&random_value), sizeof(random_seed));
  gen->readString(Form("Random:seed = %d", random_value % 900000001));
  // print debug
  // gen->PrintDebug();

  return gen;
}

