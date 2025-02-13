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

class GeneratorPythia8HadronTriggeredWithGap : public o2::eventgen::GeneratorPythia8 {
public:
  
  /// constructor
  GeneratorPythia8HadronTriggeredWithGap(int inputTriggerRatio = 5)  {

    mGeneratedEvents = 0;
    mInverseTriggerRatio = inputTriggerRatio;
    // define minimum bias event generator
    auto seed = (gRandom->TRandom::GetSeed() % 900000000);
    // main physics option for the min bias pythia events: SoftQCD:Inelastic
    TString pathconfigMB = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/generator/pythia8_inel_triggerGap.cfg");
    pythiaMBgen.readFile(pathconfigMB.Data());
    pythiaMBgen.readString("Random:setSeed on");
    pythiaMBgen.readString("Random:seed " + std::to_string(seed));
    mConfigMBdecays = "";
    mRapidityMin = -1.;
    mRapidityMax = 1.;
    mVerbose = false; 
  }

  ///  Destructor
  ~GeneratorPythia8HadronTriggeredWithGap() = default;

  void addHadronPDGs(int pdg) { mHadronsPDGs.push_back(pdg); };

  void setRapidityRange(double valMin, double valMax)
  {
    mRapidityMin = valMin;
    mRapidityMax = valMax;
  };

  void setTriggerGap(int triggerGap) {mInverseTriggerRatio = triggerGap;}

  void setConfigMBdecays(TString val){mConfigMBdecays = val;}

  void setVerbose(bool val) { mVerbose = val; };

protected:

bool generateEvent() override {
  // reset  event
  bool genOk = false;
  if (mGeneratedEvents % mInverseTriggerRatio == 0) {
    bool found = false;
    while (! (genOk && found)) {
      /// reset event
      mPythia.event.reset();
      genOk = GeneratorPythia8::generateEvent(); 
      // find the q-qbar or single hadron ancestor
      found = findHadrons(mPythia.event);
    }
    notifySubGenerator(1);
  } else {
    /// reset event
    pythiaMBgen.event.reset();
    while (!genOk) {
      genOk = pythiaMBgen.next();
    }
    mPythia.event = pythiaMBgen.event;
    notifySubGenerator(0);
  }
  mGeneratedEvents++; 
  if (mVerbose) { 
    mOutputEvent.list();
  }
  return true;
}

bool Init() override {
        
  if(mConfigMBdecays.Contains("cfg")) {
    pythiaMBgen.readFile(mConfigMBdecays.Data());	
  }
  addSubGenerator(0, "Minimum bias");
  addSubGenerator(1, "Hadron triggered");
	GeneratorPythia8::Init();
  pythiaMBgen.init();
  return true;
} 

// search for the presence of at least one of the required hadrons in a selected rapidity window
bool findHadrons(Pythia8::Event& event) { 
   
  for (int ipa = 0; ipa < event.size(); ++ipa) {
    
    auto daughterList = event[ipa].daughterList();
  
    for (auto ida : daughterList) {
      for (int pdg : mHadronsPDGs) {   // check that at least one of the pdg code is found in the event
        if (event[ida].id() == pdg) {
          if ((event[ida].y() > mRapidityMin) && (event[ida].y() < mRapidityMax)) {
            cout << "============= Found jpsi y,pt " <<  event[ida].y() << ", " << event[ida].pT() << endl;
            std::vector<int> daughters = event[ida].daughterList();
            for (int d : daughters) {
              cout << "###### daughter " << d << ": code " << event[d].id() << ", pt " << event[d].pT() << endl;
            }
            return true;
          }
        }
      }
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
  std::vector<int> mHadronsPDGs;
  double mRapidityMin; 
  double mRapidityMax;
  bool mVerbose;
};

}

}

// Predefined generators:
FairGenerator*
  GeneratorInclusiveJpsi_EvtGenMidY(int triggerGap, double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false)
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8HadronTriggeredWithGap>();
  gen->setTriggerGap(triggerGap);
  gen->setRapidityRange(rapidityMin, rapidityMax);
  gen->addHadronPDGs(443);
  gen->setVerbose(verbose);

  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffJpsi.cfg");
  gen->readFile(pathO2table.Data());
  gen->setConfigMBdecays(pathO2table);
  gen->PrintDebug(true);

  gen->SetSizePdg(1);
  gen->AddPdg(443, 0);

  gen->SetForceDecay(kEvtDiElectron);

  // set random seed
  gen->readString("Random:setSeed on");
  uint random_seed;
  unsigned long long int random_value = 0;
  ifstream urandom("/dev/urandom", ios::in|ios::binary);
  urandom.read(reinterpret_cast<char*>(&random_value), sizeof(random_seed));
  gen->readString(Form("Random:seed = %llu", random_value % 900000001));

  // print debug
  // gen->PrintDebug();

  return gen;

}

// Predefined generators:
FairGenerator*
  GeneratorInclusiveJpsiPsi2S_EvtGenMidY(int triggerGap, double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false)
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8HadronTriggeredWithGap>();
  gen->setTriggerGap(triggerGap);
  gen->setRapidityRange(rapidityMin, rapidityMax);
  gen->addHadronPDGs(443);
  gen->addHadronPDGs(100443);
  gen->setVerbose(verbose);

  TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffJpsi.cfg");
  gen->readFile(pathO2table.Data());
  gen->setConfigMBdecays(pathO2table);
  gen->PrintDebug(true);

  gen->SetSizePdg(2);
  gen->AddPdg(443, 0);
  gen->AddPdg(100443, 1);

  gen->SetForceDecay(kEvtDiElectron);

  // set random seed
  gen->readString("Random:setSeed on");
  uint random_seed;
  unsigned long long int random_value = 0;
  ifstream urandom("/dev/urandom", ios::in|ios::binary);
  urandom.read(reinterpret_cast<char*>(&random_value), sizeof(random_seed));
  gen->readString(Form("Random:seed = %llu", random_value % 900000001));

  // print debug
  // gen->PrintDebug();

  return gen;
}