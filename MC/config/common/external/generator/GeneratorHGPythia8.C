// HG-PYTHIA: heavy-ion events built from a Glauber model with eikonal NN
// interactions and minijet (hard scattering) counting, where each NN
// collision is represented by a PYTHIA 8 pp event with the matching number
// of multiparton interactions. The heavy-ion event is the sum of the pp
// events.
//
// Model: C. Loizides, A. Morsch, Phys. Lett. B773 (2017) 408 (arXiv:1705.08856)
// Reference implementation: https://github.com/abaty/HGPythia (A. Baty)
//
// The PYTHIA pp configuration (beams at sqrt(s_NN), SoftQCD:inelastic,
// decays...) is given through the usual GeneratorPythia8 parameters, e.g.
//   GeneratorPythia8.config=${O2DPG_MC_CONFIG_ROOT}/MC/config/common/pythia8/generator/pythia8_inel_536.cfg
// The collision energy used for the Glauber model is taken from PYTHIA.
//
// Differences with respect to the reference implementation:
// - the unused J/psi and bookkeeping parts are not ported
//
/// @author Marco Giacalone (marco.giacalone@cern.ch)
/// @date 09-2026

#include "Generators/GeneratorPythia8.h"
#include "SimConfig/SimConfig.h"
#include "SimulationDataFormat/MCEventHeader.h"
#include "SimulationDataFormat/MCGenProperties.h"
#include "SimulationDataFormat/ParticleStatus.h"
#include "Pythia8/Pythia.h"
#include "TF1.h"
#include "TF2.h"
#include "TMath.h"
#include "TParticle.h"
#include "TRandom3.h"
#include <fairlogger/Logger.h>
#include <array>
#include <memory>
#include <string>
#include <vector>

namespace o2
{
namespace eventgen
{

class GeneratorHGPythia8 : public GeneratorPythia8
{
 public:
  /// Number of bins for the hard scatterings per NN collision (and MPIs per PYTHIA event), as in the
  /// reference implementation: collisions with 20 or more hard scatterings are counted in the last bin (19)
  static constexpr int kMaxMPI = 20;
  /// Maximum number of consecutive PYTHIA events not matching any requested number of MPIs
  static constexpr long kMaxRejected = 10000000;

  GeneratorHGPythia8(int A = 208, int B = 208) : GeneratorPythia8(), mA(A), mB(B)
  {
    // the PYTHIA interface only describes the last NN collision: do not expose it as "pythia8"
    mInterfaceName = "hgpythia8";
    // defaults, overridden by the PYTHIA configuration file (GeneratorPythia8.config) read in Init
    readString("Beams:idA 2212");
    readString("Beams:idB 2212");
    readString("SoftQCD:inelastic on");
    readString("ParticleDecays:limitTau0 on");
    readString("ParticleDecays:tau0Max 10.");
  }
  ~GeneratorHGPythia8() override = default;

  /// Impact parameter range in fm. A non-positive bMax selects o2-sim --bMax,
  /// if given, otherwise 20 fm (10 fm for p-A, 5 fm for pp)
  void setImpactParameterRange(double bMin, double bMax)
  {
    mBMin = bMin;
    mBMax = bMax;
  }
  /// Hard (minijet) NN cross-section in mb, <0 takes it from the built-in energy table
  void setSigmaHard(double sigma) { mSigmaHardIn = sigma; }
  /// Soft NN cross-section in mb
  void setSigmaSoft(double sigma) { mSigmaSoft = sigma; }
  /// Include elastic NN scattering in the eikonal
  void setElastic(bool val) { mElastic = val; }

  /// Glauber information of the current event
  double getImpactParameter() const { return mImpactParameter; }
  int getNcoll() const { return mNcoll; }
  int getNcollHard() const { return mNcollHard; }
  int getNhard() const { return mNhard; }
  int getNpartProjectile() const { return mNpartProj; }
  int getNpartTarget() const { return mNpartTarg; }
  int getNpartBlackDisc() const { return mNpartBlackDisc; }
  int getNcollBlackDisc() const { return mNcollBlackDisc; }
  double getEccentricity() const { return mEccentricity; }

