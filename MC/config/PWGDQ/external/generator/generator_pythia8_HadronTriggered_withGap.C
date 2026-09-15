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

  void addHadronPDGs(int pdg) { mHadronsPDGs.push_back(pdg); mRejFactorPrompt.push_back(1.0); mRejFactorNonPrompt.push_back(1.0);}
  
  void setRejFactorPrompt(int pdg, float rejFactor) {
    for (size_t i = 0; i < mHadronsPDGs.size(); i++) {
      if (pdg == mHadronsPDGs[i]) {
        mRejFactorPrompt[i] = rejFactor;
      }
    }
  }
  
  void setRejFactorNonPrompt(int pdg, float rejFactor) {
    for (size_t i = 0; i < mHadronsPDGs.size(); i++) {
      if (pdg == mHadronsPDGs[i]) {
        mRejFactorNonPrompt[i] = rejFactor;
      }
    }
  }

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
  
  for (size_t i = 0; i < mHadronsPDGs.size(); i++) {
    LOGF(info, "triggering hadron %d with rejection factor (prompt/non-prompt) %f/%f", mHadronsPDGs[i], mRejFactorPrompt[i], mRejFactorNonPrompt[i]);
  }
  
  return true;
} 


bool isOpenBhadron(int pdg) {
  // all open beauty hadrons, no upsilon
  return ((abs(pdg) >= 500 && abs(pdg) < 599) || (abs(pdg) >= 5000 && abs(pdg) < 5999)) && pdg != 553;
}

