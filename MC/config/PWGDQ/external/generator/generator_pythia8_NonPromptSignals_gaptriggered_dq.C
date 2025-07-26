#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"

R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
#include "GeneratorEvtGen.C"

#include <string>

using namespace o2::eventgen;

namespace o2
{
namespace eventgen
{

class GeneratorPythia8NonPromptInjectedGapTriggeredDQ : public o2::eventgen::GeneratorPythia8 {
public:
  
  /// constructor
  GeneratorPythia8NonPromptInjectedGapTriggeredDQ(int inputTriggerRatio = 5)  {

    mGeneratedEvents = 0;
    mInverseTriggerRatio = inputTriggerRatio; 
    // define minimum bias event generator
    auto seed = (gRandom->TRandom::GetSeed() % 900000000);
    TString pathconfigMB = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/generator/pythia8_inel_triggerGap.cfg");
    pythiaMBgen.readFile(pathconfigMB.Data());
    pythiaMBgen.readString("Random:setSeed on");
    pythiaMBgen.readString("Random:seed " + std::to_string(seed));
    mConfigMBdecays = "";        
    mPDG = 5; 
    mRapidityMin = -1.;
    mRapidityMax = 1.;
    mHadronMultiplicity = -1; 
    mHadronRapidityMin = -1.;
    mHadronRapidityMax = 1.;  
    mVerbose = false; 
  }

  ///  Destructor
  ~GeneratorPythia8NonPromptInjectedGapTriggeredDQ() = default;

  void setPDG(int val) { mPDG = val; };
  void addHadronPDGs(int pdg) { mHadronsPDGs.push_back(pdg); };
  void setHadronMultiplicity(int val) { mHadronMultiplicity = val; };
  void setRapidity(double valMin, double valMax)
  {
    mRapidityMin = valMin;
    mRapidityMax = valMax;
  };

  void setRapidityHadron(double valMin, double valMax)
  {
    mHadronRapidityMin = valMin;
    mHadronRapidityMax = valMax;
  };

  void setConfigMBdecays(TString val){mConfigMBdecays = val;}

  void setVerbose(bool val) { mVerbose = val; };

protected:

Bool_t generateEvent() override
  {
     // reset  event
     bool genOk = false;
     if (mGeneratedEvents % mInverseTriggerRatio == 0){
       bool ancestor = false;
       while (! (genOk && ancestor) ){
         /// reset event
         mPythia.event.reset();
         genOk = GeneratorPythia8::generateEvent(); 
         // find the q-qbar ancestor
         ancestor = findHeavyQuarkPair(mPythia.event);
       }
     } else {
       /// reset event
       pythiaMBgen.event.reset();
       while (!genOk) {
        genOk = pythiaMBgen.next();
       }
       mPythia.event = pythiaMBgen.event;
     }
    mGeneratedEvents++; 
    if (mVerbose)  mOutputEvent.list();
    return true;
  }

Bool_t Init() override
  {
        if(mConfigMBdecays.Contains("cfg")) pythiaMBgen.readFile(mConfigMBdecays.Data());	
	GeneratorPythia8::Init();
       	pythiaMBgen.init();
        return true;
  } 

  // search for q-qbar mother with at least one q in a selected rapidity window
  bool findHeavyQuarkPair(Pythia8::Event& event)
  { 
    int countH[mHadronsPDGs.size()]; for(int ipdg=0; ipdg < mHadronsPDGs.size(); ipdg++) countH[ipdg]=0;
    bool hasq = false, hasqbar = false, atSelectedY = false, isOkAtPartonicLevel = false;
    for (int ipa = 0; ipa < event.size(); ++ipa) {
      
      if(!isOkAtPartonicLevel){    
      auto daughterList = event[ipa].daughterList();
      hasq = false; hasqbar = false; atSelectedY = false; 
      for (auto ida : daughterList) {
        if (event[ida].id() == mPDG)
          hasq = true;
        if (event[ida].id() == -mPDG)
          hasqbar = true;
        if ((event[ida].y() > mRapidityMin) && (event[ida].y() < mRapidityMax))
          atSelectedY = true;
        }
        if (hasq && hasqbar && atSelectedY) isOkAtPartonicLevel = true;
      }

      if( (mHadronMultiplicity <= 0) && isOkAtPartonicLevel) return true;  // no selection at hadron level
    
      /// check at hadron level if needed 
      int ipdg=0;
      for (auto& pdgVal : mHadronsPDGs){
             if ( (TMath::Abs(event[ipa].id()) == pdgVal) && (event[ipa].y() > mHadronRapidityMin) && (event[ipa].y() < mHadronRapidityMax) )   countH[ipdg]++; 
             if(isOkAtPartonicLevel && countH[ipdg] >= mHadronMultiplicity) return true;
	     ipdg++;
        }
      }
    return false;
  };


private:
// Interface to override import particles
Pythia8::Event mOutputEvent;

  // Control gap-triggering
  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;
  Pythia8::Pythia pythiaMBgen; // minimum bias event  
  TString mConfigMBdecays;		
  int mPDG;
  std::vector<int> mHadronsPDGs;
  int mHadronMultiplicity;
  double mRapidityMin; 
  double mRapidityMax;
  double mHadronRapidityMin;
  double mHadronRapidityMax;
  bool mVerbose;
  };

}

}

