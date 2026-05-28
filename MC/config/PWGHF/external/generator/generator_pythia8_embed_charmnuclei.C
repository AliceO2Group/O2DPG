#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"
#include "TF1.h"
#include "TMath.h"
#include <fairlogger/Logger.h>
#include <algorithm>
#include <string>
#include <vector>

R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
#include "MC/config/common/external/generator/CoalescencePythia8.h"

using namespace Pythia8;

class GeneratorPythia8HFEmbedCharmNuclei : public o2::eventgen::GeneratorPythia8
{
 public:
  /// default constructor
  GeneratorPythia8HFEmbedCharmNuclei() = default;

  /// constructor
  GeneratorPythia8HFEmbedCharmNuclei(int pdgCode = 2010010020, float lifetime = 1.f, int nCharmNucleiPerEvent = 10, float yMin = -1.f, float yMax = 1.f, bool trivialCoal = false, float coalMomentum = 0.2)
  {
    nNumberOfCharmNucleiPerEvent = nCharmNucleiPerEvent;
    mRapidityMinCharmNuclei = yMin;
    mRapidityMaxCharmNuclei = yMax;
    mTrivialCoal = trivialCoal;
    mCoalMomentum = coalMomentum;
    mPdgCharmNucleus = pdgCode;
    if (std::abs(mPdgCharmNucleus) == 2010010020) {
      mMassCharmNucleus = 3.226f;
    } else {
      LOG(fatal) << "********** [GeneratorPythia8HFEmbedCharmNuclei] Only c-deuteron (pdg=2010010020) currently supported! Exit **********";
    }
    mLifetimeCharmNucleus = lifetime;
    mDecayDistr =  TF1("mDecayDistr", Form("exp(-x/%f)", mLifetimeCharmNucleus), 0., 1000.)

    Print();

    /** switch off process level **/
    mPythiaGun.readString("ProcessLevel:all off");
    auto& param = o2::eventgen::GeneratorPythia8::Instance();
    LOG(info) << "Init \'GeneratorPythia8HFEmbedCharmNuclei\' with following parameters";
    LOG(info) << param;
    for (int iCfg{0}; iCfg < 8; ++iCfg) {
      if (param.config[iCfg].empty()) {
        continue;
      }
      std::string config = gSystem->ExpandPathName(param.config[iCfg].c_str());
      LOG(info) << "GeneratorPythia8HFEmbedCharmNuclei Reading configuration from file: " << config;
      if (!mPythiaGun.readFile(config, true)) {
        LOG(fatal) << "Failed to init \'GeneratorPythia8\': problems with configuration file "
                   << config;
        return;
      }
    }
    if (!mPythiaGun.init()) {
      LOG(fatal) << "Failed to init \'GeneratorPythia8\': init returned with error";
      return;
    }
  }

  ///  Destructor
  ~GeneratorPythia8HFEmbedCharmNuclei() = default;

  /// Init
  bool Init() override
  {
    return o2::eventgen::GeneratorPythia8::Init();
  }

  ///  Print the input
  void Print()
  {
    LOG(info) << "********** GeneratorPythia8HFEmbedCharmNuclei configuration dump **********";
    LOG(info) << Form("* PDG code of charm nuclei to be injected: %d", mPdgCharmNucleus);
    LOG(info) << Form("* Mass of charm nuclei to be injected (GeV/c2): %f", mMassCharmNucleus);
    LOG(info) << Form("* Lifetime of charm nuclei to be injected (mm): %f", mLifetimeCharmNucleus);
    LOG(info) << Form("* Number of charm nuclei injected per event: %d", nNumberOfCharmNucleiPerEvent);
    LOG(info) << Form("* Hadron rapidity: %f - %f", mHadRapidityMin, mHadRapidityMax);
    LOG(info) << Form("* Trivial coalescence: %d", mTrivialCoal);
    LOG(info) << Form("* Coalescence momentum: %f", mCoalMomentum);
    LOG(info) << "***********************************************************************";
  }

  void setHadronRapidity(float yMin, float yMax)
  {
    mRapidityMinCharmNuclei = yMin;
    mRapidityMaxCharmNuclei = yMax;
  };

  void setUsedSeed(unsigned int seed)
  {
    mUsedSeed = seed;
  };

