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
#include "fairlogger/Logger.h"
#include "fastjet/ClusterSequence.hh"
#include <cmath>
#include <fstream>
#include <string>
#include <vector>

using namespace Pythia8;
using namespace fastjet;
#endif

/// Pythia8 event generator for pp collisions
/// Selection of events with Xi or Omega inside jets with pt > 10 GeV
/// Jets built from physical primaries OR HF decay products

class GeneratorPythia8StrangeInJet : public o2::eventgen::GeneratorPythia8 {
public:
  /// Constructor
  GeneratorPythia8StrangeInJet(double ptJetThreshold = 10.0,
                              double jetR = 0.4,
                              int gapSize = 4)
    : o2::eventgen::GeneratorPythia8(),
      mPtJetThreshold(ptJetThreshold),
      mJetR(jetR),
      mGapSize(gapSize)
  {
    fmt::printf(
      ">> Pythia8 generator: Xi/Omega inside jets with ptJet > %.1f GeV, R = %.1f, gap = %d\n",
      ptJetThreshold, jetR, gapSize);
  }

  ~GeneratorPythia8StrangeInJet() = default;

  bool Init() override {
    addSubGenerator(0, "Pythia8 events with Xi/Omega inside jets");
    return o2::eventgen::GeneratorPythia8::Init();
  }

protected:
  /// Check if particle is physical primary OR from HF decay
  bool isPhysicalPrimaryOrFromHF(const Pythia8::Particle& p,
                                const Pythia8::Event& event)
  {
    // Must be final
    if (!p.isFinal()) {
      return false;
    }

    // Physical primary: no real mother (or beam)
    if (p.mother1() <= 0) {
      return true;
    }

    // Walk up ancestry to identify charm or beauty
    int motherIdx = p.mother1();
    while (motherIdx > 0) {
      const auto& mother = event[motherIdx];
      int absPdg = std::abs(mother.id());

      // Charm or beauty hadrons
      if ((absPdg / 100 == 4) || (absPdg / 100 == 5) ||
          (absPdg / 1000 == 4) || (absPdg / 1000 == 5)) {
        return true;
      }

      // Stop at beam
      if (mother.mother1() <= 0) {
        break;
      }
      motherIdx = mother.mother1();
    }

    return false;
  }

  bool generateEvent() override {
    fmt::printf(">> Generating event %lu\n", mGeneratedEvents);

    bool genOk = false;
    int localCounter{0};

    // Accept mGapSize events unconditionally, then one triggered event
    if (mGeneratedEvents % (mGapSize + 1) < mGapSize) {
      genOk = GeneratorPythia8::generateEvent();
      fmt::printf(">> Gap-trigger accepted event (no strangeness check)\n");
    } else {
      while (!genOk) {
        if (GeneratorPythia8::generateEvent()) {
          genOk = selectEvent(mPythia.event);
        }
        localCounter++;
      }
      fmt::printf(">> Event accepted after %d iterations (Xi/Omega in jet)\n",
                  localCounter);
    }

    notifySubGenerator(0);
    mGeneratedEvents++;
    return true;
  }

  bool selectEvent(Pythia8::Event &event) {
    const std::vector<int> pdgXiOmega = {3312, -3312, 3334, -3334};
    const double mpi = 0.1395704;

    std::vector<PseudoJet> fjParticles;

    for (int i = 0; i < event.size(); ++i) {
      const auto& p = event[i];

      // --- Jet input selection ---
      if (!p.isFinal()) continue;
      if (!p.isCharged()) continue;
      if (!isPhysicalPrimaryOrFromHF(p, event)) continue;
      if (std::abs(p.eta()) > 0.8) continue;

      double pt = std::sqrt(p.px() * p.px() + p.py() * p.py());
      if (pt < 0.1) continue;

      double energy = std::sqrt(p.p() * p.p() + mpi * mpi);

      PseudoJet pj(p.px(), p.py(), p.pz(), energy);
      pj.set_user_index(i);   // map back to Pythia index
      fjParticles.push_back(pj);
    }

    if (fjParticles.empty()) return false;

    JetDefinition jetDef(antikt_algorithm, mJetR);
    ClusterSequence cs(fjParticles, jetDef);
    auto jets = sorted_by_pt(cs.inclusive_jets(mPtJetThreshold));

    for (const auto& jet : jets) {
      for (const auto& c : jet.constituents()) {
        int idx = c.user_index();
        int pdg = event[idx].id();

        if (std::find(pdgXiOmega.begin(), pdgXiOmega.end(), pdg) != pdgXiOmega.end()) {
          fmt::printf(
            ">> Accepted jet: pt = %.2f, eta = %.2f, phi = %.2f, contains PDG %d\n",
            jet.pt(), jet.eta(), jet.phi(), pdg);
          return true;
        }
      }
    }

    return false;
  }

private:
  double   mPtJetThreshold{10.0};
  double   mJetR{0.4};
  int      mGapSize{4};
  uint64_t mGeneratedEvents{0};
};

