#include "FairGenerator.h"

class FwdBoxGenerator : public FairGenerator {

public:
  FwdBoxGenerator(int nparticles, int pdgcode, float etamin, float etamax,
                  float ptmin, float ptmax)
      : FairGenerator(), mPDGCode(pdgcode), mNParticles(nparticles),
        mEtaMin(etamin), mEtaMax(etamax), mPtMin(ptmin), mPtMax(ptmax){};
  ~FwdBoxGenerator() = default;

  int mPDGCode;
  int mNParticles;
  float mEtaMin;
  float mEtaMax;
  float mPtMin;
  float mPtMax;
  bool mRandomizeCharge = true;
  void disableRandomCharge() { mRandomizeCharge = false; }

  Bool_t ReadEvent(FairPrimaryGenerator *primGen) override {

    int iPart = mNParticles;
    while (iPart) {
      float pt = gRandom->Uniform(mPtMin, mPtMax);
      float eta = gRandom->Uniform(mEtaMin, mEtaMax);
      float phi = gRandom->Uniform(0., TMath::TwoPi());
      float px = pt * TMath::Cos(phi);
      float py = pt * TMath::Sin(phi);
      float tanl = tan(TMath::Pi() / 2 - 2 * atan(exp(-eta)));
      float pz = tanl * pt;
      int charge = 1;

      if (mRandomizeCharge && (gRandom->Rndm() < 0.5)) {
        charge = -1;
      }
      primGen->AddTrack(charge * mPDGCode, px, py, pz, 0, 0, 0);
      printf("Add track %d %.2f %.2f %.2f  \n", charge * mPDGCode, px, py, pz);

      iPart--;
    }
    return kTRUE;
  }

private:
};

FairGenerator *fwdMuBoxGen(int nParticles = 1, int pdgCode = 13,
                           float etamin = -3.8f, float etamax = -2.2f,
                           float ptmin = 0.01f, float ptmax = 20.f) {
  if (gSystem->Getenv("NMUONS")) {
    nParticles = atoi(gSystem->Getenv("NMUONS"));
  }
  auto gen =
      new FwdBoxGenerator(nParticles, pdgCode, etamin, etamax, ptmin, ptmax);
  return gen;
}
