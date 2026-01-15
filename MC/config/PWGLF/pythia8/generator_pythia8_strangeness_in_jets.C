#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"

#include "Pythia8/Pythia.h"

#include <fastjet/PseudoJet.hh>
#include <fastjet/JetDefinition.hh>
#include <fastjet/ClusterSequence.hh>

#include <cmath>
#include <vector>
#include <string>
#include <algorithm>

using namespace Pythia8;
using namespace fastjet;

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
    if (!p.isFinal()) {
      return false;
    }

    const int absPdg = std::abs(p.id());

    // Particle species selection
    const bool isAcceptedSpecies = (absPdg == 211 || absPdg == 321 || absPdg == 2212 || absPdg == 1000010020 || absPdg == 11 || absPdg == 13);

    if (!isAcceptedSpecies) {
      return false;
    }

    // Walk up ancestry
    int motherIdx = p.mother1();

    while (motherIdx > 0) {
      const auto& mother = event[motherIdx];
      const int absMotherPdg = std::abs(mother.id());

      // Charm or beauty hadron → accept (HF decay)
      if ((absMotherPdg / 100 == 4) || (absMotherPdg / 100 == 5) || (absMotherPdg / 1000 == 4) || (absMotherPdg / 1000 == 5)) {
        return true;
      }

      // Weakly decaying hadron → reject (non-physical primary)
      if (mother.isHadron() && mother.tau0() > 1.0) {
        return false;
      }
      motherIdx = mother.mother1();
    }
    return true;
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

    std::vector<fastjet::PseudoJet> fjParticles;

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

      fastjet::PseudoJet pj(p.px(), p.py(), p.pz(), energy);
      pj.set_user_index(i);   // map back to Pythia index
      fjParticles.push_back(pj);
    }

    if (fjParticles.empty()) return false;

    fastjet::JetDefinition jetDef(fastjet::antikt_algorithm, mJetR);
    fastjet::ClusterSequence cs(fjParticles, jetDef);
    auto jets = fastjet::sorted_by_pt(cs.inclusive_jets(mPtJetThreshold));

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

