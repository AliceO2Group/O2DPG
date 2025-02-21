// Parameterized generator for muons
// Adaptation of the Run 2 generator by P. Pillot:
// https://github.com/alisw/AliDPG/blob/master/MC/CustomGenerators/PWGDQ/Muon_GenParamSingle_PbPb5TeV_1.C

#include "FairGenerator.h"
#include "TF1.h"
#include "TRandom.h"
#include "TDatabasePDG.h"
#include "TParticlePDG.h"

class O2_GeneratorParamMuon : public FairGenerator
{
 public:
  O2_GeneratorParamMuon(int npart = 2, int pdg = 13, double ymin = -4.3, double ymax = -2.3, double ptmin = 0.1, double ptmax = 999.)
    : FairGenerator("ParaMuon"), fNParticles(npart), fPDGCode(pdg), fYMin(ymin), fYMax(ymax), fPtMin(ptmin), fPtMax(ptmax)
  {
    TParticlePDG* particle = TDatabasePDG::Instance()->GetParticle(fPDGCode);
    fMass = particle->Mass();
    fMass2 = fMass * fMass;
  }

  ~O2_GeneratorParamMuon() = default;

  void SetRandomCharge(bool flag) { fRandomizeCharge = flag; }

  void SetPtPars(double p0, double p1, double p2, double p3, double p4, double p5)
  {
    fPtP0 = p0;
    fPtP1 = p1;
    fPtP2 = p2;
    fPtP3 = p3;
    fPtP4 = p4;
    fPtP5 = p5;
  }

  void SetYPars(double p0, double p1, double p2, double p3, double p4)
  {
    fYP0 = p0;
    fYP1 = p1;
    fYP2 = p2;
    fYP3 = p3;
    fYP4 = p4;
  }

  void InitParaFuncs()
  {
    fPtPara = new TF1("pt-para", PtMuon, fPtMin, fPtMax, 6);
    fPtPara->SetParameter(0, fPtP0);
    fPtPara->SetParameter(1, fPtP1);
    fPtPara->SetParameter(2, fPtP2);
    fPtPara->SetParameter(3, fPtP3);
    fPtPara->SetParameter(4, fPtP4);
    fPtPara->SetParameter(5, fPtP5);
    fYPara = new TF1("y-para", YMuon, fYMin, fYMax, 5);
    fYPara->SetParameter(0, fYP0);
    fYPara->SetParameter(1, fYP1);
    fYPara->SetParameter(2, fYP2);
    fYPara->SetParameter(3, fYP3);
    fYPara->SetParameter(4, fYP4);
  }

  static double PtMuon(const double* xx, const double* par)
  {
    double x = xx[0];
    double p0 = par[0];
    double p1 = par[1];
    double p2 = par[2];
    double p3 = par[3];
    double p4 = par[4];
    double p5 = par[5];
    return p0 * (1. / std::pow(p1 + std::pow(x, p2), p3) + p4 * std::exp(p5 * x));
  }

  static double YMuon(const double* xx, const double* par)
  {
    double x = xx[0];
    double p0 = par[0];
    double p1 = par[1];
    double p2 = par[2];
    double p3 = par[3];
    double p4 = par[4];
    double x2 = x * x;
    return p0 * (1. + p1 * x + p2 * x2 + p3 * x2 * x + p4 * x2 * x2);
  }

  bool ReadEvent(FairPrimaryGenerator* primGen) override
  {
    // no kinematic cuts -> accepting all
    for (int i = 0; i < fNParticles; ++i) {
      double pt = fPtPara->GetRandom();
      double ty = std::tanh(fYPara->GetRandom());
      double xmt = std::sqrt(pt * pt + fMass2);
      double pl = xmt * ty / std::sqrt((1. - ty * ty));
      double phi = gRandom->Uniform(0., 2. * M_PI);
      double px = pt * std::cos(phi);
      double py = pt * std::sin(phi);
      int pdg = fPDGCode;
      if (fRandomizeCharge) {
        int charge;
        if (gRandom->Rndm() < 0.5) {
          charge = 1;
        } else {
          charge = -1;
        }
        pdg = std::abs(pdg) * charge;
      }
      primGen->AddTrack(pdg, px, py, pl, 0, 0, 0);
      printf("Add track %d %.2f %.2f %.2f  \n", pdg, px, py, pl);
    }
    return kTRUE;
  }

 private:
  TF1* fPtPara{nullptr};
  TF1* fYPara{nullptr};
  TF1* fdNdPhi{nullptr};

  // parameters tuned to Pb-Pb @ 5.02 TeV
  double fPtP0{797.446};
  double fPtP1{0.830278};
  double fPtP2{0.632177};
  double fPtP3{10.2202};
  double fPtP4{-0.000614809};
  double fPtP5{-1.70993};

  double fYP0{1.87732};
  double fYP1{0.00658212};
  double fYP2{-0.0988071};
  double fYP3{-0.000452746};
  double fYP4{0.00269782};

  // configuration
  int fPDGCode{13};
  int fNParticles{2};
  double fYMin{-4.3};
  double fYMax{-2.3};
  double fPtMin{0.1};
  double fPtMax{999.};
  bool fRandomizeCharge{true};
  double fMass{0.10566};
  double fMass2{0};
};

FairGenerator* paramMuGen(double ptP0 = 797.446, double ptP1 = 0.830278,
                          double ptP2 = 0.632177, double ptP3 = 10.2202,
                          double ptP4 = -0.000614809, double ptP5 = -1.70993,
                          double yP0 = 1.87732, double yP1 = 0.00658212,
                          double yP2 = -0.0988071, double yP3 = -0.000452746,
                          double yP4 = 0.00269782,
                          int nPart = 2, int pdg = 13,
                          double ymin = -4.3, double ymax = -2.3,
                          double ptmin = 0.1, float ptmax = 999.,
                          int randCharge = 1)
{
  auto* gen = new O2_GeneratorParamMuon(nPart, pdg, ymin, ymax, ptmin, ptmax);
  gen->SetPtPars(ptP0, ptP1, ptP2, ptP3, ptP4, ptP5);
  gen->SetYPars(yP0, yP1, yP2, yP3, yP4);
  gen->InitParaFuncs();
  gen->SetRandomCharge(randCharge);
  return gen;
}