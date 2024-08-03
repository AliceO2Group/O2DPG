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

/// First version of the simple coalescence generator based PYTHIA8
/// TODO: extend to other nuclei (only He3 is implemented now)

class GeneratorPythia8Coalescence : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8Coalescence(int input_trigger_ratio = 1, double coal_momentum = 0.4)
      : o2::eventgen::GeneratorPythia8()
  {
    fmt::printf(">> Coalescence generator %d\n", input_trigger_ratio);
    mInverseTriggerRatio = input_trigger_ratio;
    mCoalMomentum = coal_momentum;
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
      bool genOk = false;
      int localCounter{0};
      while (!genOk)
      {
        if (GeneratorPythia8::generateEvent())
        {
          genOk = selectEvent(mPythia.event);
        }
        localCounter++;
      }
      fmt::printf(">> Coalescence successful after %i generations\n", localCounter);
      std::cout << std::endl << std::endl;
      notifySubGenerator(1);
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

  bool selectEvent(Pythia8::Event &event)
  {
    static int sign = -1; // start with antimatter
    std::vector<int> protons, neutrons, lambdas;
    for (auto iPart{0}; iPart < event.size(); ++iPart)
    {
      if (std::abs(event[iPart].y()) > 1.) // skip particles with y > 1
      {
        continue;
      }
      if (event[iPart].id() == 2212 * sign)
      {
        protons.push_back(iPart);
      }
      else if (event[iPart].id() == 2112 * sign)
      {
        neutrons.push_back(iPart);
      }
      else if (event[iPart].id() == 3122 * sign)
      {
        lambdas.push_back(iPart);
      }
    }
    double coalescenceRadius{0.5 * 1.122462 * mCoalMomentum}; /// 1.122462 [2^(1/6)] from PRL 126, 101101 (2021), only for 3 body coalescence
    if (protons.size() < 2 || neutrons.size() < 1) // at least 2 protons and 1 neutron
    {
      return false;
    }
    for (uint32_t i{0}; i < protons.size(); ++i)
    {
      for (uint32_t j{i + 1}; j < protons.size(); ++j)
      {
        for (uint32_t k{0}; k < neutrons.size(); ++k)
        {
          auto p1 = event[protons[i]].p();
          auto p2 = event[protons[j]].p();
          auto p3 = event[neutrons[k]].p();
          auto p = p1 + p2 + p3;
          p1.bstback(p);
          p2.bstback(p);
          p3.bstback(p);

          if (p1.pAbs() <= coalescenceRadius && p2.pAbs() <= coalescenceRadius && p3.pAbs() <= coalescenceRadius)
          {
            p.e(std::hypot(p.pAbs(), 2.80839160743));
            /// In order to avoid the transport of the mother particles, but to still keep them in the stack, we set the status to negative and we mark the nucleus status as 94 (decay product)
            event.append(sign * 1000020030, 94, 0, 0, 0, 0, 0, 0, p.px(), p.py(), p.pz(), p.e(), 2.80839160743);
            event[protons[i]].statusNeg();
            event[protons[i]].daughter1(event.size() - 1);
            event[protons[j]].statusNeg();
            event[protons[j]].daughter1(event.size() - 1);
            event[neutrons[k]].statusNeg();
            event[neutrons[k]].daughter1(event.size() - 1);

            fmt::printf(">> Adding a He3 with p = %f, %f, %f, E = %f\n", p.px(), p.py(), p.pz(), p.e());
            std::cout << std::endl;
            std::cout << std::endl;

            sign *= -1;
            return true;
          }
        }
      }
    }
    return false;
  }

private:
  // Control gap-triggering
  float mCoalMomentum = 0.4;
  uint64_t mGeneratedEvents = 0; /// number of events generated so far
  int mInverseTriggerRatio = 1;  /// injection gap
};

///___________________________________________________________
FairGenerator *generateCoalescence(int input_trigger_ratio, double coal_momentum = 0.4)
{
  auto myGen = new GeneratorPythia8Coalescence(input_trigger_ratio, coal_momentum);
  return myGen;
}
