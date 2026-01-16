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

/// Event generator using Pythia ropes for Ξ and Ω production in jets.
/// Jets are defined as particles within a cone around the highest-pT particle
/// (approximate jet axis) and include charged final-state particles that are
/// either physical primaries or from heavy-flavor decays.
/// Jets must be fully within the acceptance and have pT > 10 GeV.
/// One event of interest is generated after 4 minimum-bias events.

class GeneratorPythia8StrangenessInJet : public o2::eventgen::GeneratorPythia8 {
public:
  /// Constructor
  GeneratorPythia8StrangenessInJet(double ptJetMin = 10.0, double Rjet = 0.4, int gapSize = 4)
    : o2::eventgen::GeneratorPythia8(),
      mptJetMin(ptJetMin),
      mRjet(Rjet),
      mGapSize(gapSize)
  {
    fmt::printf(
      ">> Pythia8 generator: Xi/Omega inside jets with pt_{jet} > %.1f GeV, R_{jet} = %.1f, gap = %d\n",
      ptJetMin, Rjet, gapSize);
  }
  /// Destructor
  ~GeneratorPythia8StrangenessInJet() = default;

  bool Init() override {
    addSubGenerator(0, "Pythia8 events with Xi/Omega inside jets");
    return o2::eventgen::GeneratorPythia8::Init();
  }

protected:
  /// Check if particle is physical primary or from HF decay
  bool isPhysicalPrimaryOrFromHF(const Pythia8::Particle& p, const Pythia8::Event& event)
  {
    // Select only final-state particles
    if (!p.isFinal()) {
      return false;
    }

    // Particle species selection
    const int absPdg = std::abs(p.id());
    if (absPdg!=211 && absPdg!=321 && absPdg!= 2212 && absPdg!=1000010020 && absPdg!=11 && absPdg!=13)
      return false;

    // Walk up ancestry
    int motherId = p.mother1();

    while (motherId > 0) {

      // Get mother
      const auto& mother = event[motherId];
      const int absMotherPdg = std::abs(mother.id());

      // Check if particle is from HF decay
      if ((absMotherPdg / 100 == 4) || (absMotherPdg / 100 == 5) || (absMotherPdg / 1000 == 4) || (absMotherPdg / 1000 == 5)) {
        return true;
      }

      // Reject non-physical primary hadrons
      if (mother.isHadron() && mother.tau0() > 1.0) {
        return false;
      }
      motherId = mother.mother1();
    }
    return true;
  }

  // Compute delta phi
  double getDeltaPhi(double a1, double a2)
  {
    double deltaPhi{0.0};
    double phi1 = TVector2::Phi_0_2pi(a1);
    double phi2 = TVector2::Phi_0_2pi(a2);
    double diff = std::fabs(phi1 - phi2);

    if (diff <= M_PI)
      deltaPhi = diff;
    if (diff > M_PI)
      deltaPhi = 2.0 * M_PI - diff;

    return deltaPhi;
  }

  bool generateEvent() override {
    fmt::printf(">> Generating event %d\n", mGeneratedEvents);

    bool genOk = false;
    int localCounter{0};
    constexpr int kMaxTries{100000};

    // Accept mGapSize events unconditionally, then one triggered event
    if (mGeneratedEvents % (mGapSize + 1) < mGapSize) {
      genOk = GeneratorPythia8::generateEvent();
      fmt::printf(">> Gap-trigger accepted event (no strangeness check)\n");
    } else {
      while (!genOk && localCounter < kMaxTries) {
        if (GeneratorPythia8::generateEvent()) {
          genOk = selectEvent(mPythia.event);
        }
        localCounter++;
      }
      if (!genOk) {
        fmt::printf("Failed to generate triggered event after %d tries\n",kMaxTries);
        return false;
      }
      fmt::printf(">> Event accepted after %d iterations (Xi/Omega in jet)\n", localCounter);
    }

    notifySubGenerator(0);
    mGeneratedEvents++;
    return true;
  }

  bool selectEvent(Pythia8::Event &event) {

    double etaJet{-999.0}, phiJet{-999.0}, ptMax{0.0};
    std::vector<int> particleID;
    bool containsXiOrOmega{false};

    for (int i = 0; i < event.size(); i++) {
      const auto& p = event[i];
      if (std::abs(p.id()) == 3312 || std::abs(p.id()) == 3334)
        containsXiOrOmega = true;

      if (std::abs(p.eta()) > 0.8 || p.pT() < 0.1) continue;
      if (!isPhysicalPrimaryOrFromHF(p, event)) continue;
      particleID.emplace_back(i);

      if (p.pT() > ptMax) {
        ptMax = p.pT();
        etaJet = p.eta();
        phiJet = p.phi();
      }
    }
    if (ptMax == 0.0)
      return false;
    if (std::abs(etaJet) + mRjet > 0.8)
      return false;
    if (!containsXiOrOmega)
      return false;

    double ptJet{0.0};
    for (int i = 0 ; i < particleID.size() ; i++) {
      int id = particleID[i];
      const auto& p = event[id];

      double deltaEta = std::abs(p.eta() - etaJet);
      double deltaPhi = getDeltaPhi(p.phi(),phiJet);
      double deltaR = std::sqrt(deltaEta * deltaEta + deltaPhi * deltaPhi);
      if (deltaR < mRjet) {
        ptJet += p.pT();
      }
    }
    if (ptJet < mptJetMin)
      return false;

    return true;
  }

private:
  double   mptJetMin{10.0};
  double   mRjet{0.4};
  int      mGapSize{4};
  uint64_t mGeneratedEvents{0};
};