  Bool_t Init() override
  {
    if (mA < 1 || mA > 208 || mB < 1 || mB > 208) {
      LOG(fatal) << "GeneratorHGPythia8: mass numbers must be between 1 and 208, got A = " << mA << ", B = " << mB;
      return false;
    }
    // PYTHIA configuration, seeding and initialisation
    if (!GeneratorPythia8::Init()) {
      return false;
    }
    if (mPythia.settings.mode("Beams:idA") != 2212 || mPythia.settings.mode("Beams:idB") != 2212) {
      LOG(warn) << "GeneratorHGPythia8: PYTHIA is expected to generate pp collisions";
    }
    // Glauber random numbers seeded from the PYTHIA seed (0 means time dependent in both cases)
    mRandom = std::make_unique<TRandom3>(mPythia.settings.mode("Random:seed"));

    const double energy = mPythia.info.eCM();
    mSigmaHard = mSigmaHardIn >= 0 ? mSigmaHardIn : sigmaHardFromTable(energy);
    if (mSigmaHard < 0) {
      LOG(fatal) << "GeneratorHGPythia8: no hard cross-section available for sqrt(s_NN) = " << energy
                 << " GeV, please set it with setSigmaHard()";
      return false;
    }
    if (mBMax <= 0) {
      const auto simBMax = o2::conf::SimConfig::Instance().getBMax();
      mBMax = simBMax > 0 ? simBMax : ((mA == 1 && mB == 1) ? 5. : ((mA == 1 || mB == 1) ? 10. : 20.));
    }
    mDensity[0].reset(makeNucleonDensity(mA, "HGPythia8A"));
    mDensity[1].reset(makeNucleonDensity(mB, "HGPythia8B"));
    for (int j = 0; j < 2; ++j) {
      mX[j].resize(j == 0 ? mA : mB);
      mY[j].resize(j == 0 ? mA : mB);
      mWounded[j].resize(j == 0 ? mA : mB);
      mWoundedBlackDisc[j].resize(j == 0 ? mA : mB);
    }
    mHIEvent.init("HG-PYTHIA event", &mPythia.particleData);

    LOG(info) << "GeneratorHGPythia8: A = " << mA << ", B = " << mB << ", sqrt(s_NN) = " << energy
              << " GeV, sigma_hard = " << mSigmaHard << " mb, sigma_soft = " << mSigmaSoft
              << " mb, b in [" << mBMin << ", " << mBMax << "] fm, elastic " << mElastic;
    return true;
  }

  Bool_t generateEvent() override
  {
    std::array<int, kMaxMPI> nMPI{};
    sampleGlauber(nMPI);

    // Generate PYTHIA events until each NN collision has a partner with the
    // matching number of MPIs, and sum them
    mHIEvent.reset();
    int nNeeded = mNcoll;
    long nRejected = 0;
    const bool prune = !mGenConfig.includePartonEvent;
    auto select = [this](const Pythia8::Particle& p) {
      const int st = p.statusHepMC();
      return (st == 1 || st == 2 || st == 4) && mUserFilterFcn(p);
    };
    while (nNeeded > 0) {
      if (!mPythia.next()) {
        continue;
      }
      const int mpi = mPythia.info.nMPI();
      if (mpi >= kMaxMPI || nMPI[mpi] == 0) {
        if (++nRejected > kMaxRejected) {
          LOG(fatal) << "GeneratorHGPythia8: " << kMaxRejected << " consecutive PYTHIA events do not match the "
                     << "requested number of MPIs, check the PYTHIA configuration (SoftQCD:inelastic needed)";
          return false;
        }
        continue;
      }
      nRejected = 0;
      nMPI[mpi]--;
      nNeeded--;
      if (prune) {
        pruneEvent(mPythia.event, select);
      }
      mHIEvent += mPythia.event;
    }
    return true;
  }

  Bool_t importParticles() override
  {
    // same conversion as GeneratorPythia8::importParticles, without pruning again the summed event
    for (int i = 1; i < mHIEvent.size(); ++i) {
      const auto& particle = mHIEvent[i];
      auto st = o2::mcgenstatus::MCGenStatusEncoding(particle.statusHepMC(), particle.status()).fullEncoding;
      mParticles.push_back(TParticle(particle.id(), st,
                                     particle.mother1() - 1, particle.mother2() - 1,
                                     particle.daughter1() - 1, particle.daughter2() - 1,
                                     particle.px(), particle.py(), particle.pz(), particle.e(),
                                     particle.xProd(), particle.yProd(), particle.zProd(), particle.tProd()));
      mParticles.back().SetBit(ParticleStatus::kToBeDone, particle.statusHepMC() == 1);
    }
    return true;
  }

