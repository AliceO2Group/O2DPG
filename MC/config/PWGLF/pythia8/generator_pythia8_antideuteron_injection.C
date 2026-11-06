#if !defined(__CLING__) || defined(__ROOTCLING__)

#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include "fairlogger/Logger.h"

#include <cmath>
#include <cstdint>
#include <string>

#endif // !defined(__CLING__) || defined(__ROOTCLING__)

/// PYTHIA8 event generator with antideuteron injection.
/// Events are generated until a final-state antiproton within the specified etaMax is found.
/// The antiproton is then replaced by an antideuteron with twice its momentum.

class GeneratorPythia8AntideuteronInjection
    : public o2::eventgen::GeneratorPythia8 {

 public:

  GeneratorPythia8AntideuteronInjection(double etaMax = 0.8)
      : o2::eventgen::GeneratorPythia8(),
        mEtaMax(etaMax) {}

  ~GeneratorPythia8AntideuteronInjection() override = default;

  bool Init() override {
    addSubGenerator(0, "Pythia8 events with antideuterons");
    return o2::eventgen::GeneratorPythia8::Init();
  }

 protected:

  
  bool generateEvent() override {
    constexpr int maxAttempts = 10000;
    for (int attempt = 0; attempt < maxAttempts; ++attempt) {
      if (!GeneratorPythia8::generateEvent()) {
        return false;
      }

      if (EventHasAntideuteron(mPythia.event)) {
        LOG(debug) << ">> An antideuteron was formed!";

        notifySubGenerator(0);
        ++mGeneratedEvents;

        return true;
      }
    }

    LOG(error) << "Failed to generate an antideuteron after " << maxAttempts << " attempts";
    return false;
  }

  bool EventHasAntideuteron(Pythia8::Event& event) {

    const double md = 1.87561294257; // Deuteron mass in GeV/c^2
    const int pdgAntid = -1000010020; // Antideuteron PDG code

    for (int iPart = 0; iPart < event.size(); ++iPart) {

      if (!event[iPart].isFinal()) {
        continue;
      }

      if (std::abs(event[iPart].eta()) > mEtaMax) {
        continue;
      }

      if (event[iPart].id() != -2212) {
        continue;
      }

      double px = 2.0 * event[iPart].px();
      double py = 2.0 * event[iPart].py();
      double pz = 2.0 * event[iPart].pz();
      double energy = std::sqrt(md * md + px * px + py * py + pz * pz);

      // Remove antiproton from final state
      event[iPart].statusNeg();

      // Add antideuteron
      const int iAntid = event.size();
      event.append(pdgAntid, 121, iPart, 0, 0, 0, 0, 0, px, py, pz, energy, md);
      // Update daughter indices
      event[iPart].daughter1(iAntid);
      event[iPart].daughter2(iAntid);
      return true;
    }
    return false;
  }

 private:

  double mEtaMax = 0.8;
  uint64_t mGeneratedEvents = 0;
};

/// Generator factory

FairGenerator* generateAntideuterons(double etaMax = 0.8) {

  auto* myGenerator = new GeneratorPythia8AntideuteronInjection(etaMax);
  auto seed = gRandom->TRandom::GetSeed() % 900000000;

  myGenerator->readString("Random:setSeed = on");
  myGenerator->readString("Random:seed = " + std::to_string(seed));

  return myGenerator;
}
