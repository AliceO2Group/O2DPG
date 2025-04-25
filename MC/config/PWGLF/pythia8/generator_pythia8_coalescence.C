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
#include <cmath>
#include <vector>
#include <fstream>
#include <string>
using namespace Pythia8;
#endif

R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
#include "MC/config/common/external/generator/CoalescencePythia8.h"
/// First version of the simple coalescence generator based PYTHIA8

class GeneratorPythia8Coalescence : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8Coalescence(std::vector<unsigned int> pdgList, int input_trigger_ratio = 1, double coal_momentum = 0.4)
      : o2::eventgen::GeneratorPythia8()
  {
    fmt::printf(">> Coalescence generator %d\n", input_trigger_ratio);
    mInverseTriggerRatio = input_trigger_ratio;
    mCoalMomentum = coal_momentum;
    mPdgList = pdgList;
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
    fmt::printf(">> Generating event %d\n", mGeneratedEvents);
    // Simple straightforward check to alternate generators
    if (mGeneratedEvents % mInverseTriggerRatio == 0)
    {
      fmt::printf(">> Generating coalescence event %d\n", mGeneratedEvents);
      bool genOk = false;
      int localCounter{0};
      while (!genOk)
      {
        if (GeneratorPythia8::generateEvent())
        {
          genOk = CoalescencePythia8(mPythia.event, mPdgList, mCoalMomentum);
        }
        localCounter++;
      }
      fmt::printf(">> Coalescence successful after %i generations\n", localCounter);
      std::cout << std::endl << std::endl;
      notifySubGenerator(1);
    }
    else
    {
      fmt::printf(">> Generating minimum-bias event %d\n", mGeneratedEvents);
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
  std::vector<unsigned int> mPdgList; /// list of pdg codes to be generated
  float mCoalMomentum = 0.4; /// coalescence momentum
  uint64_t mGeneratedEvents = 0; /// number of events generated so far
  int mInverseTriggerRatio = 1;  /// injection gap
};

///___________________________________________________________
FairGenerator *generateCoalescence(std::vector<unsigned int> pdgList, int input_trigger_ratio, double coal_momentum = 0.4)
{
  auto myGen = new GeneratorPythia8Coalescence(pdgList, input_trigger_ratio, coal_momentum);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
///___________________________________________________________