  void updateHeader(o2::dataformats::MCEventHeader* eventHeader) override
  {
    using Key = o2::dataformats::MCInfoKeys;
    eventHeader->putInfo<std::string>(Key::generator, "hgpythia8");
    eventHeader->putInfo<int>(Key::generatorVersion, PYTHIA_VERSION_INTEGER);
    eventHeader->SetB(mImpactParameter);
    eventHeader->putInfo<double>(Key::impactParameter, mImpactParameter);
    eventHeader->putInfo<double>(Key::planeAngle, 0.); // impact parameter along x
    eventHeader->putInfo<int>(Key::nColl, mNcoll);
    eventHeader->putInfo<int>(Key::nCollHard, mNcollHard);
    eventHeader->putInfo<int>(Key::nPart, mNpartProj + mNpartTarg);
    eventHeader->putInfo<int>(Key::nPartProjectile, mNpartProj);
    eventHeader->putInfo<int>(Key::nPartTarget, mNpartTarg);
    eventHeader->putInfo<float>(Key::sigmaInelNN, mSigmaSoft + mSigmaHard);
    eventHeader->putInfo<int>("nHard", mNhard);
    eventHeader->putInfo<int>("Npart_blackdisc", mNpartBlackDisc);
    eventHeader->putInfo<int>("Ncoll_blackdisc", mNcollBlackDisc);
    eventHeader->putInfo<float>("eccentricity", mEccentricity);
  }

 private:
  /// Hard cross-section (pT > 2 GeV) in mb as a function of sqrt(s_NN), from the reference implementation
  double sigmaHardFromTable(double energy) const
  {
    if (energy < 20) return 0.161440969;
    if (energy < 40) return 1.07414019;
    if (energy < 64) return 2.32993174;
    if (energy < 201) return 11.6641903;
    if (energy < 2800) return 85.2298813;
    if (energy < 5100) return 124.296341;
    if (energy < 5500) return 130.82;
    if (energy < 6400) return 144.17;
    if (energy < 8100) return 166.184998;
    if (energy < 9700) return 180.87;
    return -1;
  }

  /// Radial (radial and polar for deformed nuclei) nucleon density; a single nucleon (A = 1) is
  /// sampled from the exponential proton profile with R = 0.234 fm (rms charge radius), as in TGlauberMC
  static TF1* makeNucleonDensity(int A, const std::string& suffix)
  {
    auto name = [&suffix](const char* n) { return std::string(n) + suffix; };
    if (A == 208) {
      return new TF1(name("wsPb").c_str(), "7.208e-4*4.*TMath::Pi()*x^2/(1+exp((x-6.62)/0.546))", 0., 20.);
    }
    if (A == 197) {
      return new TF1(name("wsAu").c_str(), "8.596e-04*4.*TMath::Pi()*x^2/(1+exp((x-6.38)/0.535))", 0., 20.);
    }
    if (A == 129) {
      auto f = new TF2(name("wsXe2a").c_str(), "x*x*TMath::Sin(y)/(1+exp((x-[0]*(1+[2]*0.315*(3*pow(cos(y),2)-1.0)+[3]*0.105*(35*pow(cos(y),4)-30*pow(cos(y),2)+3)))/[1]))", 0, 15, 0.0, TMath::Pi());
      f->SetNpx(120);
      f->SetNpy(120);
      f->SetParameters(5.36, 0.59, 0.18, 0);
      return f;
    }
    if (A == 40) {
      return new TF1(name("wsAr").c_str(), "1.*TMath::Pi()*x^2/(1+exp((x-3.53)/0.542))", 0., 15.);
    }
    if (A == 20) {
      auto f = new TF1(name("wsNe").c_str(), "x*x*(1+[2]*(x/[0])**2)/(1+exp((x-[0])/[1]))", 0, 10.);
      f->SetParameters(2.791, 0.698, -0.168);
      return f;
    }
    if (A == 16) {
      auto f = new TF1(name("wsO").c_str(), "x*x*(1+[2]*(x/[0])**2)/(1+exp((x-[0])/[1]))", 0, 10.);
      f->SetParameters(2.608, 0.513, -0.051);
      return f;
    }
    if (A == 6) {
      return new TF1(name("wsC").c_str(), "7.208e-4*4.*TMath::Pi()*x^2*(1.-0.149*(x/2.46)**2)/(1+exp((x-2.46)/0.522))", 0., 10.);
    }
    if (A == 3) {
      return new TF1(name("wsHe").c_str(), "7.208e-4*4.*TMath::Pi()*x^2*(1.+0.517*(x/0.964)**2)/(1+exp((x-0.964)/0.322))", 0., 10.);
    }
    if (A == 1) {
      return new TF1(name("prot").c_str(), "x*x*exp(-x/0.234)", 0., 5.);
    }
    LOG(fatal) << "GeneratorHGPythia8: nucleus with A = " << A << " not supported (1, 3, 6, 16, 20, 40, 129, 197, 208)";
    return nullptr;
  }

