// usage
// o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp5TeV.C;GeneratorExternal.funcName=GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp5TeV()"
//
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/PromptQuarkonia)
R__LOAD_LIBRARY(libpythia6)
#include "GeneratorCocktail.C"
#include "GeneratorEvtGen.C"

namespace o2
{
namespace eventgen
{

class O2_GeneratorParamJpsi : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamJpsi() : GeneratorTGenerator("ParamJpsi")
  {
    paramJpsi = new GeneratorParam(1, -1, PtJPsipp5TeV, YJPsipp5TeV, V2JPsipp5TeV, IpJPsipp5TeV);
    paramJpsi->SetMomentumRange(0., 1.e6);
    paramJpsi->SetPtRange(0, 999.);
    paramJpsi->SetYRange(-4.2, -2.3);
    paramJpsi->SetPhiRange(0., 360.);
    paramJpsi->SetDecayer(new TPythia6Decayer());
    paramJpsi->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramJpsi->SetTrackingFlag(1);  // (from AliGenParam) -> check this
    setTGenerator(paramJpsi);
  };

  ~O2_GeneratorParamJpsi()
  {
    delete paramJpsi;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    paramJpsi->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig) { paramJpsi->SetNumberParticles(nsig); }

  //-------------------------------------------------------------------------//
  static Double_t PtJPsipp5TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // jpsi pT in pp at 5.02 TeV, tuned on https://www.hepdata.net/record/ins1935680
    Double_t x = *px;
    Float_t p0, p1, p2, p3;
    p0 = 1;
    p1 = 4.30923;
    p2 = 1.82061;
    p3 = 4.37563;
    return p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3);
  }

  //-------------------------------------------------------------------------//
  static Double_t YJPsipp5TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // jpsi y in pp at 5.02 TeV, tuned on https://www.hepdata.net/record/ins1935680
    Double_t y = *py;
    Float_t p0, p1, p2;
    p0 = 1;
    p1 = 0.0338222;
    p2 = 2.96748;
    return p0 * TMath::Exp(-(1. / 2.) * TMath::Power(((y - p1) / p2), 2));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2JPsipp5TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpJPsipp5TeV(TRandom*)
  {
    return 443;
  }

 private:
  GeneratorParam* paramJpsi = nullptr;
};

class O2_GeneratorParamPsi : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamPsi() : GeneratorTGenerator("ParamPsi")
  {
    paramPsi = new GeneratorParam(1, -1, PtPsipp5TeV, YPsipp5TeV, V2Psipp5TeV, IpPsipp5TeV);
    paramPsi->SetMomentumRange(0., 1.e6);
    paramPsi->SetPtRange(0, 999.);
    paramPsi->SetYRange(-4.2, -2.3);
    paramPsi->SetPhiRange(0., 360.);
    paramPsi->SetDecayer(new TPythia6Decayer());
    paramPsi->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramJpsi->SetTrackingFlag(1);  // check this
    setTGenerator(paramPsi);
  };

  ~O2_GeneratorParamPsi()
  {
    delete paramPsi;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    paramPsi->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig) { paramPsi->SetNumberParticles(nsig); }

  //-------------------------------------------------------------------------//
  static Double_t PtPsipp5TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // psi2s pT in pp at 5.02 TeV, tuned on https://www.hepdata.net/record/ins1935680
    Double_t x = *px;
    Float_t p0, p1, p2, p3;
    p0 = 1;
    p1 = 2.6444;
    p2 = 6.17572;
    p3 = 0.701753;
    return p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3);
  }

  //-------------------------------------------------------------------------//
  static Double_t YPsipp5TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // psi2s y in pp at 5.02 TeV, tuned on https://www.hepdata.net/record/ins1935680
    // WARNING! The shape extracted from data provide wired rapidity shape (low stat.), the J/psi one is used 
    Double_t y = *py;
    Float_t p0, p1, p2;
    // Extracted from Psi(2S) Run 2 data
    //p0 = 1;
    //p1 = -17.4857;
    //p2 = 2.98887;
    // Same parametrization as J/psi
    p0 = 1;
    p1 = 0.0338222;
    p2 = 2.96748;
    return p0 * TMath::Exp(-(1. / 2.) * TMath::Power(((y - p1) / p2), 2));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2Psipp5TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpPsipp5TeV(TRandom*)
  {
    return 100443;
  }

 private:
  GeneratorParam* paramPsi = nullptr;
};

} // namespace eventgen
} // namespace o2

FairGenerator* GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp5TeV()
{

  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsi;
  genJpsi->SetNSignalPerEvent(4); // 4 J/psi generated per event by GeneratorParam
  auto genPsi = new o2::eventgen::O2_GeneratorParamPsi;
  genPsi->SetNSignalPerEvent(2);               // 2 Psi(2S) generated per event by GeneratorParam
  genCocktailEvtGen->AddGenerator(genJpsi, 1); // 2/3 J/psi
  genCocktailEvtGen->AddGenerator(genPsi, 1);  // 1/3 Psi(2S)

  TString pdgs = "443;100443";
  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  genCocktailEvtGen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    genCocktailEvtGen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  genCocktailEvtGen->SetForceDecay(kEvtDiMuon);

  return genCocktailEvtGen;
}
