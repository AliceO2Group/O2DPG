#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include <fairlogger/Logger.h>

#include <string>
#include <vector>

using namespace Pythia8;

class GeneratorPythia8GapTriggeredHF : public o2::eventgen::GeneratorPythia8
{
public:
  /// default constructor
  GeneratorPythia8GapTriggeredHF() = default;

  /// constructor
  GeneratorPythia8GapTriggeredHF(int inputTriggerRatio = 5, std::vector<int> quarkPdgList = {}, std::vector<int> hadronPdgList = {})
  {

    mGeneratedEvents = 0;
    mInverseTriggerRatio = inputTriggerRatio;
    mQuarkRapidityMin = -1.5;
    mQuarkRapidityMax = -1.5;
    mHadRapidityMin = -1.5;
    mHadRapidityMax = -1.5;
    mQuarkPdg = 0;
    mHadronPdg = 0;
    mQuarkPdgList = quarkPdgList;
    mHadronPdgList = hadronPdgList;
    mUseAltGenForBkg = false;
    Print();
  }

  ///  Destructor
  ~GeneratorPythia8GapTriggeredHF() = default;

  ///  Print the input
  void Print()
  {
    LOG(info) << "********** GeneratorPythia8GapTriggeredHF configuration dump **********";
    LOG(info)<<Form("* Trigger ratio: %d", mInverseTriggerRatio);
    LOG(info)<<Form("* Quark pdg: %d", mQuarkPdg);
    LOG(info)<<Form("* Quark rapidity: %f - %f", mQuarkRapidityMin, mQuarkRapidityMax);
    LOG(info)<<Form("* Hadron pdg: %d", mHadronPdg);
    LOG(info)<<Form("* Hadron rapidity: %f - %f", mHadRapidityMin, mHadRapidityMax);
    LOG(info)<<Form("* Quark pdg list: ");
    for (auto pdg : mQuarkPdgList)
    {
      LOG(info)<<Form("* %d ", pdg);
    }
    LOG(info)<<Form("* Hadron pdg list: ");
    for (auto pdg : mHadronPdgList)
    {
      LOG(info)<<Form("* %d ", pdg);
    }
    LOG(info)<<"***********************************************************************";
  }

  bool Init() override
  {
    addSubGenerator(0, "Minimum bias");
    addSubGenerator(4, "Charm injected");
    addSubGenerator(5, "Beauty injected");
    bool initAltOk{true};
    bool initMainOk = o2::eventgen::GeneratorPythia8::Init();
    // we also initialise alternative PYTHIA generator, if needed
    if (mUseAltGenForBkg)
    {
      initAltOk = mBkgGen.init();
    }
    return (initMainOk && initAltOk);
  }

