#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "Pythia8/Pythia.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "fairlogger/Logger.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "TSystem.h"
#include "TMath.h"
#include <algorithm>
#include <cmath>
#include <vector>
#include <fstream>
#include <string>
using namespace Pythia8;
#endif

R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
#include "MC/config/common/external/generator/CoalescencePythia8.h"

/// First version of the simple coalescence generator based on PYTHIA8
class GeneratorPythia8Coalescence : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8Coalescence(std::vector<int> pdgList, int input_trigger_ratio = 1, double coal_momentum = 0.4)
      : o2::eventgen::GeneratorPythia8()
  {
    fmt::printf(">> Coalescence generator %d\n", input_trigger_ratio);
    mInverseTriggerRatio = input_trigger_ratio;
    mCoalMomentum = coal_momentum;
    mPdgList = pdgList;

    // CoalescencePythia8 accepts unsigned PDG codes
    for (auto pdg : mPdgList) {
      mAbsPdgList.push_back(static_cast<unsigned int>(std::abs(pdg)));
    }
  }

  /// Destructor
  ~GeneratorPythia8Coalescence() = default;

  bool Init() override
  {
    addSubGenerator(0, "Minimum bias");
    addSubGenerator(1, "Coalescence");
    return o2::eventgen::GeneratorPythia8::Init();
  }

protected:
  bool generateEvent() override
  {
    fmt::printf(">> Generating event %llu\n",
                static_cast<unsigned long long>(mGeneratedEvents));

    // Simple straightforward check to alternate generators
    if (mGeneratedEvents % mInverseTriggerRatio == 0)
    {
      fmt::printf(">> Generating coalescence event %llu\n",
                  static_cast<unsigned long long>(mGeneratedEvents));

      bool genOk = false;
      int localCounter{0};

      while (!genOk)
      {
        if (GeneratorPythia8::generateEvent())
        {
          // Store the event size before coalescence
          const int originalSize = mPythia.event.size();

          // Run coalescence with absolute PDG codes
          bool coalOk = CoalescencePythia8(
              mPythia.event, mAbsPdgList, false, mCoalMomentum);

          if (coalOk && mPythia.event.size() > originalSize) {
            for (int i = originalSize; i < mPythia.event.size(); ++i) {
              const int producedPdg = mPythia.event[i].id();
              if (std::find(mPdgList.begin(), mPdgList.end(), producedPdg) != mPdgList.end()) {
                genOk = true;
                break;
              }
            }
          }
        }

        localCounter++;
      }

      fmt::printf(">> Coalescence successful after %i generations\n",
                  localCounter);
      std::cout << std::endl << std::endl;
      notifySubGenerator(1);
    }
    else
    {
      fmt::printf(">> Generating minimum-bias event %llu\n",
                  static_cast<unsigned long long>(mGeneratedEvents));

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

private:
  std::vector<int> mPdgList;                /// Signed PDG codes
  std::vector<unsigned int> mAbsPdgList;    /// Absolute PDG codes for coalescence
  float mCoalMomentum = 0.4;                /// Coalescence momentum
  uint64_t mGeneratedEvents = 0;           /// Number of generated events
  int mInverseTriggerRatio = 1;            /// Injection gap
};

/// Factory function
FairGenerator* generateCoalescence(std::vector<int> pdgList,
                                  int input_trigger_ratio,
                                  double coal_momentum = 0.4)
{
  auto myGen = new GeneratorPythia8Coalescence(
      pdgList, input_trigger_ratio, coal_momentum);

  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));

  return myGen;
}