  /// Matter distribution in the proton (eikonal)
  static double eikonal(double x)
  {
    constexpr double p0 = 3.9, p1 = 96.;
    return p0 * p0 / p1 * TMath::Power(p0 * x, 3) * TMath::BesselK(3, p0 * x);
  }

  /// Sample the nucleon positions in the transverse plane for nucleus j, centred at x = dx
  void sampleNucleus(int j, double dx)
  {
    auto density = mDensity[j].get();
    auto f2 = dynamic_cast<TF2*>(density);
    for (size_t k = 0; k < mX[j].size(); ++k) {
      double x = 0., y = 0.;
      if (f2) {
        double r, theta;
        f2->GetRandom2(r, theta, mRandom.get());
        const double phi = 2. * TMath::Pi() * mRandom->Rndm();
        x = r * TMath::Sin(phi) * TMath::Sin(theta);
        y = r * TMath::Cos(phi) * TMath::Sin(theta);
      } else if (density) {
        const double r = density->GetRandom(mRandom.get());
        const double phi = 2. * TMath::Pi() * mRandom->Rndm();
        const double costh = 2. * mRandom->Rndm() - 1.;
        const double sinth = costh * costh < 1. ? TMath::Sqrt(1. - costh * costh) : 0.;
        x = r * sinth * TMath::Cos(phi);
        y = r * sinth * TMath::Sin(phi);
      }
      mX[j][k] = x + dx;
      mY[j][k] = y;
    }
  }

