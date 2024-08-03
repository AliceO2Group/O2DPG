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
/// Selection of events with leading particle (pt>ptThreshold) and containing at
/// least one (anti)deuteron produced by simple coalescence

class GeneratorPythia8AntidAndHighPt : public o2::eventgen::GeneratorPythia8 {
public:
  /// Constructor
  GeneratorPythia8AntidAndHighPt(double p0 = 0.3, double pt_leading = 5.0)
      : o2::eventgen::GeneratorPythia8() {
    mP0 = p0;
    mPt_leading = pt_leading;
  }
  /// Destructor
  ~GeneratorPythia8AntidAndHighPt() = default;

  bool Init() override {
    addSubGenerator(0, "Pythia8 with (anti)deuterons and high pt particle");
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
    fmt::printf(
        ">> Generation of event of interest successful after %i iterations\n",
        localCounter);
    std::cout << std::endl << std::endl;
    notifySubGenerator(0);

    mGeneratedEvents++;

    return true;
  }

  bool selectEvent(Pythia8::Event &event) {

    bool has_particle_of_interest = false;

    // Deuteron Mass [GeV]
    double md = 1.87561294257;

    // Protons and Neutrons
    vector<int> proton_ID;
    vector<int> neutron_ID;
    vector<int> proton_status;
    vector<int> neutron_status;

    // ptMax
    double pt_max{0};

    for (auto iPart{0}; iPart < event.size(); ++iPart) {

      // Only final-state particles
      if (event[iPart].status() <= 0) {
        continue;
      }

      //(Anti)Proton selection
      if (abs(event[iPart].id()) == 2212) {
        proton_ID.push_back(iPart);
        proton_status.push_back(0);
      }

      //(Anti)Neutron selection
      if (abs(event[iPart].id()) == 2112) {
        neutron_ID.push_back(iPart);
        neutron_status.push_back(0);
      }

      if (std::abs(event[iPart].eta()) < 0.8 && (!event[iPart].isNeutral()) &&
          event[iPart].pT() > pt_max)
        pt_max = event[iPart].pT();
    }

    // Skip Events with no leading particle
    if (pt_max < mPt_leading)
      return false;

    if (proton_ID.size() < 1 || neutron_ID.size() < 1)
      return false;

    for (uint32_t ip = 0; ip < proton_ID.size(); ++ip) {

      // Skip used protons
      if (proton_status[ip] < 0) {
        continue;
      }
      for (uint32_t in = 0; in < neutron_ID.size(); ++in) {

        // Skip used neutrons
        if (neutron_status[in] < 0) {
          continue;
        }

        auto sign_p =
            event[proton_ID[ip]].id() / abs(event[proton_ID[ip]].id());
        auto sign_n =
            event[neutron_ID[in]].id() / abs(event[neutron_ID[in]].id());

        auto p1 = event[proton_ID[ip]].p();
        auto p2 = event[neutron_ID[in]].p();
        auto p = p1 + p2;
        p1.bstback(p);
        p2.bstback(p);

        // Coalescence
        if (p1.pAbs() <= mP0 && p2.pAbs() <= mP0 && sign_p == sign_n) {
          p.e(std::hypot(p.pAbs(), md));
          event.append(sign_p * 1000010020, 121, 0, 0, 0, 0, 0, 0, p.px(),
                       p.py(), p.pz(), p.e(), md);
          event[proton_ID[ip]].statusNeg();
          event[proton_ID[ip]].daughter1(event.size() - 1);
          event[neutron_ID[in]].statusNeg();
          event[neutron_ID[in]].daughter1(event.size() - 1);
          proton_status[ip] = -1;
          neutron_status[in] = -1;
          has_particle_of_interest = true;
        }
      }
    }

    return has_particle_of_interest;
  }

private:
  double mP0 = 0.3;
  double mPt_leading = 5.0;
  uint64_t mGeneratedEvents = 0;
};

///___________________________________________________________
FairGenerator *generateAntidAndHighPt(double p0 = 0.3,
                                      double pt_leading = 5.0) {

  auto myGenerator = new GeneratorPythia8AntidAndHighPt(p0, pt_leading);
  return myGenerator;
}
