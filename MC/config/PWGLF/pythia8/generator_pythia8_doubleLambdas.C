#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TDatabasePDG.h"
#include "TMath.h"
#include "TParticlePDG.h"
#include "TRandom3.h"
#include "TSystem.h"
#include "TVector2.h"
#include "fairlogger/Logger.h"
#include <cmath>
#include <fstream>
#include <string>
#include <vector>
using namespace Pythia8;
#endif

/// Event generator using Pythia ropes
/// One event of interest is triggered after n minimum-bias events.
/// Event of interest : an event that contains at least two generated (anti-)Lambdas

class GeneratorPythia8DoubleLambda : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8DoubleLambda(int gapSize = 4, double minPt = 0.2, double maxPt = 10, double maxEta = 0.8)
      : o2::eventgen::GeneratorPythia8(),
        mGapSize(gapSize),
        mMinPt(minPt),
        mMaxPt(maxPt),
        mMaxEta(maxEta)
  {
    fmt::printf(
        ">> Pythia8 generator: two (anti-)Lambdas, gap = %d, minPtLambda = %f, maxPtLambda = %f, |etaLambda| < %f\n", gapSize, minPt, maxPt, maxEta);
  }
  /// Destructor
  ~GeneratorPythia8DoubleLambda() = default;

  bool Init() override
  {
    addSubGenerator(0, "Pythia8 events with two (anti-)Lambdas");
    return o2::eventgen::GeneratorPythia8::Init();
  }

protected:
  /// Check if particle is physical primary or from HF decay
  bool isLambdaPhysicalPrimaryOrFromHF(const Pythia8::Particle &p, const Pythia8::Event &event)
  {
    // Select only final-state particles
    if (!p.isFinal())
    {
      return false;
    }

    // Walk up ancestry
    int motherId = p.mother1();

    while (motherId > 0)
    {

      // Get mother
      const auto &mother = event[motherId];
      const int absMotherPdg = std::abs(mother.id());

      // Check if particle is from HF decay
      if ((absMotherPdg / 100 == 4) || (absMotherPdg / 100 == 5) || (absMotherPdg / 1000 == 4) || (absMotherPdg / 1000 == 5))
      {
        return true;
      }

      // Reject non-physical primary hadrons
      if (mother.isHadron() && mother.tau0() > 1.0)
      {
        return false;
      }
      motherId = mother.mother1();
    }
    return true;
  }

  bool generateEvent() override
  {
    fmt::printf(">> Generating event %d\n", mGeneratedEvents);

    bool genOk = false;
    int localCounter{0};
    constexpr int kMaxTries{100000};

    // Accept mGapSize events unconditionally, then one triggered event
    if (mGeneratedEvents % (mGapSize + 1) < mGapSize)
    {
      genOk = GeneratorPythia8::generateEvent();
      fmt::printf(">> Gap-event (no strangeness check)\n");
    }
    else
    {
      while (!genOk && localCounter < kMaxTries)
      {
        if (GeneratorPythia8::generateEvent())
        {
          genOk = selectEvent(mPythia.event);
        }
        localCounter++;
      }
      if (!genOk)
      {
        fmt::printf("Failed to generate triggered event after %d tries\n", kMaxTries);
        return false;
      }
      fmt::printf(">> Triggered event: event accepted after %d iterations (double (anti-)Lambdas)\n", localCounter);
    }

    notifySubGenerator(0);
    mGeneratedEvents++;
    return true;
  }

  bool selectEvent(Pythia8::Event &event)
  {

    std::vector<int> particleID;
    int nLambda{0};

    for (int i = 0; i < event.size(); i++)
    {
      const auto &p = event[i];
      if (std::abs(p.eta()) > mMaxEta || p.pT() < mMinPt || p.pT() > mMaxPt)
        continue;
      if (!isLambdaPhysicalPrimaryOrFromHF(p, event))
        continue;

      if (std::abs(p.id()) == 3122)
        nLambda++;

      particleID.emplace_back(i);
    }
    if (nLambda < 2)
      return false;

    return true;
  }

private:
  int mGapSize{4};
  double mMinPt{0.2};
  double mMaxPt{10.0};
  double mMaxEta{0.8};
  uint64_t mGeneratedEvents{0};
};

///___________________________________________________________
FairGenerator *generateDoubleLambda(int gap = 4, double minPt = 0.2, double maxPt = 10, double maxEta = 0.8)
{

  auto myGenerator = new GeneratorPythia8DoubleLambda(gap, minPt, maxPt, maxEta);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGenerator->readString("Random:setSeed on");
  myGenerator->readString("Random:seed " + std::to_string(seed));
  return myGenerator;
}
