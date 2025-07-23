#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Generators/GeneratorPythia8Param.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include "TDatabasePDG.h"
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
  GeneratorPythia8GapTriggeredHF(int inputTriggerRatio = 5, std::vector<int> quarkPdgList = {}, std::vector<int> hadronPdgList = {}, std::vector<std::array<int, 2>> partPdgToReplaceList = {}, std::vector<float> freqReplaceList = {})
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
    mPartPdgToReplaceList = partPdgToReplaceList;
    mFreqReplaceList = freqReplaceList;
    // Ds1*(2700), Ds1*(2860), Ds3*(2860), Xic(3055)+, Xic(3080)+, Xic(3055)0, Xic(3080)0, LambdaC(2625), LambdaC(2595)
    mCustomPartPdgs = {30433, 40433, 437, 4315, 4316, 4325, 4326, 4124, 14122};
    mCustomPartMasses[30433] = 2.714f;
    mCustomPartMasses[40433] =  2.859f;
    mCustomPartMasses[437] = 2.860f;
    mCustomPartMasses[4315] = 3.0590f;
    mCustomPartMasses[4316] = 3.0799f;
    mCustomPartMasses[4325] = 3.0559f;
    mCustomPartMasses[4326] = 3.0772f;
    mCustomPartMasses[4124] = 2.62810f;
    mCustomPartMasses[14122] = 2.59225f;
    mCustomPartWidths[30433] = 0.122f;
    mCustomPartWidths[40433] =  0.160f;
    mCustomPartWidths[437] = 0.053f;
    mCustomPartWidths[4315] = 0.0064f;
    mCustomPartWidths[4316] = 0.0056f;
    mCustomPartWidths[4325] = 0.0078f;
    mCustomPartWidths[4326] = 0.0036f;
    mCustomPartWidths[4124] = 0.00052f;
    mCustomPartWidths[14122] = 0.0026f;
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
    LOG(info)<<Form("* Replacements: ");
    for (auto iRepl{0u}; iRepl<mPartPdgToReplaceList.size(); ++iRepl)
    {
      LOGP(info, "* {} -> {} (freq. {})", mPartPdgToReplaceList[iRepl].at(0), mPartPdgToReplaceList[iRepl].at(1), mFreqReplaceList[iRepl]);
    }
    LOG(info)<<"***********************************************************************";
  }

  bool Init() override
  {
    addSubGenerator(0, "Minimum bias");
    addSubGenerator(4, "Charm injected");
    addSubGenerator(5, "Beauty injected");

    std::vector<int> pdgToReplace{};
    for (auto iRepl{0u}; iRepl<mPartPdgToReplaceList.size(); ++iRepl)
    {
      for (auto iPdgRep{0u}; iPdgRep<pdgToReplace.size(); ++iPdgRep) {
        if (mPartPdgToReplaceList[iRepl].at(0) == pdgToReplace[iPdgRep]) {
          mFreqReplaceList[iRepl] += mFreqReplaceList[iPdgRep];
        }
      }
      if (mFreqReplaceList[iRepl] > 1.f) {
        LOGP(fatal, "Replacing more than 100% of a particle!");
      }
      pdgToReplace.push_back(mPartPdgToReplaceList[iRepl].at(0));
    }

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
          genOk = selectEvent();
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

  bool selectEvent()
  {

    bool isGoodAtPartonLevel{mQuarkPdgList.size() == 0};
    bool isGoodAtHadronLevel{mHadronPdgList.size() == 0};
    bool anyPartToReplace{mPartPdgToReplaceList.size() > 0};

    for (auto iPart{0}; iPart < mPythia.event.size(); ++iPart)
    {
      // search for Q-Qbar mother with at least one Q in rapidity window
      if (!isGoodAtPartonLevel)
      {
        auto daughterList = mPythia.event[iPart].daughterList();
        bool hasQ = false, hasQbar = false, atSelectedY = false;
        for (auto iDau : daughterList)
        {
          if (mPythia.event[iDau].id() == mQuarkPdg)
          {
            hasQ = true;
            if ((mPythia.event[iDau].y() > mQuarkRapidityMin) && (mPythia.event[iDau].y() < mQuarkRapidityMax))
            {
              atSelectedY = true;
            }
          }
          if (mPythia.event[iDau].id() == -mQuarkPdg)
          {
            hasQbar = true;
            if ((mPythia.event[iDau].y() > mQuarkRapidityMin) && (mPythia.event[iDau].y() < mQuarkRapidityMax))
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
        int id = std::abs(mPythia.event[iPart].id());
        float rap = mPythia.event[iPart].y();
        if (id == mHadronPdg && rap > mHadRapidityMin && rap < mHadRapidityMax)
        {
          isGoodAtHadronLevel = true;
        }
      }

      // if requested, we replace the particle
      const double pseudoRndm = mPythia.event[iPart].pT() * 1000. - (int64_t)(mPythia.event[iPart].pT() * 1000);
      for (auto iPartToReplace{0u}; iPartToReplace<mPartPdgToReplaceList.size(); ++iPartToReplace) {
        if (std::abs(mPythia.event[iPart].id()) == mPartPdgToReplaceList[iPartToReplace][0] && pseudoRndm < mFreqReplaceList[iPartToReplace]) {
          LOGP(debug, "REPLACING PARTICLE {} WITH {}, BEING RNDM {}", mPartPdgToReplaceList[iPartToReplace][0], mPartPdgToReplaceList[iPartToReplace][1], pseudoRndm);
          replaceParticle(iPart, mPartPdgToReplaceList[iPartToReplace][1]);
          break;
        }
      }

      // we send the trigger immediately (if there are no particles to replace, that can be different from the trigger ones)
      if (isGoodAtPartonLevel && isGoodAtHadronLevel && !anyPartToReplace)
      {
        LOG(debug)<<"EVENT SELECTED: Found particle "<<mPythia.event[iPart].id()<<" at rapidity "<<mPythia.event[iPart].y()<<"\n";
        return true;
      }
    }

    // we send the trigger
    if (isGoodAtPartonLevel && isGoodAtHadronLevel) {
      return true;
    }

    return false;
  };

  bool replaceParticle(int iPartToReplace, int pdgCodeNew) {

    auto mothers = mPythia.event[iPartToReplace].motherList();

    std::array<int, 25> pdgDiquarks = {1103, 2101, 2103, 2203, 3101, 3103, 3201, 3203, 3303, 4101, 4103, 4201, 4203, 4301, 4303, 4403, 5101, 5103, 5201, 5203, 5301, 5303, 5401, 5403, 5503};

    for (auto const& mother: mothers) {
      auto pdgMother = std::abs(mPythia.event[mother].id());
      if (pdgMother > 100 && std::find(pdgDiquarks.begin(), pdgDiquarks.end(), pdgMother) == pdgDiquarks.end()) {
        return false;
      }
    }

    int charge = mPythia.event[iPartToReplace].id() / std::abs(mPythia.event[iPartToReplace].id());
    float px = mPythia.event[iPartToReplace].px();
    float py = mPythia.event[iPartToReplace].py();
    float pz = mPythia.event[iPartToReplace].pz();
    float mass = 0.f;

    if (std::find(mCustomPartPdgs.begin(), mCustomPartPdgs.end(), pdgCodeNew) == mCustomPartPdgs.end()) { // not a custom particle
      float width = TDatabasePDG::Instance()->GetParticle(pdgCodeNew)->Width();
      float massRest = TDatabasePDG::Instance()->GetParticle(pdgCodeNew)->Mass();
      if (width > 0.f) {
        mass = gRandom->BreitWigner(massRest, width);
      } else {
        mass = massRest;
      }
    } else {
      if (mCustomPartWidths[pdgCodeNew] > 0.f) {
        mass = gRandom->BreitWigner(mCustomPartMasses[pdgCodeNew], mCustomPartWidths[pdgCodeNew]);
      } else {
        mass = mCustomPartMasses[pdgCodeNew];
      }
    }
    float energy = std::sqrt(px*px + py*py + pz*pz + mass*mass);

    // buffer daughter indices of mothers
    std::vector<std::vector<int>> dauOfMothers{};
    for (auto const& mother: mothers) {
      dauOfMothers.push_back(mPythia.event[mother].daughterList());
    }

    // we remove particle to replace and its daughters
    mPythia.event[iPartToReplace].undoDecay();
    int status = std::abs(mPythia.event[iPartToReplace].status()); // we must get it here otherwise it is negative (already decayed)
    if (status < 81 || status > 89) {
      status = 81;
    }
    mPythia.event.remove(iPartToReplace, iPartToReplace, true); // we remove the original particle

    // we restore the daughter indices of the mothers after the removal
    int newPartIdx{0};
    std::array<int, 2> newMothers = {0, 0};
    if (o2::eventgen::GeneratorPythia8Param::Instance().includePartonEvent) { // only necessary in case of parton event, otherwise we keep no mother
      newMothers[0] = mothers.front();
      newMothers[1] = mothers.back();
      newPartIdx = mPythia.event.size();
    }
    for (auto iMom{0u}; iMom<mothers.size(); ++iMom) {
      auto dau1 = dauOfMothers[iMom].front();
      auto dau2 = dauOfMothers[iMom].back();
      if (dau2 > dau1) {
        mPythia.event[mothers[iMom]].daughter1(dau1);
        mPythia.event[mothers[iMom]].daughter2(dau2 - 1);
      } else if (dau1 == dau2) {
        if (dau1 == 0) {
          mPythia.event[mothers[iMom]].daughter1(0);
          mPythia.event[mothers[iMom]].daughter2(0);
        } else { // in this case we set it equal to the new particle
          mPythia.event[mothers[iMom]].daughter1(newPartIdx);
          mPythia.event[mothers[iMom]].daughter2(newPartIdx);
        }
      } else if (dau2 < dau1) { // in this case we set it equal to the new particle
        if (dau2 == 0) {
          mPythia.event[mothers[iMom]].daughter1(newPartIdx);
        } else {
          if (dau1 == iPartToReplace) {
            mPythia.event[mothers[iMom]].daughter1(newPartIdx);
          } else {
            mPythia.event[mothers[iMom]].daughter2(newPartIdx);
          }
        }
      }
    }

    mPythia.event.append(charge * pdgCodeNew, status, newMothers[0], newMothers[1], 0, 0, 0, 0, px, py, pz, energy, mass);
    mPythia.moreDecays(); // we need to decay the new particle

    return true;
  }

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
  std::vector<std::array<int, 2>> mPartPdgToReplaceList;
  std::vector<float> mFreqReplaceList;
  std::vector<int> mCustomPartPdgs;
  std::map<int, float> mCustomPartMasses;
  std::map<int, float> mCustomPartWidths;

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
FairGenerator *GeneratorPythia8GapTriggeredCharm(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {}, std::vector<std::array<int, 2>> partPdgToReplaceList = {}, std::vector<float> freqReplaceList = {})
{
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, std::vector<int>{4}, hadronPdgList, partPdgToReplaceList, freqReplaceList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->setUsedSeed(seed);
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
FairGenerator *GeneratorPythia8GapTriggeredBeauty(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {}, std::vector<std::array<int, 2>> partPdgToReplaceList = {}, std::vector<float> freqReplaceList = {})
{
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, std::vector<int>{5}, hadronPdgList, partPdgToReplaceList, freqReplaceList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->setUsedSeed(seed);
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
FairGenerator *GeneratorPythia8GapTriggeredCharmAndBeauty(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {}, std::vector<std::array<int, 2>> partPdgToReplaceList = {}, std::vector<float> freqReplaceList = {})
{
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, std::vector<int>{4, 5}, hadronPdgList, partPdgToReplaceList, freqReplaceList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->setUsedSeed(seed);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  if (hadronPdgList.size() != 0)
  {
    myGen->setHadronRapidity(yHadronMin, yHadronMax);
  }
  return myGen;
}

FairGenerator *GeneratorPythia8GapHF(int inputTriggerRatio, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> quarkPdgList = {}, std::vector<int> hadronPdgList = {}, std::vector<std::array<int, 2>> partPdgToReplaceList = {}, std::vector<float> freqReplaceList = {})
{
  if (hadronPdgList.size() == 0 && quarkPdgList.size() == 0)
  {
    LOG(fatal) << "GeneratorPythia8GapHF: At least one quark or hadron PDG code must be specified";
  }
  auto myGen = new GeneratorPythia8GapTriggeredHF(inputTriggerRatio, quarkPdgList, hadronPdgList, partPdgToReplaceList, freqReplaceList);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->setUsedSeed(seed);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yQuarkMin, yQuarkMax);
  myGen->setHadronRapidity(yHadronMin, yHadronMax);

  return myGen;
}