  /// Sample a Glauber configuration with at least one inelastic NN collision and count, for
  /// each NN collision, the number of hard scatterings (nMPI[0]: collisions without any)
  void sampleGlauber(std::array<int, kMaxMPI>& nMPI)
  {
    constexpr double dmax = 1.43; // black-disc NN distance (fm)
    const double b02 = 0.5 * mSigmaSoft * 0.1 / TMath::Pi();
    do {
      nMPI.fill(0);
      const double b = TMath::Sqrt(mBMin * mBMin + mRandom->Rndm() * (mBMax * mBMax - mBMin * mBMin));
      sampleNucleus(0, b / 2.);
      sampleNucleus(1, -b / 2.);
      for (int j = 0; j < 2; ++j) {
        std::fill(mWounded[j].begin(), mWounded[j].end(), 0);
        std::fill(mWoundedBlackDisc[j].begin(), mWoundedBlackDisc[j].end(), 0);
      }
      const double gstot0 = mElastic ? 2. * (1. - TMath::Exp(-(mSigmaSoft + mSigmaHard) / mSigmaSoft * eikonal(0.001))) : 1.;

      mImpactParameter = b;
      mNcoll = mNcollHard = mNhard = mNcollBlackDisc = 0;
      for (int i = 0; i < mA; ++i) {
        for (int j = 0; j < mB; ++j) {
          const double dx = mX[0][i] - mX[1][j];
          const double dy = mY[0][i] - mY[1][j];
          double r2 = dx * dx + dy * dy;
          if (r2 < dmax * dmax) {
            mWoundedBlackDisc[0][i] = 1;
            mWoundedBlackDisc[1][j] = 1;
            mNcollBlackDisc++;
          }
          if (r2 > 25.) {
            continue;
          }
          // interaction probability
          r2 /= b02;
          r2 /= gstot0;
          const double chi = eikonal(TMath::Sqrt(r2));
          const double gs = 1. - TMath::Exp(-2. * (mSigmaSoft + mSigmaHard) / mSigmaSoft * chi);
          const double gstot = 2. * (1. - TMath::Sqrt(1. - gs));
          const double rantot = mRandom->Rndm() * gstot0;
          if (rantot > gstot && mElastic) {
            continue;
          }
          if (rantot > gs) {
            continue;
          }
          mWounded[0][i] = 1;
          mWounded[1][j] = 1;
          mNcoll++;
          // minijets
          const double tt = 2. * chi * mSigmaHard / mSigmaSoft;
          const double ts = 2. * chi;
          if (rantot < TMath::Exp(-tt) * (1. - TMath::Exp(-ts))) {
            nMPI[0]++;
            continue;
          }
          double xr = -TMath::Log(TMath::Exp(-tt) + mRandom->Rndm() * (1. - TMath::Exp(-tt)));
          int njet = 0;
          while (true) {
            njet++;
            xr -= TMath::Log(mRandom->Rndm());
            if (xr > tt) {
              break;
            }
          }
          njet = TMath::Min(njet, kMaxMPI - 1);
          nMPI[njet]++;
          mNhard += njet;
          mNcollHard++;
        }
      }
    } while (mNcoll < 1);

    // participants and participant eccentricity
    mNpartProj = mNpartTarg = mNpartBlackDisc = 0;
    double mx = 0., my = 0., mx2 = 0., my2 = 0., mxy = 0.;
    for (int j = 0; j < 2; ++j) {
      for (size_t k = 0; k < mX[j].size(); ++k) {
        mNpartBlackDisc += mWoundedBlackDisc[j][k];
        if (!mWounded[j][k]) {
          continue;
        }
        (j == 0 ? mNpartProj : mNpartTarg)++;
        mx += mX[j][k];
        my += mY[j][k];
        mx2 += mX[j][k] * mX[j][k];
        my2 += mY[j][k] * mY[j][k];
        mxy += mX[j][k] * mY[j][k];
      }
    }
    const double iw = mNpartProj + mNpartTarg;
    mx2 -= mx * mx / iw;
    my2 -= my * my / iw;
    mxy -= mx * my / iw;
    mEccentricity = (mx2 + my2) > 0 ? TMath::Sqrt((my2 - mx2) * (my2 - mx2) + 4. * mxy * mxy) / (mx2 + my2) : 0.;
  }

  // configuration
  int mA = 208;
  int mB = 208;
  double mBMin = 0.;
  double mBMax = -1.;
  double mSigmaHardIn = -1.;
  double mSigmaHard = -1.;
  double mSigmaSoft = 57.;
  bool mElastic = false;

  // Glauber state
  std::unique_ptr<TRandom3> mRandom;
  std::array<std::unique_ptr<TF1>, 2> mDensity;
  std::array<std::vector<double>, 2> mX;
  std::array<std::vector<double>, 2> mY;
  std::array<std::vector<int>, 2> mWounded;
  std::array<std::vector<int>, 2> mWoundedBlackDisc;
  double mImpactParameter = 0.;
  int mNcoll = 0;
  int mNcollHard = 0;
  int mNhard = 0;
  int mNpartProj = 0;
  int mNpartTarg = 0;
  int mNpartBlackDisc = 0;
  int mNcollBlackDisc = 0;
  double mEccentricity = 0.;

  // sum of the PYTHIA events of the current heavy-ion event
  Pythia8::Event mHIEvent;
};

} // namespace eventgen
} // namespace o2

/// HG-PYTHIA generator for nuclei with mass numbers A (along +z, PYTHIA beam A) and B.
/// bMax <= 0: o2-sim --bMax if given, otherwise 20 fm (10 fm for p-A, 5 fm for pp).
/// sigmaHard < 0: hard cross-section from the built-in sqrt(s_NN) table (up to 8.1 TeV).
FairGenerator* generateHGPythia8(int A = 208, int B = 208, double bMin = 0., double bMax = -1.,
                                 double sigmaHard = -1., double sigmaSoft = 57.,
                                 bool elastic = false)
{
  auto gen = new o2::eventgen::GeneratorHGPythia8(A, B);
  gen->setImpactParameterRange(bMin, bMax);
  gen->setSigmaHard(sigmaHard);
  gen->setSigmaSoft(sigmaSoft);
  gen->setElastic(elastic);
  return gen;
}
