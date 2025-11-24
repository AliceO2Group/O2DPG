#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"

#include <map>
#include <unordered_set>
//#include <utility>	// for std::pair

using namespace Pythia8;

class GeneratorPythia8GapTriggeredHFLeptonOO : public o2::eventgen::GeneratorPythia8
{
public:
  /// default constructor
  GeneratorPythia8GapTriggeredHFLeptonOO() = default;

  /// constructor
  GeneratorPythia8GapTriggeredHFLeptonOO(TString configsignal, int quarkPdg = 4, int lInputTriggerRatio = 5, int lInputExternalID = 0)
  {

    lGeneratedEvents = 0;
    lInverseTriggerRatio = lInputTriggerRatio;
    lExternalID = lInputExternalID;
    mQuarkPdg = quarkPdg;

    auto seed = (gRandom->TRandom::GetSeed() % 900000000);

    int offset = (int)(gRandom->Uniform(lInverseTriggerRatio)); // create offset to mitigate edge effects due to small number of events per job
    lGeneratedEvents += offset;
    
    cout << "Initalizing extra PYTHIA object used to generate min-bias events..." << endl;
    TString pathconfigMB = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}//MC/config/common/pythia8/generator/pythia8_OO_536.cfg");
    pythiaObjectMinimumBias.readFile(pathconfigMB.Data());
    pythiaObjectMinimumBias.readString("Random:setSeed on");
    pythiaObjectMinimumBias.readString("Random:seed " + std::to_string(seed));
    pythiaObjectMinimumBias.init();
    cout << "Initalization of gap event is complete" << endl;

    cout << "Initalizing extra PYTHIA object used to generate signal events..." << endl;
    TString pathconfigSignal = gSystem->ExpandPathName(configsignal.Data());
    pythiaObjectSignal.readFile(pathconfigSignal.Data());
    pythiaObjectSignal.readString("Random:setSeed on");
    pythiaObjectSignal.readString("Random:seed " + std::to_string(seed));
    pythiaObjectSignal.readString("Beams:idA = 1000080160");
    pythiaObjectSignal.readString("Beams:idB = 1000080160");
    pythiaObjectSignal.readString("Beams:eCM = 5360.0");
    pythiaObjectSignal.readString("Beams:frameType = 1");
    pythiaObjectSignal.readString("ParticleDecays:limitTau0 = on");
    pythiaObjectSignal.readString("ParticleDecays:tau0Max = 10.");
    pythiaObjectSignal.readString("HeavyIon:SigFitNGen = 0");
    pythiaObjectSignal.readString("HeavyIon:SigFitDefPar = 2.15,18.42,0.33");
    pythiaObjectSignal.init();
    cout << "Initalization of signal event is complete" << endl;

    // flag the generators using type
    // addCocktailConstituent(type, "interesting");
    // addCocktailConstitent(0, "minbias");
    // Add Sub generators
    addSubGenerator(0, "default generator");
    addSubGenerator(1, "charm lepton");
    addSubGenerator(2, "beauty forced decay");
    addSubGenerator(3, "beauty no foced decay");
  }

  ///  Destructor
  ~GeneratorPythia8GapTriggeredHFLeptonOO() = default;

  void addTriggerOnDaughter(int nb, int pdg)
  {
    mNbDaughter = nb;
    mPdgDaughter = pdg;
  };
  void setQuarkRapidity(float yMin, float yMax)
  {
    mQuarkRapidityMin = yMin;
    mQuarkRapidityMax = yMax;
  };
  void setDaughterRapidity(float yMin, float yMax)
  {
    mDaughterRapidityMin = yMin;
    mDaughterRapidityMax = yMax;
  };

