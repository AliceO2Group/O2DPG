//
// generators for bottomonia considering at midrapidity and forward rapidity
//

R__ADD_INCLUDE_PATH(${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/EvtGen)
R__LOAD_LIBRARY(libpythia6)
#include "GeneratorCocktail.C"
#include "GeneratorEvtGen.C"

namespace o2
{
namespace eventgen
{

/////////////////////////////////////////////////////////////////////////////
class O2_GeneratorParamUpsilon1SFwdY : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamUpsilon1SFwdY() : GeneratorTGenerator("ParamUpsilon1S")
  {
    paramUpsilon1S = new GeneratorParam(1, -1, PtUpsilon1Spp13TeV, YUpsilon1Spp13TeV, V2Upsilon1Spp13TeV, IpUpsilon1Spp13TeV);
    paramUpsilon1S->SetMomentumRange(0., 1.e6);
    paramUpsilon1S->SetPtRange(0, 999.);
    paramUpsilon1S->SetYRange(-4.2, -2.3);
    paramUpsilon1S->SetPhiRange(0., 360.);
    paramUpsilon1S->SetDecayer(new TPythia6Decayer());
    paramUpsilon1S->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramUpsilon1S->SetTrackingFlag(1);  // (from AliGenParam) -> check this
    setTGenerator(paramUpsilon1S);
  };

  ~O2_GeneratorParamUpsilon1SFwdY()
  {
    delete paramUpsilon1S;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    paramUpsilon1S->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig) { paramUpsilon1S->SetNumberParticles(nsig); }

  //-------------------------------------------------------------------------//
  static Double_t PtUpsilon1Spp13TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // Upsilon1S pt shape from LHCb pp@13TeV arXiv:1804.09214
    Double_t x = *px;
    Float_t p0, p1, p2, p3;

    p0 = 4.11195e+02;
    p1 = 1.03097e+01;
    p2 = 1.62309e+00;
    p3 = 4.84709e+00;

    return (p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3));
  }

  //-------------------------------------------------------------------------//
  static Double_t YUpsilon1Spp13TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // Upsilon1S y shape from LHCb pp@13TeV arXiv:1804.09214
    Double_t x = *py;
    Float_t p0, p1;

    p0 =  3.07931e+03;
    p1 = -3.53102e-02;

    return (p0 * (1. + p1 * x * x));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2Upsilon1Spp13TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // Upsilon(1S) v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpUpsilon1Spp13TeV(TRandom*)
  {
    return 553;
  }

 private:
  GeneratorParam* paramUpsilon1S = nullptr;
};

/////////////////////////////////////////////////////////////////////////////
class O2_GeneratorParamUpsilon2SFwdY : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamUpsilon2SFwdY() : GeneratorTGenerator("ParamUpsilon2S")
  {
    paramUpsilon2S = new GeneratorParam(1, -1, PtUpsilon2Spp13TeV, YUpsilon2Spp13TeV, V2Upsilon2Spp13TeV, IpUpsilon2Spp13TeV);
    paramUpsilon2S->SetMomentumRange(0., 1.e6);
    paramUpsilon2S->SetPtRange(0, 999.);
    paramUpsilon2S->SetYRange(-4.2, -2.3);
    paramUpsilon2S->SetPhiRange(0., 360.);
    paramUpsilon2S->SetDecayer(new TPythia6Decayer());
    paramUpsilon2S->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramUpsilon2S->SetTrackingFlag(1);  // (from AliGenParam) -> check this
    setTGenerator(paramUpsilon2S);
  };

  ~O2_GeneratorParamUpsilon2SFwdY()
  {
    delete paramUpsilon2S;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    paramUpsilon2S->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig) { paramUpsilon2S->SetNumberParticles(nsig); }

  //-------------------------------------------------------------------------//
  static Double_t PtUpsilon2Spp13TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // Upsilon2S pt shape from LHCb pp@13TeV arXiv:1804.09214
    Double_t x = *px;
    Float_t p0, p1, p2, p3;

    p0 = 8.15699e+01;
    p1 = 1.48060e+01;
    p2 = 1.50018e+00;
    p3 = 6.34208e+00;

    return (p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3));
  }

  //-------------------------------------------------------------------------//
  static Double_t YUpsilon2Spp13TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // Upsilon2s y shape from LHCb pp@13TeV arXiv:1804.09214
    Double_t x = *py;
    Float_t p0, p1;

    p0 =  7.50409e+02;
    p1 = -3.57039e-02;

    return (p0 * (1. + p1 * x * x));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2Upsilon2Spp13TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // Upsilon(2S) v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpUpsilon2Spp13TeV(TRandom*)
  {
    return 100553;
  }

 private:
  GeneratorParam* paramUpsilon2S = nullptr;
};

