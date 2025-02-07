// Parameterized generator for muons
// Port of the Run 2 generator by P. Pillot:
// https://github.com/alisw/AliDPG/blob/master/MC/CustomGenerators/PWGDQ/Muon_GenParamSingle_PbPb5TeV_1.C

// clang-format off
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
// clang-format on
R__LOAD_LIBRARY(libpythia6)

#include "GeneratorEvtGen.C"

namespace o2
{
namespace eventgen
{

class O2_GeneratorParamMuon : public GeneratorTGenerator
{
 public:
  // parameters tuned to Pb-Pb @ 5.02 TeV
  inline static Double_t fPtP0{797.446};
  inline static Double_t fPtP1{0.830278};
  inline static Double_t fPtP2{0.632177};
  inline static Double_t fPtP3{10.2202};
  inline static Double_t fPtP4{-0.000614809};
  inline static Double_t fPtP5{-1.70993};

  inline static Double_t fYP0{1.87732};
  inline static Double_t fYP1{0.00658212};
  inline static Double_t fYP2{-0.0988071};
  inline static Double_t fYP3{-0.000452746};
  inline static Double_t fYP4{0.00269782};

  O2_GeneratorParamMuon() : GeneratorTGenerator("ParamMuon")
  {
    fParamMuon = new GeneratorParam(2, -1, PtMuon, YMuon, V2Muon, IpMuon);
    fParamMuon->SetPtRange(0.1, 999.);
    fParamMuon->SetYRange(-4.3, -2.3);
    fParamMuon->SetPhiRange(0., 360.);
    fParamMuon->SetDecayer(new TPythia6Decayer()); // "no decayer" error otherwise
    fParamMuon->SetForceDecay(kNoDecay);
    setTGenerator(fParamMuon);
  }

  ~O2_GeneratorParamMuon() { delete fParamMuon; };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    fParamMuon->Init();
    return true;
  }

  // for tuning steps
  static void SetPtPars(Double_t p0, Double_t p1, Double_t p2, Double_t p3,
                        Double_t p4, Double_t p5)
  {
    fPtP0 = p0;
    fPtP1 = p1;
    fPtP2 = p2;
    fPtP3 = p3;
    fPtP4 = p4;
    fPtP5 = p5;
  }

  // for tuning steps
  static void SetYPars(Double_t p0, Double_t p1, Double_t p2, Double_t p3,
                       Double_t p4)
  {
    fYP0 = p0;
    fYP1 = p1;
    fYP2 = p2;
    fYP3 = p3;
    fYP4 = p4;
  }

  void SetNSignalPerEvent(Int_t nsig) { fParamMuon->SetNumberParticles(nsig); }

  // muon composition
  static Int_t IpMuon(TRandom* ran)
  {
    if (ran->Rndm() < 0.5) {
      return 13;
    } else {
      return -13;
    }
  }

  // muon pT
  static Double_t PtMuon(const Double_t* px, const Double_t*)
  {
    Double_t x = px[0];
    return fPtP0 * (1. / TMath::Power(fPtP1 + TMath::Power(x, fPtP2), fPtP3) +
                    fPtP4 * TMath::Exp(fPtP5 * x));
  }

  // muon y
  static Double_t YMuon(const Double_t* py, const Double_t*)
  {
    Double_t y = py[0];
    return fYP0 * (1. + fYP1 * y + fYP2 * y * y + fYP3 * y * y * y +
                   fYP4 * y * y * y * y);
  }

  static Double_t V2Muon(const Double_t*, const Double_t*)
  {
    // muon v2
    return 0.;
  }

 private:
  GeneratorParam* fParamMuon{nullptr};
};

} // namespace eventgen
} // namespace o2

FairGenerator* paramMuGen(Double_t ptP0 = 797.446, Double_t ptP1 = 0.830278,
                          Double_t ptP2 = 0.632177, Double_t ptP3 = 10.2202,
                          Double_t ptP4 = -0.000614809, Double_t ptP5 = -1.70993,
                          Double_t yP0 = 1.87732, Double_t yP1 = 0.00658212,
                          Double_t yP2 = -0.0988071, Double_t yP3 = -0.000452746,
                          Double_t yP4 = 0.00269782, Int_t nMuons = 2, TString pdgs = "13")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::O2_GeneratorParamMuon>();
  o2::eventgen::O2_GeneratorParamMuon::SetPtPars(ptP0, ptP1, ptP2, ptP3, ptP4, ptP5);
  o2::eventgen::O2_GeneratorParamMuon::SetYPars(yP0, yP1, yP2, yP3, yP4);
  gen->SetNSignalPerEvent(nMuons); // number of muons per event

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }

  gen->PrintDebug();
  return gen;
}