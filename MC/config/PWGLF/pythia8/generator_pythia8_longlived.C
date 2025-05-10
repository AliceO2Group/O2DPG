
#if !defined(__CLING__) || defined(__ROOTCLING__)
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
#endif

class GeneratorPythia8LongLivedGun : public o2::eventgen::GeneratorPythia8
{
public:
  /// constructor
  GeneratorPythia8LongLivedGun(int input_pdg, int nInject = 1, float ptMin = 1, float ptMax = 10, float etaMin = -1.0, float etaMax = 1.0, float phiMin = 0.0, float phiMax = TMath::Pi(), int input_pdg2 = -1) : pdg{input_pdg}, nParticles{nInject}, genMinPt{ptMin}, genMaxPt{ptMax}, genMinEta{etaMin}, genMaxEta{etaMax}, genMinPhi{phiMin}, genMaxPhi{phiMax},  m{getMass(input_pdg)}, pdg2{input_pdg2}
  {
  }

  ///  Destructor
  ~GeneratorPythia8LongLivedGun() = default;

  /// randomize the PDG code sign of core particle
  void setRandomizePDGsign(bool val) { randomizePDGsign = val; }

  /// get mass from TParticlePDG
  static double getMass(int input_pdg)
  {
    double mass = 0;
    if (TDatabasePDG::Instance())
    {
      TParticlePDG *particle = TDatabasePDG::Instance()->GetParticle(input_pdg);
      if (particle) {
        mass = particle->Mass();
      } else {
        std::cout << "===> Unknown particle requested with PDG " << input_pdg << ", mass set to 0" << std::endl;
      }
    }
    return mass;
  }

  //__________________________________________________________________
  Bool_t importParticles() override
  {
    GeneratorPythia8::importParticles();
    static int sign{1};
    for (int i{0}; i < nParticles; ++i)
    {
      const double pt = gRandom->Uniform(genMinPt, genMaxPt);
      const double eta = gRandom->Uniform(genMinEta, genMaxEta);
      const double phi = gRandom->Uniform(genMinPhi, genMaxPhi);
      const double px{pt * std::cos(phi)};
      const double py{pt * std::sin(phi)};
      const double pz{pt * std::sinh(eta)};
      const double et{std::hypot(std::hypot(pt, pz), m)};
      sign *= randomizePDGsign ? -1 : 1;
      mParticles.push_back(TParticle(sign * pdg, 1, -1, -1, -1, -1, px, py, pz, et, 0., 0., 0., 0.));
      // make sure status code is encoded properly. Transport flag will be set by default and we have nothing
      // to do since all pushed particles should be tracked.
      o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back());
    }

    if (pdg2 != -1)
    {
      for (int i{0}; i < nParticles; ++i)
      {
        const double pt = gRandom->Uniform(genMinPt, genMaxPt);
        const double eta = gRandom->Uniform(genMinEta, genMaxEta);
        const double phi = gRandom->Uniform(genMinPhi, genMaxPhi);
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double pz{pt * std::sinh(eta)};
        const double et{std::hypot(std::hypot(pt, pz), m)};
        sign *= randomizePDGsign ? -1 : 1;
        mParticles.push_back(TParticle(sign * pdg2, 1, -1, -1, -1, -1, px, py, pz, et, 0., 0., 0., 0.));
        // make sure status code is encoded properly. Transport flag will be set by default and we have nothing
        // to do since all pushed particles should be tracked.
        o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back());
      }
    }

    return true;
  }

private:
  double genMinPt = 0.5;  /// minimum 3-momentum for generated particles
  double genMaxPt = 12.;  /// maximum 3-momentum for generated particles
  double genMinEta = -1.0; /// minimum pseudorapidity for generated particles
  double genMaxEta = +1.0; /// maximum pseudorapidity for generated particles
  double genMinPhi = 0.0; /// minimum pseudorapidity for generated particles
  double genMaxPhi = TMath::Pi(); /// maximum pseudorapidity for generated particles

  double m = 0;       /// particle mass [GeV/c^2]
  int pdg = 0;        /// particle pdg code
  int nParticles = 1; /// Number of injected particles

  int pdg2 = -1; /// optional second particle pdg code

  bool randomizePDGsign = true; /// bool to randomize the PDG code of the core particle
};

///___________________________________________________________
FairGenerator *generateLongLived(int pdg, int nInject, float ptMin = 1, float ptMax = 10, float etaMin = -1.0, float etaMax = 1.0, float phiMin = 0.0, float phiMax = TMath::Pi(), int pdg2 = -1)
{
  return new GeneratorPythia8LongLivedGun(pdg, nInject, ptMin, ptMax, etaMin, etaMax, phiMin, phiMax, pdg2);
}