// search for the presence of at least one of the required hadrons in a selected rapidity window
bool findHadrons(Pythia8::Event& event) { 
  int ihad = 0;
  for (int ipa = 0; ipa < event.size(); ++ipa) {
    
    auto daughterList = event[ipa].daughterList();
  
    for (auto ida : daughterList) {
      ihad = 0;
      for (int pdg : mHadronsPDGs) {   // check that at least one of the pdg code is found in the event
        if (event[ida].id() == pdg) {
          if ((event[ida].y() > mRapidityMin) && (event[ida].y() < mRapidityMax)) {
            cout << "============= Found jpsi y,pt,pdg " <<  event[ida].y() << ", " << event[ida].pT() << ", " << event[ida].pdg() << endl;
            std::vector<int> daughters = event[ida].daughterList();
            for (int d : daughters) {
              cout << "###### daughter " << d << ": code " << event[d].id() << ", pt " << event[d].pT() << endl;
            }

            // check whether particle is prompt or non-prompt, since rejection factor can depend on it
            bool isNonPrompt = false;
            if (isOpenBhadron(pdg)) {
              isNonPrompt = true;
              cout << "particle is non-prompt" << endl
            } else {
              // we check the mother
              int mother = event[ida].mother1();
              if (mother >= 0 && isOpenBhadron(event[mother].id())) {
                isNonPrompt = true;
                cout << "particle is non-prompt, mother pdg: " << event[mother].id() << endl;
              }
              if (mother >= 0 && !isOpenBhadron(event[mother].id())) {
                // we check the grand-mother
                int grandmother = event[mother].mother1();
                if (grandmother >= 0 && isOpenBhadron(event[grandmother].id())) {
                  isNonPrompt = true;
                  cout << "particle is non-prompt, mother pdg: " << event[mother].id() << ", grand-mother pdg: "<< event[grandmother].id() << endl;
                }
                if (grandmother >= 0 && !isOpenBhadron(event[grandmother].id())) {
                  isNonPrompt = false;
                  cout << "particle is prompt, mother pdg: " << event[mother].id() << ", grand-mother pdg: "<< event[grandmother].id() << endl;
                }
              }
            }

            // rejection factor given in the ini file
            float randomNumber = gRandom->Rndm();
            if ((isPrompt && (randomNumber <= mRejFactorPrompt[ihad])) || (isNonPrompt && (randomNumber <= mRejFactorNonPrompt[ihad]))) {
              return true;
            }
          }
        }
        ihad++;
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
  std::vector<float> mRejFactorPrompt; // rejection factors for possibility to trigger a given particle only a fraction of the time, 1 by default
  std::vector<float> mRejFactorNonPrompt;
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
FairGenerator *
GeneratorInclusiveJpsiPsi2SChiC_EvtGenMidY(int triggerGap, double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false)
{
    auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8HadronTriggeredWithGap>();
    gen->setTriggerGap(triggerGap);
    gen->setRapidityRange(rapidityMin, rapidityMax);
    gen->addHadronPDGs(443);
    gen->addHadronPDGs(100443);
    gen->addHadronPDGs(445);
    gen->addHadronPDGs(20443);
    gen->setVerbose(verbose);

    TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffJpsi.cfg");
    gen->readFile(pathO2table.Data());
    gen->setConfigMBdecays(pathO2table);
    gen->PrintDebug(true);

    gen->SetSizePdg(4);
    gen->AddPdg(443, 0);
    gen->AddPdg(100443, 1);
    gen->AddPdg(445, 2);
    gen->AddPdg(20443, 3);

    gen->SetForceDecay(kEvtDiElectron);

    // set random seed
    gen->readString("Random:setSeed on");
    uint random_seed;
    unsigned long long int random_value = 0;
    ifstream urandom("/dev/urandom", ios::in | ios::binary);
    urandom.read(reinterpret_cast<char *>(&random_value), sizeof(random_seed));
    gen->readString(Form("Random:seed = %llu", random_value % 900000001));

    // print debug
    // gen->PrintDebug();

    return gen;
}
FairGenerator *
GeneratorInclusiveAllQuarkonia_EvtGenMidY(int triggerGap, double rapidityMin = -1.0, double rapidityMax = 1.0, TString rejFactors = "", bool verbose = false)
{

    int particleList[16] = {443, // Jpsi
      100443, // psi(2S)
      10441, // chic0
      20443, // chic1
      445, // chic2
      553, // upsilon(1S)
      100553, // upsilon(2S)
      200553, // upsilon(3S)
      // we also add B hadrons to trigger correct rapidity range (e.g. B is within |y|<1 but non-prompt J/psi has |y|>1)
      511, // B0
      521, // B+
      531, // Bs
      541, // Bc
      5122, // Lambdab
      5132, // Xib+
      5232, // Xib0
      5332 // Omegab
    }; 

    auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::GeneratorPythia8HadronTriggeredWithGap>();
    gen->setTriggerGap(triggerGap);
    gen->setRapidityRange(rapidityMin, rapidityMax);
    // specify particles to be triggered
    for (int i = 0; i < 16; i++) {
      gen->addHadronPDGs(particleList[i]);
    }
    gen->setVerbose(verbose);
    
    // possibility to enhance a particle compared to another (or completely reject one particle) using rejection factors configured from a string
    // the rejection factors can be kept in a comma separated list (e.g. "pdg1:rejFactor1,pdg2:rejFactor2")
    // also the keywords "prompt" and "non-prompt" can be used to modify all prompt and all non-prompt (e.g. "prompt:rejFactor1,non-prompt:rejFactor2")
    // or the keyword can be used for only one particle (e.g. "pdg1:rejFactor1:prompt,pdg1:rejFactor2:non-prompt")
    TObjArray* objArray = rejFactors.Tokenize(",");
    for (int i = 0; i < objArray->GetEntries(); i++) {
      TString rejStr = objArray->At(i);
      TObjArray* objArrayCurrent = rejStr.Tokenize(":");
      if (objArrayCurrent->GetEntries() != 2 && objArrayCurrent->GetEntries() != 3) {
        LOGF(fatal, "Problem when configuring string for particle rejection factors: %s, incorrect length", rejStr.Data());
      }
      if (!objArrayCurrent[1].IsFloat()) {
        LOGF(fatal, "Problem when configuring string for particle rejection factors: %s, is not float", rejStr.Data());
      }
      if (objArrayCurrent[0].CompareTo("prompt") == 0) {
        // Common switch for all prompt particles
        for (int ihad = 0; ihad < 16; i++) {
          gen->setRejFactorPrompt(particleList[i], objArrayCurrent[1].Atof());
        }
        continue;
      }
      if (objArrayCurrent[0].CompareTo("non-prompt") == 0) {
        // Common switch for all non-prompt particles
        for (int ihad = 0; ihad < 16; i++) {
          gen->setRejFactorNonPrompt(particleList[i], objArrayCurrent[1].Atof());
        }
        continue;
      }
      if (objArrayCurrent[0].IsDigit()) {
        // Setting the rejection factor for a specific particle
        if (objArrayCurrent->GetEntries() == 2) {
          gen->setRejFactorPrompt(objArrayCurrent[0].Atoi(), objArrayCurrent[1].Atof());
          gen->setRejFactorNonPrompt(objArrayCurrent[0].Atoi(), objArrayCurrent[1].Atof());
          continue;
        }
        else {
          if (objArrayCurrent[2].CompareTo("prompt") == 0) {
            gen->setRejFactorPrompt(objArrayCurrent[0].Atoi(), objArrayCurrent[1].Atof());
            continue;
          }
          if (objArrayCurrent[2].CompareTo("non-prompt") == 0) {
            gen->setRejFactorNonPrompt(objArrayCurrent[0].Atoi(), objArrayCurrent[1].Atof());
            continue;
          }
        }
      }
      LOGF(fatal, "Problem when configuring string for particle rejection factors: %s, incorrect template", rejStr.Data());
    }
    

    TString pathO2table = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/pythia8/decayer/switchOffAllQuarkonia.cfg");
    gen->readFile(pathO2table.Data());
    gen->setConfigMBdecays(pathO2table);
    gen->PrintDebug(true);

    // specify particles to be decayed with EvtGen
    gen->SetSizePdg(16);
    for (int i = 0; i < 16; i++) {
      gen->AddPdg(particleList[i], i);
    }
    
    gen->SetForceDecay(kEvtBPsiAndJpsiDiElectron);

    // set random seed
    gen->readString("Random:setSeed on");
    uint random_seed;
    unsigned long long int random_value = 0;
    ifstream urandom("/dev/urandom", ios::in | ios::binary);
    urandom.read(reinterpret_cast<char *>(&random_value), sizeof(random_seed));
    gen->readString(Form("Random:seed = %llu", random_value % 900000001));

    // print debug
    // gen->PrintDebug();

    return gen;
}