  void setAlternativeConfigForBkgEvents(std::string bkgGenConfig, unsigned int seed)
  {
    // define minimum bias event generator
    std::string pathBkgGenConfig = gSystem->ExpandPathName(bkgGenConfig.data());
    mBkgGen.readFile(pathBkgGenConfig.data());
    mBkgGen.readString("Random:setSeed on");
    mBkgGen.readString("Random:seed " + std::to_string(seed));
    mUseAltGenForBkg = true;
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

protected:
  //__________________________________________________________________
  bool generateEvent() override
  {
    

    // Simple straightforward check to alternate generators
    if (mGeneratedEvents % mInverseTriggerRatio == 0)
    {
      int nInjectedEvents = mGeneratedEvents / mInverseTriggerRatio;
      // Alternate quarks if enabled (with the same ratio)
      if (mQuarkPdgList.size() >= 1)
      {
        int iQuark = nInjectedEvents % mQuarkPdgList.size();
        mQuarkPdg = mQuarkPdgList[iQuark];
        LOG(debug)<<"SELECTED quark: "<<mQuarkPdgList[iQuark];
      }
      // Alternate hadrons if enabled (with the same ratio)
      if (mHadronPdgList.size() >= 1)
      {
        int iHadron = (nInjectedEvents / std::max(mQuarkPdgList.size(), 1ul)) % mHadronPdgList.size();
        mHadronPdg = mHadronPdgList[iHadron];
        LOG(debug)<<"SELECTED hadron: "<<mHadronPdgList[iHadron];
      }

      // Generate event of interest
      bool genOk = false;
      while (!genOk)
      {
        if (GeneratorPythia8::generateEvent())
        {
          genOk = selectEvent(mPythia.event);
        }
      }
      notifySubGenerator(mQuarkPdg);
    }
    else
    {
      // Generate minimum-bias event
      bool genOk = false;
      if (!mUseAltGenForBkg)
      {
        while (!genOk)
        {
          genOk = GeneratorPythia8::generateEvent();
        }
      }
      else
      {
        mBkgGen.event.reset();
        while (!genOk) {
          genOk = mBkgGen.next();
        }
        mPythia.event = mBkgGen.event;
      }
      notifySubGenerator(0);
    }

    mGeneratedEvents++;

    return true;
  }

  bool selectEvent(const Pythia8::Event &event)
  {

    bool isGoodAtPartonLevel{mQuarkPdgList.size() == 0};
    bool isGoodAtHadronLevel{mHadronPdgList.size() == 0};

    for (auto iPart{0}; iPart < event.size(); ++iPart)
    {

      // search for Q-Qbar mother with at least one Q in rapidity window
      if (!isGoodAtPartonLevel)
      {
        auto daughterList = event[iPart].daughterList();
        bool hasQ = false, hasQbar = false, atSelectedY = false;
        for (auto iDau : daughterList)
        {
          if (event[iDau].id() == mQuarkPdg)
          {
            hasQ = true;
            if ((event[iDau].y() > mQuarkRapidityMin) && (event[iDau].y() < mQuarkRapidityMax))
            {
              atSelectedY = true;
            }
          }
          if (event[iDau].id() == -mQuarkPdg)
          {
            hasQbar = true;
            if ((event[iDau].y() > mQuarkRapidityMin) && (event[iDau].y() < mQuarkRapidityMax))
            {
              atSelectedY = true;
            }
          }
        }
        if (hasQ && hasQbar && atSelectedY)
        {
          isGoodAtPartonLevel = true;
        }
      }

      // search for hadron in rapidity window
      if (!isGoodAtHadronLevel)
      {
        int id = std::abs(event[iPart].id());
        float rap = event[iPart].y();
        if (id == mHadronPdg && rap > mHadRapidityMin && rap < mHadRapidityMax)
        {
          isGoodAtHadronLevel = true;
        }
      }

      // we send the trigger
      if (isGoodAtPartonLevel && isGoodAtHadronLevel)
      {
        LOG(debug)<<"EVENT SELECTED: Found particle "<<event[iPart].id()<<" at rapidity "<<event[iPart].y()<<"\n";
        return true;
      }
    }

    return false;
  };

private:
  // Interface to override import particles
  Pythia8::Event mOutputEvent;

  // alternative pythia generator for background (in case a different one is needed)
  Pythia8::Pythia mBkgGen;
  bool mUseAltGenForBkg;

  // Properties of selection
  int mQuarkPdg;
  float mQuarkRapidityMin;
  float mQuarkRapidityMax;
  int mHadronPdg;
  float mHadRapidityMin;
  float mHadRapidityMax;

  // Control gap-triggering
  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;

  // Control alternate trigger on charm and beauty quarks
  std::vector<int> mQuarkPdgList = {};

  // Control alternate trigger on different hadrons
  std::vector<int> mHadronPdgList = {};
};

// Predefined generators:
// Charm-enriched
FairGenerator *GeneratorPythia8GapTriggeredCharm(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, std::vector<int>{4}, hadronPdgList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if (hadronPdgList.size() != 0)
  {
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  return myGen;
}

// Beauty-enriched
FairGenerator *GeneratorPythia8GapTriggeredBeauty(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, std::vector<int>{5}, hadronPdgList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if (hadronPdgList.size() != 0)
  {
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  return myGen;
}

// Charm and beauty enriched (with same ratio)
FairGenerator *GeneratorPythia8GapTriggeredCharmAndBeauty(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, std::vector<int>{4, 5}, hadronPdgList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if (hadronPdgList.size() != 0)
  {
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  return myGen;
}

FairGenerator *GeneratorPythia8GapHF(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> quarkPdgList = {}, std::vector<int> hadronPdgList = {})
{
  if (hadronPdgList.size() == 0 && quarkPdgList.size() == 0)
  {
    LOG(fatal) << "GeneratorPythia8GapHF: At least one quark or hadron PDG code must be specified";
  }
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, quarkPdgList, hadronPdgList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  myGen->setHadronRapidity(yHadronMin, yHadronMax);

  return myGen;
}

// Charm and beauty enriched (with same ratio)
FairGenerator *GeneratorPythia8GapTriggeredCharmAndBeautyWithAltBkgEvents(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, std::vector<int>{4, 5}, hadronPdgList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if (hadronPdgList.size() != 0)
  {
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  myGen->setAlternativeConfigForBkgEvents("$O2DPG_ROOT/MC/config/PWGHF/pythia8/generator/pythia8_inel_forbkg.cfg", seed);
  return myGen;
}
