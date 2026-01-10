#include "FairGenerator.h"

#include "TDatabasePDG.h"
#include "TRandom.h"

#include "Generators/GeneratorPythia8.h"
#include "Generators/GeneratorPythia8Param.h"
#include "Pythia8/Pythia.h"
#include <fairlogger/Logger.h>

#include <string>
#include <vector>

using namespace Pythia8;

class GeneratorPythia8GapTriggeredPionEta : public o2::eventgen::GeneratorPythia8
{
 public:
  /// default constructor
  GeneratorPythia8GapTriggeredPionEta() = default;
  GeneratorPythia8GapTriggeredPionEta(int inputTriggerRatio = 5, std::vector<int> quarkPdgList = {}, std::vector<int> hadronPdgList = {})
  {
    mGeneratedEvents = 0;
    mInverseTriggerRatio = inputTriggerRatio;
    mQuarkRapidityMin = -1.5;
    mQuarkRapidityMax = 1.5;
    mHadRapidityMin = -1.5;
    mHadRapidityMax = 1.5;

    mQuarkPdg = 0;
    mHadronPdg = 0;
    mQuarkPdgList = quarkPdgList;
    mHadronPdgList = hadronPdgList;
    Print();
  }

  ///  Destructor
  ~GeneratorPythia8GapTriggeredPionEta() = default;
  ///  Print the input
  void Print()
  {
    LOG(info) << "********** GeneratorPythia8GapTriggeredHF configuration dump **********";
    LOG(info) << Form("* Trigger ratio: %d", mInverseTriggerRatio);
    LOG(info) << Form("* Quark pdg: %d", mQuarkPdg);
    LOG(info) << Form("* Quark rapidity: %f - %f", mQuarkRapidityMin, mQuarkRapidityMax);
    LOG(info) << Form("* Hadron pdg: %d", mHadronPdg);
    LOG(info) << Form("* Hadron rapidity: %f - %f", mHadRapidityMin, mHadRapidityMax);
    LOG(info) << Form("* Quark pdg list: ");
    for (auto pdg : mQuarkPdgList) {
      LOG(info) << Form("* %d ", pdg);
    }
    LOG(info) << Form("* Hadron pdg list: ");
    for (auto pdg : mHadronPdgList) {
      LOG(info) << Form("* %d ", pdg);
    }
    LOG(info) << "***********************************************************************";
  }

  bool Init() override
  {
    addSubGenerator(0, "Minimum bias");
    addSubGenerator(1, "Down injected");
    addSubGenerator(2, "Up injected");
    addSubGenerator(3, "Strange injected");

    return o2::eventgen::GeneratorPythia8::Init();
  }
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
  void setUsedSeed(unsigned int seed)
  {
    mUsedSeed = seed;
  };
  unsigned int getUsedSeed() const
  {
    return mUsedSeed;
  };

 protected:
  //__________________________________________________________________
  bool generateEvent() override
  {

    // Simple straightforward check to alternate generators
    if (mGeneratedEvents % mInverseTriggerRatio == 0) {
      int nInjectedEvents = mGeneratedEvents / mInverseTriggerRatio;
      // Alternate quarks if enabled (with the same ratio)
      if (mQuarkPdgList.size() >= 1) {
        int iQuark = nInjectedEvents % mQuarkPdgList.size();
        mQuarkPdg = mQuarkPdgList[iQuark];
        LOG(debug) << "SELECTED quark: " << mQuarkPdgList[iQuark];
      }
      // Alternate hadrons if enabled (with the same ratio)
      if (mHadronPdgList.size() >= 1) {
        int iHadron = (nInjectedEvents / std::max(mQuarkPdgList.size(), 1ul)) % mHadronPdgList.size();
        mHadronPdg = mHadronPdgList[iHadron];
        LOG(debug) << "SELECTED hadron: " << mHadronPdgList[iHadron];
      }

      // Generate event of interest
      bool genOk = false;
      while (!genOk) {
        if (GeneratorPythia8::generateEvent()) {
          genOk = selectEvent();
        }
      }
      notifySubGenerator(mQuarkPdg);
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
  bool selectEvent()
  {

    bool isGoodAtPartonLevel{mQuarkPdgList.size() == 0};
    bool isGoodAtHadronLevel{mHadronPdgList.size() == 0};

    for (auto iPart{0}; iPart < mPythia.event.size(); ++iPart) {
      // search for Q-Qbar mother with at least one Q in rapidity window
      if (!isGoodAtPartonLevel) {
        auto daughterList = mPythia.event[iPart].daughterList();
        bool hasQ = false, hasQbar = false, atSelectedY = false;
        for (auto iDau : daughterList) {
          if (mPythia.event[iDau].id() == mQuarkPdg) {
            hasQ = true;
            if ((mPythia.event[iDau].y() > mQuarkRapidityMin) && (mPythia.event[iDau].y() < mQuarkRapidityMax)) {
              atSelectedY = true;
            }
          }
          if (mPythia.event[iDau].id() == -mQuarkPdg) {
            hasQbar = true;
            if ((mPythia.event[iDau].y() > mQuarkRapidityMin) && (mPythia.event[iDau].y() < mQuarkRapidityMax)) {
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
        int id = std::abs(mPythia.event[iPart].id());
        float rap = mPythia.event[iPart].y();
        if (id == mHadronPdg && rap > mHadRapidityMin && rap < mHadRapidityMax) {
          isGoodAtHadronLevel = true;
        }
      }
      // we send the trigger immediately (if there are no particles to replace, that can be different from the trigger ones)
      if (isGoodAtPartonLevel && isGoodAtHadronLevel) {
        LOG(debug) << "EVENT SELECTED: Found particle " << mPythia.event[iPart].id() << " at rapidity " << mPythia.event[iPart].y() << "\n";
        return true;
      }
    }
    // we send the trigger
    if (isGoodAtPartonLevel && isGoodAtHadronLevel) {
      return true;
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
  unsigned int mUsedSeed;

  // Control gap-triggering
  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;

  // Control alternate trigger on charm and beauty quarks
  std::vector<int> mQuarkPdgList = {};

  // Control alternate trigger on different hadrons
  std::vector<int> mHadronPdgList = {};
};
// Predefined generators:
// Predefined generators:
// Charm-enriched
FairGenerator* GeneratorPythia8GapTriggeredPionAndEta(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {}, std::vector<std::array<int, 2>> partPdgToReplaceList = {}, std::vector<float> freqReplaceList = {})
{
  auto myGen = new GeneratorPythia8GapTriggeredPionEta(inputTriggerRatio, std::vector<int>{1, 2, 3}, hadronPdgList, partPdgToReplaceList, freqReplaceList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->setUsedSeed(seed);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if (hadronPdgList.size() != 0) {
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  return myGen;
}
