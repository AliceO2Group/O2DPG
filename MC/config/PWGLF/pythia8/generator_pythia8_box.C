#include "Pythia8/Pythia.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "TMath.h"
#include <cmath>

using namespace Pythia8;

class GeneratorPythia8Box : public o2::eventgen::GeneratorPythia8
{
public:
  /// constructor
  GeneratorPythia8Box(int input_pdg, int nInject = 1, float ptMin = 1, float ptMax = 10) : pdg{input_pdg}, nParticles{nInject}, genMinPt{ptMin}, genMaxPt{ptMax}, m{getMass(input_pdg)}
  {
  }

  ///  Destructor
  ~GeneratorPythia8Box() = default;

  /// randomize the PDG code sign of core particle
  void setRandomizePDGsign(bool val) { randomizePDGsign = val; }

  /// get mass from TParticlePDG
  static double getMass(int input_pdg)
  {
    double mass = 0;
    if (TDatabasePDG::Instance())
    {
      TParticlePDG *particle = TDatabasePDG::Instance()->GetParticle(input_pdg);
      if (particle)
      {
        mass = particle->Mass();
      }
      else
      {
        std::cout << "===> Unknown particle requested with PDG " << input_pdg << ", mass set to 0" << std::endl;
      }
    }
    return mass;
  }

  Bool_t generateEvent() override
  {
    mPythia.event.reset();

    static int sign{1};
    for (int i{0}; i < nParticles; ++i)
    {
      const double pt = gRandom->Uniform(genMinPt, genMaxPt);
      const double eta = gRandom->Uniform(genMinEta, genMaxEta);
      const double phi = gRandom->Uniform(0, TMath::TwoPi());
      const double px{pt * std::cos(phi)};
      const double py{pt * std::sin(phi)};
      const double pz{pt * std::sinh(eta)};
      const double et{std::hypot(std::hypot(pt, pz), m)};
      sign *= randomizePDGsign ? -1 : 1;

      Particle myparticle;
      myparticle.id(pdg);
      myparticle.status(11);
      myparticle.px(px);
      myparticle.py(py);
      myparticle.pz(pz);
      myparticle.e(et);
      myparticle.m(m);
      myparticle.xProd(0);
      myparticle.yProd(0);
      myparticle.zProd(0);

      mPythia.event.append(myparticle);
    }
    mPythia.next();
    return true;
  }

  //__________________________________________________________________

private:
  double genMinPt = 0.5;  /// minimum 3-momentum for generated particles
  double genMaxPt = 12.;  /// maximum 3-momentum for generated particles
  double genMinEta = -1.; /// minimum pseudorapidity for generated particles
  double genMaxEta = +1.; /// maximum pseudorapidity for generated particles

  double m = 0;       /// particle mass [GeV/c^2]
  int pdg = 0;        /// particle pdg code
  int nParticles = 1; /// Number of injected particles

  bool randomizePDGsign = true; /// bool to randomize the PDG code of the core particle
};

///___________________________________________________________
FairGenerator *generatePythia8Box(int pdg, int nInject, float ptMin = 1, float ptMax = 10)
{
  return new GeneratorPythia8Box(pdg, nInject, ptMin, ptMax);
}
