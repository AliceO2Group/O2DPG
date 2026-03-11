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

/// Event of interest:
///   an event that contains at least one Sigma- or Sigma+
///   paired with at least one hadron of a specific PDG code,
///   and the pair has k* < kStarMax

class GeneratorPythia8SigmaHadron : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8SigmaHadron(int hadronPdg, int gapSize = 4, double minPt = 0.2,
                              double maxPt = 10, double maxEta = 0.8, double kStarMax = 1.0)
      : o2::eventgen::GeneratorPythia8(),
        mHadronPdg(hadronPdg),
        mGapSize(gapSize),
        mMinPt(minPt),
        mMaxPt(maxPt),
        mMaxEta(maxEta),
        mKStarMax(kStarMax)
  {
    fmt::printf(
        ">> Pythia8 generator: Sigma± + hadron(PDG=%d), gap = %d, minPt = %f, maxPt = %f, |eta| < %f, k* < %f\n",
        hadronPdg, gapSize, minPt, maxPt, maxEta, kStarMax);
  }

  ~GeneratorPythia8SigmaHadron() = default;

  bool Init() override
  {
    addSubGenerator(0, "Pythia8 events with Sigma± and a specific hadron");
    return o2::eventgen::GeneratorPythia8::Init();
  }

protected:
  /// Check whether particle descends from a Sigma+ or Sigma-
  bool isFromSigmaDecay(const Pythia8::Particle& p, const Pythia8::Event& event)
  {
    int motherId = p.mother1();

    while (motherId > 0) {
      const auto& mother = event[motherId];
      const int absMotherPdg = std::abs(mother.id());

      if (absMotherPdg == 3112 || absMotherPdg == 3222) {
        return true;
      }

      motherId = mother.mother1();
    }

    return false;
  }

  /// k* of a pair from invariant masses and 4-momenta
  /// k* = momentum of either particle in the pair rest frame
  double computeKStar(const Pythia8::Particle& p1, const Pythia8::Particle& p2) const
  {
    const double e = p1.e() + p2.e();
    const double px = p1.px() + p2.px();
    const double py = p1.py() + p2.py();
    const double pz = p1.pz() + p2.pz();
    const double s = e * e - px * px - py * py - pz * pz;
    if (s <= 0.) {
      return 1.e9;
    }
    const double m1 = p1.m();
    const double m2 = p2.m();
    const double term1 = s - std::pow(m1 + m2, 2);
    const double term2 = s - std::pow(m1 - m2, 2);
    const double lambda = term1 * term2;

    if (lambda <= 0.) {
      return 0.;
    }
    return 0.5 * std::sqrt(lambda / s);
  }

  bool generateEvent() override
  {
    fmt::printf(">> Generating event %llu\n", mGeneratedEvents);

    bool genOk = false;
    int localCounter{0};
    constexpr int kMaxTries{100000};

    // Accept mGapSize events unconditionally, then one triggered event
    if (mGeneratedEvents % (mGapSize + 1) < mGapSize) {
      genOk = GeneratorPythia8::generateEvent();
      fmt::printf(">> Gap-event (no trigger check)\n");
    } else {
      while (!genOk && localCounter < kMaxTries) {
        if (GeneratorPythia8::generateEvent()) {
          genOk = selectEvent(mPythia.event);
        }
        localCounter++;
      }

      if (!genOk) {
        fmt::printf("Failed to generate triggered event after %d tries\n", kMaxTries);
        return false;
      }

      fmt::printf(">> Triggered event: accepted after %d iterations (Sigma± + hadron PDG=%d, k* < %f)\n",
                  localCounter, mHadronPdg, mKStarMax);
    }

    notifySubGenerator(0);
    mGeneratedEvents++;
    return true;
  }

  bool selectEvent(Pythia8::Event& event)
  {
    std::vector<int> sigmaIndices;
    std::vector<int> hadronIndices;

    for (int i = 0; i < event.size(); i++) {
      const auto& p = event[i];

      if (std::abs(p.eta()) > mMaxEta || p.pT() < mMinPt || p.pT() > mMaxPt) {
        continue;
      }

      const int pdg = p.id();
      const int absPdg = std::abs(pdg);

      // Sigma- or Sigma+
      if (absPdg == 3112 || absPdg == 3222) {
        sigmaIndices.push_back(i);
      }

      if (std::abs(pdg) == mHadronPdg && !isFromSigmaDecay(p, event)) {
        hadronIndices.push_back(i);
      }
    }
    if (sigmaIndices.empty() || hadronIndices.empty()) {
      return false;
    }

    for (const auto iSigma : sigmaIndices) {
      for (const auto iHadron : hadronIndices) {

        if (iSigma == iHadron) {
          continue;
        }

        const auto& sigma = event[iSigma];
        const auto& hadron = event[iHadron];

        const double kStar = computeKStar(sigma, hadron);
        if (kStar < mKStarMax) {
          return true;
        }
      }
    }

    return false;
  }

private:
  int mHadronPdg{211};
  int mGapSize{4};
  double mMinPt{0.2};
  double mMaxPt{10.0};
  double mMaxEta{0.8};
  double mKStarMax{1.0};
  uint64_t mGeneratedEvents{0};
};

///___________________________________________________________
FairGenerator* generateSigmaHadron(int hadronPdg, int gap = 4, double minPt = 0.2,
                                   double maxPt = 10, double maxEta = 0.8, double kStarMax = 1.0)
{
  auto myGenerator = new GeneratorPythia8SigmaHadron(hadronPdg, gap, minPt, maxPt, maxEta, kStarMax);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGenerator->readString("Random:setSeed on");
  myGenerator->readString("Random:seed " + std::to_string(seed));
  return myGenerator;
}