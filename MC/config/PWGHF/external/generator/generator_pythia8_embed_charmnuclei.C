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

#include "Math/Vector3D.h"
#include "Math/Vector4D.h"

R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
#include "MC/config/common/external/generator/CoalescencePythia8.h"

using namespace Pythia8;

class GeneratorPythia8HFEmbedCharmNuclei : public o2::eventgen::GeneratorPythia8
{
 public:

  /// constructor
  GeneratorPythia8HFEmbedCharmNuclei(int pdgCode = 2010010020, float lifetime = 1.f, int nCharmNucleiPerEvent = 10, float yMin = -1.f, float yMax = 1.f, float ptMax = 25.f, bool trivialCoal = false, float coalMomentum = 0.2, float fracFromB = 0.f)
  {
    nNumberOfCharmNucleiPerEvent = nCharmNucleiPerEvent;
    mRapidityMinCharmNuclei = yMin;
    mRapidityMaxCharmNuclei = yMax;
    mPtMaxCharmNuclei = ptMax;
    mTrivialCoal = trivialCoal;
    mCoalMomentum = coalMomentum;
    mFractionFromBeauty = fracFromB;
    mPdgCharmNucleus = pdgCode;
    mSign = 1;
    if (std::abs(mPdgCharmNucleus) == 2010010020) {
      mMassCharmNucleus = 3.226f;
    } else {
      LOG(fatal) << "********** [GeneratorPythia8HFEmbedCharmNuclei] Only c-deuteron (pdg=2010010020) currently supported! Exit **********";
    }
    mLifetimeCharmNucleus = lifetime;
    mDecayDistr = new TF1("mDecayDistr", "TMath::Exp(-x * 1./[0])", 0., mLifetimeCharmNucleus * 100);
    mDecayDistr->SetNpx(10000);
    mDecayDistr->SetParameter(0, mLifetimeCharmNucleus);
    mDecayDistrLb = new TF1("mDecayDistrLb", "TMath::Exp(-x * 1./[0])", 0., 44.f);
    mDecayDistrLb->SetParameter(0, 0.440f); // lifetime of Lambda_b in mm/c
    mDecayDistrLb->SetNpx(10000);
    mPtDistrLb = new TF1("mPtDistrLb","[0]*x/TMath::Power((1+TMath::Power(x/[1],[3])),[2])",0.,100.);
    mPtDistrLb->SetParameters(1000., 6.97355, 3.20721, 1.71678);
    mPtDistrLb->SetNpx(10000);

    Print();

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
    LOG(info) << Form("* Charmed nucleus rapidity: %f - %f", mRapidityMinCharmNuclei, mRapidityMaxCharmNuclei);
    LOG(info) << Form("* Charmed nucleus pT max (prompt): %f", mPtMaxCharmNuclei);
    LOG(info) << Form("* Trivial coalescence: %d", mTrivialCoal);
    LOG(info) << Form("* Coalescence momentum: %f", mCoalMomentum);
    LOG(info) << Form("* Fraction from beauty: %f", mFractionFromBeauty);
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

      // we alternate the sign of the generated charmed nuclei, if mSign is set to 0, they are generated with 50% of probability as particle or antiparticle
      (mSign > 0) ? mSign = -1 : mSign = 1;
      if (nNumberOfCharmNucleiPerEvent % 2 != 0 && iCharmNuclei == nNumberOfCharmNucleiPerEvent - 1) {
        if (gRandom->Rndm() < 0.5) {
          mSign = 1;
        }
      }

      int pdgToGen = mPdgCharmNucleus;
      float massToGen = mMassCharmNucleus;
      float lifetimeToGen = 0.f;
      float minRapToGen = mRapidityMinCharmNuclei;
      float maxRapToGen = mRapidityMaxCharmNuclei;
      bool isFromB = gRandom->Rndm() < mFractionFromBeauty;
      // we determine if it's prompt or non-prompt
      if (isFromB) {
        pdgToGen = 5122; // we generate a Lambda_b and we let it decay into the charmed nucleus, no other beauty hadrons are considered
        massToGen = 5.61940f; // mass of Lambda_b (GeV/c2)
        lifetimeToGen = mDecayDistrLb->GetRandom();
        minRapToGen *= 2;
        maxRapToGen *= 2;
      } else {
        lifetimeToGen = mDecayDistr->GetRandom();
      }

      auto pt = (!isFromB) ? gRandom->Uniform(0., mPtMaxCharmNuclei) : mPtDistrLb->GetRandom();
      auto y = gRandom->Uniform(minRapToGen, maxRapToGen);
      auto phi = gRandom->Uniform(0, TMath::TwoPi());
      auto px = pt * TMath::Cos(phi);
      auto py = pt * TMath::Sin(phi);
      auto mt = TMath::Sqrt(massToGen * massToGen + pt * pt);
      auto pz = mt * TMath::SinH(y);
      auto p = TMath::Sqrt(pt * pt + pz * pz);
      auto e = TMath::Sqrt(massToGen * massToGen + p * p);

      Particle particle;
      particle.id(mSign * pdgToGen);
      particle.status(83);
      particle.m(massToGen);
      particle.px(px);
      particle.py(py);
      particle.pz(pz);
      particle.e(e);
      particle.xProd(0.f);
      particle.yProd(0.f);
      particle.zProd(0.f);
      particle.tau(lifetimeToGen);
      mPythiaGun.particleData.mayDecay(5122, true); // force decay
      mPythiaGun.particleData.mayDecay(mPdgCharmNucleus, true); // force decay

      bool isCoalSuccess{false};
      int nTrials{0};
      while(!isCoalSuccess || nTrials > 1e4) {
        mPythiaGun.event.reset();
        mPythiaGun.event.append(particle);
        mPythiaGun.moreDecays();
        std::array<int, 2> dausToCoal = {-1, -1};
        std::vector<int> pdgShortLivedResos = {313, 2224, 102134};
        std::map<int, int> statusResoDecay = {{313, 95}, {2224, 96}, {102134, 97}}; // do not use 94, it is used by default for no resonances
        int whichReso{0};
        int idxCharmNucleus{-1};
        for (int iPart{0}; iPart<mPythiaGun.event.size(); ++iPart) {
          auto part = mPythiaGun.event[iPart];
          auto absPdg = std::abs(part.id());
          if (absPdg == mPdgCharmNucleus) {
            idxCharmNucleus = iPart;
          }
          auto mother = part.mother1();
          // if we find a resonance, we remove it, otherwise we prevent the coalescence of daughters from resonances and daughters from charmed nucleus directly
          auto resoIt = std::find(pdgShortLivedResos.begin(), pdgShortLivedResos.end(), absPdg);
          if (resoIt != pdgShortLivedResos.end() && mother >= idxCharmNucleus) {
            // we need to change the indices of the daughter particles to point to the charmed nucleus
            auto dauList = part.daughterList();
            for (auto const& dau : dauList) {
              mPythiaGun.event[dau].mother1(idxCharmNucleus);
            }
            mPythiaGun.event.remove(iPart, iPart, true);
            whichReso=*resoIt;
          }
        }
        if (whichReso > 0) { // we have to reset all the particles as daughters of the charm nucleus
          std::vector<int> idxDausCharmNucleus{};
          for (int iPart{0}; iPart<mPythiaGun.event.size(); ++iPart) {
            auto mother = mPythiaGun.event[iPart].mother1();
            if (mother == idxCharmNucleus) {
              idxDausCharmNucleus.push_back(iPart);
            }
          }
          if (idxDausCharmNucleus.size() == idxDausCharmNucleus.back() - idxDausCharmNucleus[0] + 1) {
            mPythiaGun.event[idxCharmNucleus].daughter1(idxDausCharmNucleus[0]);
            mPythiaGun.event[idxCharmNucleus].daughter2(idxDausCharmNucleus.back());
          } else { // the history is broken, we need to restore it
            std::vector<Particle> newPartList{};
            std::vector<int> idxToRemove{};
            for (int iPart{idxDausCharmNucleus[0]}; iPart<mPythiaGun.event.size(); ++iPart) {
              if (std::find(idxDausCharmNucleus.begin(), idxDausCharmNucleus.end(), iPart) == idxDausCharmNucleus.end()) {
                newPartList.push_back(mPythiaGun.event[iPart]);
                idxToRemove.push_back(iPart);
              }
            }
            int removed{0};
            for (auto const& idx : idxToRemove) {
              mPythiaGun.event.remove(idx - removed, idx - removed, false);
              ++removed;
            }
            std::vector<int> updatedMothers{};
            for (int iPart{0}; iPart<newPartList.size(); ++iPart) {
              mPythiaGun.event.append(newPartList[iPart]);
              auto mother = newPartList[iPart].mother1();
              if (std::find(updatedMothers.begin(), updatedMothers.end(), mother) == updatedMothers.end()) {
                updatedMothers.push_back(mother);
                int delta = mPythiaGun.event.size() - idxToRemove[iPart] - 1;
                mPythiaGun.event[mother].daughters(mPythiaGun.event[mother].daughter1() + delta, mPythiaGun.event[mother].daughter2() + delta);
              }
            }
            mPythiaGun.event[idxCharmNucleus].daughter1(idxDausCharmNucleus[0]);
            mPythiaGun.event[idxCharmNucleus].daughter2(idxDausCharmNucleus[0] + idxDausCharmNucleus.size() - 1);
          }
        }

        int iDau{-1};
        for (int iPart{0}; iPart<mPythiaGun.event.size(); ++iPart) {
          auto absPdg = std::abs(mPythiaGun.event[iPart].id());
          auto mother = mPythiaGun.event[iPart].mother1();

          if ((absPdg == 2212 || absPdg == 2112) && mother == idxCharmNucleus) { // coalescence of protons and deuterons
            dausToCoal[++iDau] = iPart;
          }
        }

        // we try the coalescence here, if successful we copy particles in the pythia event and we move to the next charm nucleus
        isCoalSuccess = CoalescencePythia8(mPythiaGun.event, std::vector<unsigned int>{1000010020}, mTrivialCoal, mCoalMomentum, dausToCoal[0], dausToCoal[1], 10.);
        if (whichReso > 0) {
          mPythiaGun.event[idxCharmNucleus].status(statusResoDecay[whichReso]);
        }
        if (isCoalSuccess) {
          restoreEnergyConservation(mPythiaGun.event, idxCharmNucleus);
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
              part.mother1(mother1 + offset - 1);
            }
            if (mother2 > 0) {
              part.mother2(mother2 + offset - 1);
            }
            if (daughter1 > 0) {
              part.daughter1(daughter1 + offset - 1);
            }
            if (daughter2 > 0) {
              part.daughter2(daughter2 + offset - 1);
            }
            mPythia.event.append(part);
          }
        }
        nTrials++;
      }
    }

    return true;
  }


