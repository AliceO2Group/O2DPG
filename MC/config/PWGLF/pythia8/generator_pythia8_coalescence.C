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
    std::vector<int> protons[2], neutrons[2], lambdas[2];
    for (auto iPart{0}; iPart < event.size(); ++iPart)
    {
      if (std::abs(event[iPart].y()) > 1.) // skip particles with y > 1
      {
        continue;
      }
      switch (std::abs(event[iPart].id()))
      {
      case 2212:
        protons[event[iPart].id() > 0].push_back(iPart);
        break;
      case 2112:
        neutrons[event[iPart].id() > 0].push_back(iPart);
        break;
      case 3122:
        lambdas[event[iPart].id() > 0].push_back(iPart);
        break;
      default:
        break;
      }
    }
    const double coalescenceRadius{0.5 * 1.122462 * mCoalMomentum}; /// 1.122462 [2^(1/6)] from PRL 126, 101101 (2021), only for 3 body coalescence

    auto coalescence = [&](int iC, int pdgCode, float mass, int iD1, int iD2, int iD3) {
      auto p1 = event[iD1].p();
      auto p2 = event[iD2].p();
      auto p3 = event[iD3].p();
      auto p = p1 + p2 + p3;
      p1.bstback(p);
      p2.bstback(p);
      p3.bstback(p);

      if (p1.pAbs() <= coalescenceRadius && p2.pAbs() <= coalescenceRadius && p3.pAbs() <= coalescenceRadius)
      {
        p.e(std::hypot(p.pAbs(), mass));
        /// In order to avoid the transport of the mother particles, but to still keep them in the stack, we set the status to negative and we mark the nucleus status as 94 (decay product)
        event.append((iC * 2 - 1) * pdgCode, 94, 0, 0, 0, 0, 0, 0, p.px(), p.py(), p.pz(), p.e(), mass);
        event[iD1].statusNeg();
        event[iD1].daughter1(event.size() - 1);
        event[iD2].statusNeg();
        event[iD2].daughter1(event.size() - 1);
        event[iD3].statusNeg();
        event[iD3].daughter1(event.size() - 1);

        fmt::printf(">> Adding a %i with p = %f, %f, %f, E = %f\n", (iC * 2 - 1) * pdgCode, p.px(), p.py(), p.pz(), p.e());

        return true;
      }
      return false;
    };

    for (int iC{0}; iC < 2; ++iC)
    {
      for (int iP{0}; iP < protons[iC].size(); ++iP) {
        for (int iN{0}; iN < neutrons[iC].size(); ++iN) {
          /// H3L loop
          for (int iL{0}; iL < lambdas[iC].size(); ++iL) {
            if (coalescence(iC, 1010010030, 2.991134, protons[iC][iP], neutrons[iC][iN], lambdas[iC][iL])) {
              return true;
            }
          }
          /// H3 loop
          for (int iN2{iN + 1}; iN2 < neutrons[iC].size(); ++iN2) {
            if (coalescence(iC, 1000010030, 2.80892113298, protons[iC][iP], neutrons[iC][iN], neutrons[iC][iN2])) {
              return true;
            }
          }
          /// He3 loop
          for (int iP2{iP + 1}; iP2 < protons[iC].size(); ++iP2) {
            if (coalescence(iC, 1000020030, 2.808391, protons[iC][iP], protons[iC][iP2], neutrons[iC][iN])) {
              return true;
            }
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
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
