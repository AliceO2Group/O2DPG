#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"

#include <string>

using namespace Pythia8;

class GeneratorPythia8GapTriggeredHF : public o2::eventgen::GeneratorPythia8 {
public:

  /// default constructor
  GeneratorPythia8GapTriggeredHF() = default;

  /// constructor
  GeneratorPythia8GapTriggeredHF(int inputTriggerRatio = 5, int quarkPdg = 4) {

    mGeneratedEvents = 0;
    mHadronPdg = 0; // unless differently set, we do not trigger on specific hadron species
    mQuarkPdg = quarkPdg;
    mInverseTriggerRatio = inputTriggerRatio;
    mQuarkRapidityMin = -1.5;
    mQuarkRapidityMax = -1.5;
    mHadRapidityMin = -1.5;
    mHadRapidityMax = -1.5;
    mDoNoQuarkTrigger = false;
    mDoAltInjection = false;
  }

  ///  Destructor
  ~GeneratorPythia8GapTriggeredHF() = default;

  Bool_t Init() override
  {
    addSubGenerator(0, "Minimum bias");
    addSubGenerator(4, "Charm injected");
    addSubGenerator(5, "Beauty injected");
    return o2::eventgen::GeneratorPythia8::Init();
  }

  void addTriggerOnHadron(int hadPdg) { mHadronPdg = hadPdg; };
  void setQuarkTrigger (bool doNoQuarkTrigger) { mDoNoQuarkTrigger = doNoQuarkTrigger; };
  void setQuarkRapidity(float yMin, float yMax)
  {
    mQuarkRapidityMin = yMin;
    mQuarkRapidityMax = yMax;
  };
  void setHadronRapidity(float yMin, float yMax)
  {
    mHadRapidityMin = yMin;
    mHadRapidityMax = yMax;
  };
  void setAlternateInjection(bool doAltInjection) {mDoAltInjection = doAltInjection; };

protected:
  //__________________________________________________________________
  bool generateEvent() override {

    // Simple straightforward check to alternate generators
    if (mGeneratedEvents % mInverseTriggerRatio == 0) {
      // Generate event of interest
      bool genOk = false;
      while (!genOk) {
        if (GeneratorPythia8::generateEvent()) {
          genOk = selectEvent(mPythia.event);
        }        
      }
      notifySubGenerator(mQuarkPdg);

      // Alternate charm and beauty if enabled (with the same ratio)
      if(mDoAltInjection) {
        mQuarkPdg = (mQuarkPdg == 4) ? 5 : 4;
      }

    } else {
      // Generate minimum-bias event
      bool genOk = false;
      while (!genOk) {
        genOk = GeneratorPythia8::generateEvent();
      }
      notifySubGenerator(0);
    }

    mGeneratedEvents++;

    return true;
  }

  bool selectEvent(const Pythia8::Event& event)
  {
    bool isGoodAtPartonLevel;
    bool isGoodAtHadronLevel;
    if(mDoNoQuarkTrigger){
      isGoodAtPartonLevel = (mHadronPdg != 0) ? true : false;
      isGoodAtHadronLevel = (mHadronPdg != 0) ? false : true;
    } else {
      isGoodAtPartonLevel = false;
      isGoodAtHadronLevel = (mHadronPdg != 0) ? false : true;
    }

    for (auto iPart{0}; iPart < event.size(); ++iPart) {

      // search for Q-Qbar mother with at least one Q in rapidity window
      if (!isGoodAtPartonLevel) {
        auto daughterList = event[iPart].daughterList();
        bool hasQ = false, hasQbar = false, atSelectedY = false;
        for (auto iDau : daughterList) {
          if (event[iDau].id() == mQuarkPdg) {
            hasQ = true;
            if ((event[iDau].y() > mQuarkRapidityMin) && (event[iDau].y() < mQuarkRapidityMax)) {
              atSelectedY = true;
            }
          }
          if (event[iDau].id() == -mQuarkPdg) {
            hasQbar = true;
            if ((event[iDau].y() > mQuarkRapidityMin) && (event[iDau].y() < mQuarkRapidityMax)) {
              atSelectedY = true;
            }
          }  
        }
        if (hasQ && hasQbar && atSelectedY) {
          isGoodAtPartonLevel = true;
        }
      }

      // search for hadron in rapidity window
      if (!isGoodAtHadronLevel) {
        int id = std::abs(event[iPart].id());
        float rap = event[iPart].y();
        if (id == mHadronPdg && rap > mHadRapidityMin && rap < mHadRapidityMax) {
          isGoodAtHadronLevel = true;
        }
      }

      // we send the trigger
      if (isGoodAtPartonLevel && isGoodAtHadronLevel) {
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
  int mHadronPdg;
  float mHadRapidityMin;
  float mHadRapidityMax;
  bool mDoNoQuarkTrigger;

  // Control gap-triggering
  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;

  // Control alternate injection of charm and beauty
  bool mDoAltInjection;
};

// Predefined generators:
// Charm-enriched
FairGenerator *GeneratorPythia8GapTriggeredCharm(int inputTriggerRatio, float yQuarkMin=-1.5, float yQuarkMax=1.5, float yHadronMin=-1.5, float yHadronMax=1.5, int pdgCodeCharmHadron=0, bool doNoQuarkTrigger=false) {
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, 4);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if(pdgCodeCharmHadron != 0) {
    myGen->setQuarkTrigger(doNoQuarkTrigger);
    myGen->addTriggerOnHadron(pdgCodeCharmHadron);
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  return myGen;
}

// Beauty-enriched
FairGenerator *GeneratorPythia8GapTriggeredBeauty(int inputTriggerRatio, float yQuarkMin=-1.5, float yQuarkMax=1.5, float yHadronMin=-1.5, float yHadronMax=1.5, int pdgCodeCharmHadron=0, bool doNoQuarkTrigger=false) {
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, 5);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if(pdgCodeCharmHadron != 0) {
    myGen->setQuarkTrigger(doNoQuarkTrigger);
    myGen->addTriggerOnHadron(pdgCodeCharmHadron);
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  return myGen;
}

// Charm and beauty enriched (with same ratio)
FairGenerator *GeneratorPythia8GapTriggeredCharmAndBeauty(int inputTriggerRatio, float yQuarkMin=-1.5, float yQuarkMax=1.5, float yHadronMin=-1.5, float yHadronMax=1.5, int pdgCodeCharmHadron=0, bool doNoQuarkTrigger=false) {
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, 4);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if(pdgCodeCharmHadron != 0) {
    myGen->setQuarkTrigger(doNoQuarkTrigger);
    myGen->addTriggerOnHadron(pdgCodeCharmHadron);
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  myGen->setAlternateInjection(true);
  return myGen;
}