protected:
  //__________________________________________________________________
  Bool_t generateEvent() override
  {
    /// reset event
    mPythia.event.reset();

    // Simple straightforward check to alternate generators
    if (lGeneratedEvents % lInverseTriggerRatio == 0) {
      // Generate event of interest
      Bool_t lGenerationOK = kFALSE;
      while (!lGenerationOK) {
        if (pythiaObjectSignal.next()) {
          lGenerationOK = selectEvent(pythiaObjectSignal.event);
        }
      }
      mPythia.event = pythiaObjectSignal.event;
      notifySubGenerator(lExternalID);
    } else {
      // Generate minimum-bias event
      Bool_t lGenerationOK = kFALSE;
      while (!lGenerationOK) {
        lGenerationOK = pythiaObjectMinimumBias.next();
      }
      mPythia.event = pythiaObjectMinimumBias.event;
      notifySubGenerator(0);
    }

    lGeneratedEvents++;
    // mPythia.next();

    return true;
  }

  bool selectEvent(const Pythia8::Event& event)
  {
    bool isGoodAtPartonLevel = false, isGoodAtDaughterLevel = (mPdgDaughter != 0) ? false : true;
    int nbDaughter = 0;
    for (auto iPart{0}; iPart < event.size(); ++iPart) {
      // search for Q-Qbar mother with at least one Q in rapidity window
      if (!isGoodAtPartonLevel) {
        auto daughterList = event[iPart].daughterList();
        bool hasQ = false, hasQbar = false, atSelectedY = false;
        for (auto iDau : daughterList) {
          if (event[iDau].id() == mQuarkPdg) {
            hasQ = true;
          }
          if (event[iDau].id() == -mQuarkPdg) {
            hasQbar = true;
          }
          if ((std::abs(event[iDau].id()) == mQuarkPdg) && (event[iDau].y() > mQuarkRapidityMin) && (event[iDau].y() < mQuarkRapidityMax))
            atSelectedY = true;
        }
        if (hasQ && hasQbar && atSelectedY) {
          isGoodAtPartonLevel = true;
        }
      }
      // search for mNbDaughter daughters of type mPdgDaughter in rapidity window
      if (!isGoodAtDaughterLevel) {
        int id = std::abs(event[iPart].id());
        float rap = event[iPart].y();
        if (id == mPdgDaughter) {
          int motherindexa = event[iPart].mother1();
          if (motherindexa > 0) {
            int idmother = std::abs(event[motherindexa].id());
            if (int(std::abs(idmother) / 100.) == 4 || int(std::abs(idmother) / 1000.) == 4 || int(std::abs(idmother) / 100.) == 5 || int(std::abs(idmother) / 1000.) == 5) {
              if (rap > mDaughterRapidityMin && rap < mDaughterRapidityMax) {
                nbDaughter++;
                if (nbDaughter >= mNbDaughter) isGoodAtDaughterLevel = true;
              }
            }
          }
        }
      }
      // we send the trigger
      if (isGoodAtPartonLevel && isGoodAtDaughterLevel) {
        return true;
      }
    }
    return false;
  };

private:
  // Interface to override import particles
  Pythia8::Event mOutputEvent;

  // Properties of selection
  int mQuarkPdg;
  float mQuarkRapidityMin;
  float mQuarkRapidityMax;
  int mPdgDaughter;
  int mNbDaughter;
  float mDaughterRapidityMin;
  float mDaughterRapidityMax;

  // Control gap-triggering
  Long64_t lGeneratedEvents;
  int lInverseTriggerRatio;
  // ID for different generators
  int lExternalID;

  // Base event generators
  Pythia8::Pythia pythiaObjectMinimumBias; ///Minimum bias collision generator
  Pythia8::Pythia pythiaObjectSignal;      ///Signal collision generator
};

// Predefined generators:

// Charm-enriched forced decay
FairGenerator* GeneratorPythia8GapTriggeredCharmLepton(int inputTriggerRatio, int inputExternalID, int pdgLepton, float yMinQ = -1.5, float yMaxQ = 1.5, float yMinL = -1, float yMaxL = 1)
{
  auto myGen = new GeneratorPythia8GapTriggeredHFLeptonOO("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/pythia8/generator/pythia8_pp_cr2_forceddecayscharm.cfg", 4, inputTriggerRatio, inputExternalID);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yMinQ, yMaxQ);
  myGen->addTriggerOnDaughter(2, pdgLepton);
  myGen->setDaughterRapidity(yMinL, yMaxL);
  return myGen;
}

// Beauty-enriched forced decay
FairGenerator* GeneratorPythia8GapTriggeredBeautyForcedDecays(int inputTriggerRatio, int inputExternalID, int pdgLepton, float yMinQ = -1.5, float yMaxQ = 1.5, float yMinL = -1, float yMaxL = 1)
{
  auto myGen = new GeneratorPythia8GapTriggeredHFLeptonOO("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/pythia8/generator/pythia8_bbbar_forceddecayscharmbeauty.cfg", 5, inputTriggerRatio, inputExternalID);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yMinQ, yMaxQ);
  myGen->addTriggerOnDaughter(2, pdgLepton);
  myGen->setDaughterRapidity(yMinL, yMaxL);
  return myGen;
}

// Beauty-enriched no forced decay
FairGenerator* GeneratorPythia8GapTriggeredBeautyNoForcedDecays(int inputTriggerRatio, int inputExternalID, int pdgLepton, float yMinQ = -1.5, float yMaxQ = 1.5, float yMinL = -1, float yMaxL = 1)
{
  auto myGen = new GeneratorPythia8GapTriggeredHFLeptonOO("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/pythia8/generator/pythia8_bbbar.cfg", 5, inputTriggerRatio, inputExternalID);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yMinQ, yMaxQ);
  myGen->addTriggerOnDaughter(2, pdgLepton);
  myGen->setDaughterRapidity(yMinL, yMaxL);
  return myGen;
}