// Predefined generators:
FairGenerator*
  GeneratorBeautyToJpsi_EvtGenMidY(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false, TString pdgs = "511;521;531;541;5112;5122;5232;5132;5332")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8NonPromptInjectedGapTriggeredDQ>();
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setPDG(5);
  gen->setRapidityHadron(-1.5,1.5);
  gen->setHadronMultiplicity(1);
  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffBhadrons.cfg");
  gen->readFile(pathO2table.Data());
  gen->setConfigMBdecays(pathO2table);
  gen->setVerbose(verbose);
  
  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    gen->addHadronPDGs(std::stoi(spdg));
    printf("PDG %d \n", std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtBJpsiDiElectron);

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

FairGenerator*
  GeneratorBeautyToPsiAndJpsi_EvtGenMidY(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false, TString pdgs = "511;521;531;541;5112;5122;5232;5132;5332")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8NonPromptInjectedGapTriggeredDQ>();
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setPDG(5);
  gen->setRapidityHadron(rapidityMin,rapidityMax);
  gen->setHadronMultiplicity(1);
  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffBhadrons.cfg");
  gen->readFile(pathO2table.Data());
  gen->setConfigMBdecays(pathO2table);
  gen->setVerbose(verbose);

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
    gen->addHadronPDGs(std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtBPsiAndJpsiDiElectron);

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

FairGenerator*
  GeneratorBplusToJpsiKaon_EvtGen(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false, TString pdgs = "511;521;531;541;5112;5122;5232;5132;5332")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8NonPromptInjectedGapTriggeredDQ>();
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setPDG(5);
  //gen->addHadronPDGs(521);
  gen->setRapidityHadron(rapidityMin,rapidityMax);
  gen->setHadronMultiplicity(2);
  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffBhadrons.cfg");
  gen->readFile(pathO2table.Data());
  gen->setConfigMBdecays(pathO2table); 
  gen->setVerbose(true);
  
  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    gen->addHadronPDGs(std::stoi(spdg));
    printf("PDG %d \n", std::stoi(spdg));
  }
  
  TString pathO2 = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/EvtGen/DecayTablesEvtgen");
  //gen->SetDecayTable(Form("%s/BPLUSTOKAONJPSITOELE.DEC", pathO2.Data()));
  //gen->SetDecayTable(Form("%s/BPLUSTOKAONJPSITOELEALLMODES.DEC", pathO2.Data())); // decay table including decay modes for correlated background
  gen->SetDecayTable(Form("%s/BTOJPSITOELE.DEC", pathO2.Data())); // decay table including decay modes for correlated background
  // print debug
  // gen->PrintDebug();
  // set random seed
  gen->readString("Random:setSeed on");
  uint random_seed;
  unsigned long long int random_value = 0;
  ifstream urandom("/dev/urandom", ios::in|ios::binary);
  urandom.read(reinterpret_cast<char*>(&random_value), sizeof(random_seed));
  gen->readString(Form("Random:seed = %d", random_value % 900000001));
   
  return gen;
}

// Predefined generators:
FairGenerator*
  GeneratorBeautyToJpsi_EvtGenFwdY(double rapidityMin = -4.3, double rapidityMax = -2.3, bool verbose = false, TString pdgs = "511;521;531;541;5112;5122;5232;5132;5332")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8NonPromptInjectedGapTriggeredDQ>();
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setPDG(5);
  gen->setRapidityHadron(rapidityMin,rapidityMax);
  gen->setHadronMultiplicity(1);
  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffBhadrons.cfg");
  gen->readFile(pathO2table.Data());
  gen->setConfigMBdecays(pathO2table);
  gen->setVerbose(verbose);

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    gen->addHadronPDGs(std::stoi(spdg));
    printf("PDG %d \n", std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtBJpsiDiMuon);

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


FairGenerator*
  GeneratorBeautyToPsiAndJpsi_EvtGenFwdY(double rapidityMin = -4.3, double rapidityMax = -2.3, bool verbose = false, TString pdgs = "511;521;531;541;5112;5122;5232;5132;5332")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8NonPromptInjectedGapTriggeredDQ>();
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setPDG(5);
  gen->setRapidityHadron(rapidityMin,rapidityMax);
  gen->setHadronMultiplicity(1);
  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffBhadrons.cfg");
  gen->readFile(pathO2table.Data());
  gen->setConfigMBdecays(pathO2table);
  gen->setVerbose(verbose);

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
    gen->addHadronPDGs(std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtBPsiAndJpsiDiMuon);

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

FairGenerator*
  GeneratorBeautyToPsiToJpsi_EvtGenMidY(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false, TString pdgs = "511;521;531;541;5112;5122;5232;5132;5332")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8NonPromptInjectedGapTriggeredDQ>();
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setPDG(5);
  gen->setRapidityHadron(rapidityMin,rapidityMax);
  gen->setHadronMultiplicity(1);
  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffBhadrons.cfg");
  gen->readFile(pathO2table.Data());
  gen->setConfigMBdecays(pathO2table);
  gen->setVerbose(verbose);

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
    gen->addHadronPDGs(std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtBtoPsi2SToJpsiPiPi);

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