  unsigned int getUsedSeed() const
  {
    return mUsedSeed;
  };

 protected:
  //__________________________________________________________________
  bool generateEvent() override
  {
    // we start from an empty event
    mPythia.event.reset();

    // we simulate c-deuteron decays
    for (int iCharmNuclei{0}; iCharmNuclei<nNumberOfCharmNucleiPerEvent; ++iCharmNuclei) {
      int sign = 1;
      // we alternate positive and negative
      if (nNumberOfCharmNucleiPerEvent % 2 == 0) {
        if (iCharmNuclei % 2 != 0) {
          sign = -1;
        }
      } else {
        if (gRandom->Rndm() < 0.5) {
          sign = -1;
        }
      }

      auto pt = gRandom->Uniform(0., 50.); // placeholder, to be modified
      auto y = gRandom->Uniform(mHadRapidityMin, mHadRapidityMax);
      auto phi = gRandom->Uniform(0, TMath::TwoPi());
      auto px = pt * TMath::Cos(phi);
      auto py = pt * TMath::Sin(phi);
      auto mt = TMath::Sqrt(mMassCharmNucleus * mMassCharmNucleus + pt * pt);
      auto pz = mt * TMath::SinH(y);
      auto p = TMath::Sqrt(pt * pt + pz * pz);
      auto e = TMath::Sqrt(mass * mass + p * p);

      Particle particle;
      particle.id(sign * mPdgCharmNucleus);
      particle.status(81);
      particle.m(mMassCharmNucleus);
      particle.px(px);
      particle.py(py);
      particle.pz(pz);
      particle.e(e);
      particle.xProd(0.f);
      particle.yProd(0.f);
      particle.zProd(0.f);
      particle.tau(mDecayDistr->GetRandom());
      mPythiaGun.particleData.mayDecay(mPdgCharmNucleus, true); // force decay

      bool isCoalSuccess{false};
      while(!isCoalSuccess) {
        mPythiaGun.event.reset();
        mPythiaGun.event.append(particle);
        mPythiaGun.moreDecays();
        std::array<int, 2> dausToCoal = {-1, -1};
        int iDau{-1};
        for (int iPart{0}; iPart<mPythiaGun.event.size(); ++iPart) {
          auto part = mPythiaGun.event[iPart];
          if (std::abs(iPart) == 2212 || std::abs(iPart) == 2112) { // coalescence of protons and deuterons
            dausToCoal[++iDau] = iPart;
          }
          if (iDau == 1) { // we found the proton and the neutron to coalesce
            break;
          }
        }
        // we try the coalescence here, if successful we copy particles in the pythia event and we move to the next charm nucleus
        isCoalSuccess = CoalescencePythia8(mPythiaGun.event, std::vector<int>{1000010020}, mTrivialCoal, mCoalMomentum, dausToCoal[0], dausToCoal[1]);
        if (isCoalSuccess) {
          for (int iPart{0}; iPart<mPythiaGun.event.size(); ++iPart) {
            mPythia.append(mPythiaGun.event[iPart]);
          }
        }
        mPythiaGun.next();
      }
    }

    mPythia.next();

    return true;
  }

 private:
  // Properties of selection
  float mMassCharmNucleus;
  int mPdgCharmNucleus;
  float mLifetimeCharmNucleus;
  int nNumberOfCharmNucleiPerEvent;
  float mRapidityMinCharmNuclei;
  float mRapidityMaxCharmNuclei;
  unsigned int mUsedSeed;

  bool mTrivialCoal = false; /// if true, the coalescence is done without checking the distance in the phase space of the nucleons
  float mCoalMomentum; /// coalescence momentum

  Pythia8::Pythia mPythiaGun; // Gun generator with decay support

  TF1* mDecayDistr;
};


///___________________________________________________________
FairGenerator *GenerateHFEmbedCDeuteron(float lifetime = 1.f, int nCharmNucleiPerEvent = 10, float yMin = -1.f, float yMax = 1.f, bool trivialCoal = false, float coalMomentum = 0.2)
{
  auto myGen = new GeneratorPythia8HFEmbedCharmNuclei(2010010020, lifetime, nCharmNucleiPerEvent, yMin, yMax, trivialCoal, coalMomentum);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
