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
    mDoNoQuarkTrigger = quarkPdgList.size() == 0;
    mQuarkPdgList = quarkPdgList;
    mHadronPdgList = hadronPdgList;
    if (mQuarkPdgList.size() > 1 && mHadronPdgList.size() > 1)
    {
      LOG(fatal)<<"GeneratorPythia8GapTriggeredHF: Only one between hadron list and quark list can have more than one element";
    }
    Print();
  }

  ///  Destructor
  ~GeneratorPythia8GapTriggeredHF() = default;

  ///  Print the input
  void Print()
  {
    std::cout << "********** GeneratorPythia8GapTriggeredHF configuration dump **********" << std::endl;
    fmt::printf("* Trigger ratio: %d\n", mInverseTriggerRatio);
    fmt::printf("* Quark pdg: %d\n", mQuarkPdg);
    fmt::printf("* Quark rapidity: %f - %f\n", mQuarkRapidityMin, mQuarkRapidityMax);
    fmt::printf("* Hadron pdg: %d\n", mHadronPdg);
    fmt::printf("* Hadron rapidity: %f - %f\n", mHadRapidityMin, mHadRapidityMax);
    fmt::printf("* No quark trigger: %d\n", mDoNoQuarkTrigger);
    fmt::printf("* Quark pdg list: ");
    for (auto pdg : mQuarkPdgList)
    {
      fmt::printf("%d ", pdg);
    }
    fmt::printf("\n");
    fmt::printf("* Hadron pdg list: ");
    for (auto pdg : mHadronPdgList)
    {
      fmt::printf("%d ", pdg);
    }
    fmt::printf("\n");
    std::cout << "***********************************************************************" << std::endl;
  }

  bool Init() override
  {
    addSubGenerator(0, "Minimum bias");
    addSubGenerator(4, "Charm injected");
    addSubGenerator(5, "Beauty injected");
    return o2::eventgen::GeneratorPythia8::Init();
  }

  void addTriggerOnHadron(int hadPdg) { mHadronPdgList.push_back(hadPdg); };
  void setQuarkTrigger(bool doNoQuarkTrigger) { mDoNoQuarkTrigger = doNoQuarkTrigger; };
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

      if (mQuarkPdgList.size() > 1)
      {
        int indexq = (mGeneratedEvents / mInverseTriggerRatio) % mQuarkPdgList.size();
        mQuarkPdg = mQuarkPdgList[indexq];
      }
      else if (mQuarkPdgList.size() == 1)
      {
        mQuarkPdg = mQuarkPdgList[0];
      }

      // Alternate Omega and Xi if enabled (with the same ratio)
      if (mHadronPdgList.size())
      {
        int indexh = (mGeneratedEvents / mInverseTriggerRatio) % mHadronPdgList.size();
        mHadronPdg = mHadronPdgList[indexh];
      }
      else if (mHadronPdgList.size() == 1)
      {
        mHadronPdg = mHadronPdgList[0];
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
      while (!genOk)
      {
        genOk = GeneratorPythia8::generateEvent();
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

  // Properties of selection
  int mQuarkPdg = 0;
  float mQuarkRapidityMin;
  float mQuarkRapidityMax;
  int mHadronPdg = 0;
  float mHadRapidityMin;
  float mHadRapidityMax;
  bool mDoNoQuarkTrigger;

  // Control gap-triggering
  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;

  // Control alternate injection of charm and beauty
  std::vector<int> mQuarkPdgList = {};

  // Control alternate injection of Omega and Xi
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
  myGen->setQuarkTrigger(quarkPdgList.size());
  myGen->setHadronRapidity(yHadronMin, yHadronMax);

  return myGen;
}