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
#include <cmath>
#include <fstream>
#include <string>
#include <vector>
using namespace Pythia8;
#endif

/// Pythia8 event generator for pp collisions
/// Selection of events with leading particle (pt>ptThreshold) and containing
/// one strange hadron extracted randomly (K0, Lambda, Xi, Omega)

class GeneratorPythia8HighPtStrangeness : public o2::eventgen::GeneratorPythia8 {
public:
  /// Constructor
  GeneratorPythia8HighPtStrangeness(double pt_leading = 5.0)
      : o2::eventgen::GeneratorPythia8() 
  {
    fmt::printf(">> Pythia8 generator: ptLeading > %.1f GeV/c\n", pt_leading);
    mPt_leading = pt_leading;
  }
  /// Destructor
  ~GeneratorPythia8HighPtStrangeness() = default;

  bool Init() override {
    addSubGenerator(0,"Pythia8 events containing high pt particle + strange hadrons");
    return o2::eventgen::GeneratorPythia8::Init();
  }

protected:
  bool generateEvent() override {
    fmt::printf(">> Generating event %d\n", mGeneratedEvents);

    bool genOk = false;
    int localCounter{0};
    while (!genOk) {
      if (GeneratorPythia8::generateEvent()) {
        genOk = selectEvent(mPythia.event);
      }
      localCounter++;
    }
    fmt::printf(">> Generation of event of interest successful after %i iterations\n",localCounter);
    std::cout << std::endl << std::endl;
    notifySubGenerator(0);

    mGeneratedEvents++;

    return true;
  }

  bool selectEvent(Pythia8::Event &event) {

    int pdg_of_interest[7] = {310, 3122, -3122, 3312, -3312, 3334, -3334};
    int partIndex = static_cast<int>(gRandom->Uniform(0,7));
     
    bool contains_particle_of_interest = false;
    double pt_max{0};
    for (auto iPart{0}; iPart < event.size(); ++iPart) {
      if (std::abs(event[iPart].eta()) > 0.8) {
        continue;
      }

      if (event[iPart].status() <= 0) {
        continue;
      }

      if (event[iPart].id() == pdg_of_interest[partIndex])
        contains_particle_of_interest = true;

      if ((!event[iPart].isNeutral()) && event[iPart].pT() > pt_max)
        pt_max = event[iPart].pT();
    }

    if (pt_max < mPt_leading)
      return false;

    return contains_particle_of_interest;
  }

private:
  double mPt_leading = 5.0;
  uint64_t mGeneratedEvents = 0;
};

///___________________________________________________________
FairGenerator *generateHighPtAndStrangeHadron(double pt_leading = 5.0) {

  auto myGenerator = new GeneratorPythia8HighPtStrangeness(pt_leading);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGenerator->readString("Random:setSeed on");
  myGenerator->readString("Random:seed " + std::to_string(seed));
  return myGenerator;
}
