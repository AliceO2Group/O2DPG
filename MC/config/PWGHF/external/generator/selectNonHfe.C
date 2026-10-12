
#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "TMath.h"
#include <fairlogger/Logger.h>
#include <cmath>
#include <vector>
#endif

#include "Pythia8/Pythia.h"

class GeneratorPythia8Box : public o2::eventgen::GeneratorPythia8
{
public:

  GeneratorPythia8Box(std::vector<int> pdgList, int nInject = 3,
                      float ptMin = 0.1, float ptMax = 50.0,
                      float etaMin = -0.8, float etaMax = 0.8)
    : mPdgList(pdgList), nParticles(nInject),
      genMinPt(ptMin), genMaxPt(ptMax),
      genMinEta(etaMin), genMaxEta(etaMax)
  {
    // Initialize dedicated Pythia instance for injection/decay only
    // Reuses same config as main Pythia; beam settings are ignored by moreDecays()
    auto& param = o2::eventgen::GeneratorPythia8Param::Instance();
    std::string cfg = gSystem->ExpandPathName(param.config.c_str());
    if (!mPythiaGun.readFile(cfg, true)) {
      LOG(fatal) << "Failed to read config for mPythiaGun: " << cfg;
    }
    if (!mPythiaGun.init()) {
      LOG(fatal) << "Failed to init mPythiaGun";
    }
  }

  ~GeneratorPythia8Box() = default;

  bool Init() override
  {
    return o2::eventgen::GeneratorPythia8::Init();
  }

protected:

  // ── generateEvent: MB + injection ──
  Bool_t generateEvent() override
  {
    bool hasElectron = false;

    while (!hasElectron) {
      // ===== 1. Generate minimum-bias event =====
      if (!mPythia.next()) continue;

      // ===== 2. Inject π⁰/η into separate gun, decay only them =====
      mPythiaGun.event.reset();
      for (int i = 0; i < nParticles; ++i) {
        int pdg = mPdgList[gRandom->Integer(mPdgList.size())];
        auto* pPDG = TDatabasePDG::Instance()->GetParticle(pdg);
        if (!pPDG) continue;
        double mass = pPDG->Mass();

        double pt  = gRandom->Uniform(genMinPt, genMaxPt);
        double eta = gRandom->Uniform(genMinEta, genMaxEta);
        double phi = gRandom->Uniform(0., TMath::TwoPi());
        double px = pt * cos(phi);
        double py = pt * sin(phi);
        double pz = pt * sinh(eta);
        double e  = sqrt(px * px + py * py + pz * pz + mass * mass);

        mPythiaGun.event.append(pdg, 11, 0, 0, px, py, pz, e, mass);
      }

      mPythiaGun.moreDecays();

      // ===== 3. Check for electron from injection in acceptance =====
      for (int i = 0; i < mPythiaGun.event.size(); ++i) {
        auto& part = mPythiaGun.event[i];
        if (std::abs(part.id()) == 11 && part.isFinal()) {
          if (part.pT() > 0.1 && std::abs(part.eta()) < 1.2) {
            hasElectron = true;
            break;
          }
        }
      }
    }

    // ===== 4. Copy injection products to MB event with index offset =====
    int offset = mPythia.event.size();

    for (int i = 0; i < mPythiaGun.event.size(); ++i) {
      auto part = mPythiaGun.event[i];
      if (part.id() == 90) continue;            // skip system placeholder
      if (!part.isFinal() && part.id() != 111 && part.id() != 221) continue;

      if (part.mother1() > 0)   part.mother1(part.mother1()   + offset - 1);
      if (part.mother2() > 0)   part.mother2(part.mother2()   + offset - 1);
      if (part.daughter1() > 0) part.daughter1(part.daughter1() + offset - 1);
      if (part.daughter2() > 0) part.daughter2(part.daughter2() + offset - 1);

      mPythia.event.append(part);
    }

    return true;
  }

private:
  std::vector<int> mPdgList;
  double genMinPt, genMaxPt;
  double genMinEta, genMaxEta;
  int nParticles;
  
  Pythia8::Pythia mPythiaGun;
};

FairGenerator *generatePythia8Box(float ptMin = 0.1, float ptMax = 50.0)
{
  std::vector<int> pdgList = {111, 221};
  return new GeneratorPythia8Box(pdgList, 3, ptMin, ptMax, -0.8, 0.8);
}