private:

  void restoreEnergyConservation(Pythia8::Event& event, int idxCharmNucleus, float targetMassTolerance = 1e-5) {
    /// In the coalescence, the energy is not conserved, we rescale the momentum of the charmed nuclei daughters to restore it to avoid changes in the invariant mass of the charmed nucleus

    float scale = 1.f;
    float invMass{0.f};
    while (abs(invMass - mMassCharmNucleus) > targetMassTolerance) {
      ROOT::Math::PxPyPzMVector fourVecCharmNucleus;
      for (int iDau{event[idxCharmNucleus].daughter1()}; iDau<=event[idxCharmNucleus].daughter2(); ++iDau) {
        auto dau = event[iDau];
        fourVecCharmNucleus += ROOT::Math::PxPyPzMVector(dau.px() * scale, dau.py() * scale, dau.pz() * scale, dau.m());
      }
      invMass = fourVecCharmNucleus.M();
      scale *= mMassCharmNucleus / invMass;
    }

      for (int iDau{event[idxCharmNucleus].daughter1()}; iDau<=event[idxCharmNucleus].daughter2(); ++iDau) {
      event[iDau].px(event[iDau].px() * scale);
      event[iDau].py(event[iDau].py() * scale);
      event[iDau].pz(event[iDau].pz() * scale);
    }
    event[idxCharmNucleus].px(event[idxCharmNucleus].px() * scale);
    event[idxCharmNucleus].py(event[idxCharmNucleus].py() * scale);
    event[idxCharmNucleus].pz(event[idxCharmNucleus].pz() * scale);
  }

  // Properties of selection
  float mMassCharmNucleus;           /// mass of the charmed nucleus
  int mPdgCharmNucleus;              /// pdg code of the charmed nucleus
  float mLifetimeCharmNucleus;       /// lifetime of the charmed nucleus
  int nNumberOfCharmNucleiPerEvent;  /// number of charmed nuclei injected per event
  float mRapidityMinCharmNuclei;     /// rapidity min of the generated charmed nuclei
  float mRapidityMaxCharmNuclei;     /// rapidity max of the generated charmed nuclei
  float mPtMaxCharmNuclei;           /// pT max of the generated charmed nuclei
  unsigned int mUsedSeed;            /// seed
  bool mTrivialCoal;                 /// if true, the coalescence is done without checking the distance in the phase space of the nucleons
  float mCoalMomentum;               /// coalescence momentum
  Pythia8::Pythia mPythiaGun;        /// Gun generator with decay support
  TF1* mDecayDistr;                  /// Lifetime distribution
  TF1* mDecayDistrLb;                /// Lifetime distribution for Lb
  TF1* mPtDistrLb;                   /// pt distribution for Lb (power-law fit to FONLL)
  float mFractionFromBeauty;         /// fraction of charmed nuclei coming from beauty hadrons
  int mSign;                         /// sign of the charmed nuclei to be generated, if 0 they are generated with 50% of probability as particle or antiparticle
};


///___________________________________________________________
FairGenerator *GenerateHFEmbedCDeuteron(float lifetime = 1.f, int nCharmNucleiPerEvent = 10, float yMin = -1.f, float yMax = 1.f, float ptMax = 25.f, bool trivialCoal = false, float coalMomentum = 0.2f, float fracFromB = 0.25f)
{
  auto myGen = new GeneratorPythia8HFEmbedCharmNuclei(2010010020, lifetime, nCharmNucleiPerEvent, yMin, yMax, ptMax, trivialCoal, coalMomentum, fracFromB);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