/////////////////////////////////////////////////////////////////////////////
class O2_GeneratorParamUpsilon3SFwdY : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamUpsilon3SFwdY() : GeneratorTGenerator("ParamUpsilon3S")
  {
    paramUpsilon3S = new GeneratorParam(1, -1, PtUpsilon3Spp13TeV, YUpsilon3Spp13TeV, V2Upsilon3Spp13TeV, IpUpsilon3Spp13TeV);
    paramUpsilon3S->SetMomentumRange(0., 1.e6);
    paramUpsilon3S->SetPtRange(0, 999.);
    paramUpsilon3S->SetYRange(-4.2, -2.3);
    paramUpsilon3S->SetPhiRange(0., 360.);
    paramUpsilon3S->SetDecayer(new TPythia6Decayer());
    paramUpsilon3S->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramUpsilon3S->SetTrackingFlag(1);  // (from AliGenParam) -> check this
    setTGenerator(paramUpsilon3S);
  };

  ~O2_GeneratorParamUpsilon3SFwdY()
  {
    delete paramUpsilon3S;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    paramUpsilon3S->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig) { paramUpsilon3S->SetNumberParticles(nsig); }

  //-------------------------------------------------------------------------//
  static Double_t PtUpsilon3Spp13TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // Upsilon3S pt shape from LHCb pp@13TeV arXiv:1804.09214
    Double_t x = *px;
    Float_t p0, p1, p2, p3;

    p0 = 3.51590e+01;
    p1 = 2.30813e+01;
    p2 = 1.40822e+00;
    p3 = 9.38026e+00;

    return (p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3));
  }

  //-------------------------------------------------------------------------//
  static Double_t YUpsilon3Spp13TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // Upsilon3s y shape from LHCb pp@13TeV arXiv:1804.09214
    Double_t x = *py;
    Float_t p0, p1;

    p0 =  3.69961e+02;
    p1 = -3.54650e-02;

    return (p0 * (1. + p1 * x * x));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2Upsilon3Spp13TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // Upsilon(3S) v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpUpsilon3Spp13TeV(TRandom*)
  {
    return 200553;
  }

 private:
  GeneratorParam* paramUpsilon3S = nullptr;
};


} // namespace eventgen
} // namespace o2

FairGenerator* GeneratorCocktailBottomoniaToMuonEvtGen_pp13TeV()
{

  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genUpsilon1S = new o2::eventgen::O2_GeneratorParamUpsilon1SFwdY;
  genUpsilon1S->SetNSignalPerEvent(1); // 1 Upsilon(1S) generated per event by GeneratorParam

  auto genUpsilon2S = new o2::eventgen::O2_GeneratorParamUpsilon2SFwdY;
  genUpsilon2S->SetNSignalPerEvent(1); // 1 Upsilon(2S) generated per event by GeneratorParam

  auto genUpsilon3S = new o2::eventgen::O2_GeneratorParamUpsilon3SFwdY;
  genUpsilon3S->SetNSignalPerEvent(1); // 1 Upsilon(3S) generated per event by GeneratorParam

  genCocktailEvtGen->AddGenerator(genUpsilon1S, 1); // add Upsilon(1S) generator
  genCocktailEvtGen->AddGenerator(genUpsilon2S, 1); // add Upsilon(2S) generator
  genCocktailEvtGen->AddGenerator(genUpsilon3S, 1); // add Upsilon(3S) generator

  TString pdgs = "553;100553;200553";
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