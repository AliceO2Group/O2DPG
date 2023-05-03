
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

class GeneratorPythia8LongLivedGapTriggered : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8LongLivedGapTriggered(int input_pdg, int input_trigger_ratio = 1, int n_injected = 1, float pt_min = 1, float pt_max = 10)
  {
    mPdg = input_pdg;
    mNinjected = n_injected;
    mInverseTriggerRatio = input_trigger_ratio;
    mPtMin = pt_min;
    mPtMax = pt_max;
    mMass = getMass(input_pdg);
    mGeneratedEvents = 0;
    mAlternatingPDGsign = true;
  }

  /// Destructor
  ~GeneratorPythia8LongLivedGapTriggered() = default;

  /// Randomize the PDG code sign of core particle
  void setAlternatingPDGsign(bool val) { mAlternatingPDGsign = val; }

  /// Set transverse momentum
  void setPt(float pt_min, float pt_max)
  {
    mPtMin = pt_min;
    mPtMax = pt_max;
  }

  /// Set pseudorapidity
  void setEta(float eta_min, float eta_max)
  {
    mEtaMin = eta_min;
    mEtaMax = eta_max;
  }

  /// Set pseudorapidity
  void setNinjected(unsigned long n_injected) { mNinjected = n_injected; }

  /// Get mass from TParticlePDG
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

  Bool_t importParticles() override
  {
    GeneratorPythia8::importParticles();
    if (mGeneratedEvents % mInverseTriggerRatio == 0)
    {
      static int sign = 1;
      for (int i = 0; i < mNinjected; ++i)
      {
        const double pt = gRandom->Uniform(mPtMin, mPtMax);
        const double eta = gRandom->Uniform(mEtaMin, mEtaMax);
        const double phi = gRandom->Uniform(0, TMath::TwoPi());
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double pz{pt * std::sinh(eta)};
        const double et{std::hypot(std::hypot(pt, pz), mMass)};
        sign *= 1 - 2 * mAlternatingPDGsign;
        mParticles.push_back(TParticle(sign * mPdg, 1, -1, -1, -1, -1, px, py, pz, et, 0., 0., 0., 0.));
        // make sure status code is encoded properly. Transport flag will be set by default and we have nothing
        // to do since all pushed particles should be tracked.
        o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back());
      }
    }
    mGeneratedEvents++;
    return true;
  }

private:
  int mPdg = 0;     /// particle mPdg code
  double mMass = 0; /// particle mass [GeV/c^2]

  double mPtMin;        /// minimum transverse momentum for generated particles
  double mPtMax;        /// maximum transverse momentum for generated particles
  double mEtaMin = -1.; /// minimum pseudorapidity for generated particles
  double mEtaMax = +1.; /// maximum pseudorapidity for generated particles

  bool mAlternatingPDGsign = true; /// bool to randomize the PDG code of the core particle

  int mNinjected = 1; /// Number of injected particles

  // Control gap-triggering
  unsigned long long mGeneratedEvents; /// number of events generated so far
  int mInverseTriggerRatio;            /// injection gap
};

///___________________________________________________________
FairGenerator *generateLongLivedGapTriggered(int mPdg, int input_trigger_ratio, int n_injected = 1, float pt_min = 1, float pt_max = 10, bool alternate_sign = true)
{
  auto myGen = new GeneratorPythia8LongLivedGapTriggered(mPdg, input_trigger_ratio, n_injected, pt_min, pt_max);
  myGen->setAlternatingPDGsign(alternate_sign);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
