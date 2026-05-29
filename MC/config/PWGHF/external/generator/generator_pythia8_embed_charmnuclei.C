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
    mDecayDistr = new TF1("mDecayDistr", Form("exp(-x/%f)", mLifetimeCharmNucleus), 0., 1000.);

    Print();

    /** switch off process level **/
    // mPythiaGun.readString("ProcessLevel:all off");
    auto& param = o2::eventgen::GeneratorPythia8Param::Instance();
    LOG(info) << "Init \'GeneratorPythia8HFEmbedCharmNuclei\' with following parameters";
    LOG(info) << param;
    if (param.config.empty()) {
      LOG(fatal) << "Failed to init \'GeneratorPythia8\': problems with configuration file ";
    }
    std::string cfg = gSystem->ExpandPathName(param.config.c_str());
    LOG(info) << "GeneratorPythia8HFEmbedCharmNuclei Reading configuration from file: " << cfg;
    if (!mPythiaGun.readFile(cfg, true)) {
      LOG(fatal) << "Failed to init \'GeneratorPythia8\': problems with configuration file " << cfg;
    }

    if (!mPythiaGun.init()) {
      LOG(fatal) << "Failed to init \'GeneratorPythia8\': init returned with error";
    }
  }

  ///  Destructor
  ~GeneratorPythia8HFEmbedCharmNuclei() = default;

  ///  Print the input
  void Print()
  {
    LOG(info) << "********** GeneratorPythia8HFEmbedCharmNuclei configuration dump **********";
    LOG(info) << Form("* PDG code of charm nuclei to be injected: %d", mPdgCharmNucleus);
    LOG(info) << Form("* Mass of charm nuclei to be injected (GeV/c2): %f", mMassCharmNucleus);
    LOG(info) << Form("* Lifetime of charm nuclei to be injected (mm): %f", mLifetimeCharmNucleus);
    LOG(info) << Form("* Number of charm nuclei injected per event: %d", nNumberOfCharmNucleiPerEvent);
    LOG(info) << Form("* Hadron rapidity: %f - %f", mRapidityMinCharmNuclei, mRapidityMaxCharmNuclei);
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
      auto y = gRandom->Uniform(mRapidityMinCharmNuclei, mRapidityMaxCharmNuclei);
      auto phi = gRandom->Uniform(0, TMath::TwoPi());
      auto px = pt * TMath::Cos(phi);
      auto py = pt * TMath::Sin(phi);
      auto mt = TMath::Sqrt(mMassCharmNucleus * mMassCharmNucleus + pt * pt);
      auto pz = mt * TMath::SinH(y);
      auto p = TMath::Sqrt(pt * pt + pz * pz);
      auto e = TMath::Sqrt(mMassCharmNucleus * mMassCharmNucleus + p * p);

      Particle particle;
      particle.id(sign * mPdgCharmNucleus);
      particle.status(83);
      particle.m(mMassCharmNucleus);
      particle.px(px);
      particle.py(py);
      particle.pz(pz);
      particle.e(e);
      particle.xProd(0.f);
      particle.yProd(0.f);
      particle.zProd(0.f);
      particle.tau(0.f); //mDecayDistr->GetRandom());
      mPythiaGun.particleData.mayDecay(mPdgCharmNucleus, true); // force decay

      bool isCoalSuccess{false};
      while(!isCoalSuccess) {
        mPythiaGun.event.reset();
        mPythiaGun.event.append(particle);
        mPythiaGun.moreDecays();
        std::array<int, 2> dausToCoal = {-1, -1};
        std::vector<int> pdgShortLivedResos = {313, 2224, 102134};
        bool isResoFound{false};
        int idxCharmNucleus{-1};
        for (int iPart{0}; iPart<mPythiaGun.event.size(); ++iPart) {
          auto part = mPythiaGun.event[iPart];
          auto absPdg = std::abs(part.id());
          if (absPdg == mPdgCharmNucleus) {
            idxCharmNucleus = iPart;
          }
          // if we find a resonance, we remove it, otherwise we prevent the coalescence of daughters from resonances and daughters from charmed nucleus directly
          if (std::find(pdgShortLivedResos.begin(), pdgShortLivedResos.end(), absPdg) != pdgShortLivedResos.end()) {
            // we need to change the indices of the daughter particles to point to the charmed nucleus
            auto dauList = part.daughterList();
            for (auto const& dau : dauList) {
              mPythiaGun.event[dau].mother1(idxCharmNucleus);
            }
            mPythiaGun.event.remove(iPart, iPart, true);
            isResoFound=true;
          }
        }
        if (isResoFound) { // we have to reset all the particles as daughters of the charm nucleus
          mPythiaGun.event[idxCharmNucleus].daughter1(idxCharmNucleus + 1);
          mPythiaGun.event[idxCharmNucleus].daughter2(mPythiaGun.event.size() - 1);
        }

        int iDau{-1};
        for (int iPart{0}; iPart<mPythiaGun.event.size(); ++iPart) {
          auto part = mPythiaGun.event[iPart];
          auto absPdg = std::abs(part.id());

          if (absPdg == 2212 || absPdg == 2112) { // coalescence of protons and deuterons
            dausToCoal[++iDau] = iPart;
          }
        }

        // we try the coalescence here, if successful we copy particles in the pythia event and we move to the next charm nucleus
        isCoalSuccess = CoalescencePythia8(mPythiaGun.event, std::vector<unsigned int>{1000010020}, mTrivialCoal, mCoalMomentum, dausToCoal[0], dausToCoal[1]);
        if (isCoalSuccess) {
          int offset = mPythia.event.size(); // we need to rescale the indices of mothers and daughters, accounting for the particles that are already appended to the event
          for (int iPart{0}; iPart<mPythiaGun.event.size(); ++iPart) {
            auto part = mPythiaGun.event[iPart];
            if (part.id() == 90) {
              continue;
            }
            auto mother1 = part.mother1();
            auto mother2 = part.mother2();
            auto daughter1 = part.daughter1();
            auto daughter2 = part.daughter2();
            if (mother1 > 0) {
              part.mother1(mother1 + offset);
            }
            if (mother2 > 0) {
              part.mother2(mother2 + offset);
            }
            if (daughter1 > 0) {
              part.daughter1(daughter1 + offset);
            }
            if (daughter2 > 0) {
              part.daughter2(daughter2 + offset);
            }
            mPythia.event.append(part);
          }
        }
      }
    }

    return true;
  }

 private:
  // Properties of selection
  float mMassCharmNucleus;           /// mass of the charmed nucleus
  int mPdgCharmNucleus;              /// pdg code of the charmed nucleus
  float mLifetimeCharmNucleus;       /// lifetime of the charmed nucleus
  int nNumberOfCharmNucleiPerEvent;  /// number of charmed nuclei injected per event
  float mRapidityMinCharmNuclei;     /// rapidity min
  float mRapidityMaxCharmNuclei;     /// rapidity max
  unsigned int mUsedSeed;            /// seed
  bool mTrivialCoal;                 /// if true, the coalescence is done without checking the distance in the phase space of the nucleons
  float mCoalMomentum;               /// coalescence momentum
  Pythia8::Pythia mPythiaGun;        /// Gun generator with decay support
  TF1* mDecayDistr;                  /// Lifetime distribution
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
