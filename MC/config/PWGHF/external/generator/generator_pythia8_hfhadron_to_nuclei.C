#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include <fairlogger/Logger.h>
#include <string>
#include <vector>

R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
#include "MC/config/common/external/generator/CoalescencePythia8.h"

using namespace Pythia8;

class GeneratorPythia8HFHadToNuclei : public o2::eventgen::GeneratorPythia8
{
 public:
  /// default constructor
  GeneratorPythia8HFHadToNuclei() = default;

  /// constructor
  GeneratorPythia8HFHadToNuclei(int inputTriggerRatio = 5, std::vector<int> hfHadronPdgList = {}, std::vector<unsigned int> nucleiPdgList = {}, bool trivialCoal = false, float coalMomentum = 0.4)
  {

    mGeneratedEvents = 0;
    mInverseTriggerRatio = inputTriggerRatio;
    mHadRapidityMin = -1.5;
    mHadRapidityMax = 1.5;
    mHadronPdg = 0;
    mHFHadronPdgList = hfHadronPdgList;
    mNucleiPdgList = nucleiPdgList;
    mTrivialCoal = trivialCoal;
    mCoalMomentum = coalMomentum;
    Print();
  }

  ///  Destructor
  ~GeneratorPythia8HFHadToNuclei() = default;

  ///  Print the input
  void Print()
  {
    LOG(info) << "********** GeneratorPythia8HFHadToNuclei configuration dump **********";
    LOG(info) << Form("* Trigger ratio: %d", mInverseTriggerRatio);
    LOG(info) << Form("* Hadron rapidity: %f - %f", mHadRapidityMin, mHadRapidityMax);
    LOG(info) << Form("* Hadron pdg list: ");
    for (auto pdg : mHFHadronPdgList) {
      LOG(info) << Form("* %d ", pdg);
    }
    LOG(info) << Form("* Trivial coalescence: %d", mTrivialCoal);
    LOG(info) << Form("* Coalescence momentum: %f", mCoalMomentum);
    LOG(info) << Form("* Nuclei pdg list: ");
    for (auto pdg : mNucleiPdgList) {
      LOG(info) << Form("* %d ", pdg);
    }
    LOG(info) << "***********************************************************************";
  }

  bool Init() override
  {
    addSubGenerator(0, "Minimum bias");
    addSubGenerator(1, "HF + Coalescence");
    return o2::eventgen::GeneratorPythia8::Init();
  }

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
      // Alternate hadrons if enabled (with the same ratio)
      if (mHFHadronPdgList.size() >= 1) {
        int iHadron = nInjectedEvents % mHFHadronPdgList.size();
        mHadronPdg = mHFHadronPdgList[iHadron];
        LOG(info) << "Selected hadron: " << mHFHadronPdgList[iHadron];
      }

      // Generate event of interest
      bool genOk = false;
      while (!genOk) {
        if (GeneratorPythia8::generateEvent()) {
          genOk = selectEvent(mPythia.event);
        }
      }
      notifySubGenerator(1);
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

  bool selectEvent(Pythia8::Event& event)
  {
    for (auto iPart{0}; iPart < event.size(); ++iPart) {
      // search for hadron in rapidity window
      int id = std::abs(event[iPart].id());
      float rap = event[iPart].y();
      if (id == mHadronPdg && rap > mHadRapidityMin && rap < mHadRapidityMax) {
        LOG(debug) << "-----------------------------------------------------";
        LOG(debug) << "Found hadron " << event[iPart].id() << " with rapidity " << rap << " and daughters " << event[iPart].daughter1() << " " << event[iPart].daughter2();
        // print pdg code of daughters
        LOG(debug) << "Daughters: ";
        for (int iDau = event[iPart].daughter1(); iDau <= event[iPart].daughter2(); ++iDau) {
          LOG(debug) << "Daughter " << iDau << ": " << event[iDau].id();
        }
        bool isCoalDone = CoalescencePythia8(event, mNucleiPdgList, mTrivialCoal, mCoalMomentum, event[iPart].daughter1(), event[iPart].daughter2());
        if (isCoalDone) {
          LOG(debug) << "Coalescence process found for hadron " << event[iPart].id() << " with daughters " << event[iPart].daughter1() << " " << event[iPart].daughter2();
          LOG(debug) << "Check updated daughters: ";
          for (int iDau = event[iPart].daughter1(); iDau <= event[iPart].daughter2(); ++iDau) {
            LOG(debug) << "Daughter " << iDau << ": " << event[iDau].id();
          }
          return true;
        }
      }
    }
    return false;
  };

 private:
  // Interface to override import particles
  Pythia8::Event mOutputEvent;

  // Properties of selection
  int mHadronPdg;
  float mHadRapidityMin;
  float mHadRapidityMax;
  unsigned int mUsedSeed;

  // Control gap-triggering
  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;

  // Control alternate trigger on different hadrons
  std::vector<int> mHFHadronPdgList = {};
  std::vector<unsigned int> mNucleiPdgList = {};

  bool mTrivialCoal = false; /// if true, the coalescence is done without checking the distance in the phase space of the nucleons
  float mCoalMomentum; /// coalescence momentum
};


///___________________________________________________________
FairGenerator *generateHFHadToNuclei(int input_trigger_ratio = 5, std::vector<int> hf_hadron_pdg_list = {}, std::vector<unsigned int> nuclei_pdg_list = {}, bool trivial_coal = false, float coal_momentum = 0.4)
{
  auto myGen = new GeneratorPythia8HFHadToNuclei(input_trigger_ratio, hf_hadron_pdg_list, nuclei_pdg_list, trivial_coal, coal_momentum);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}