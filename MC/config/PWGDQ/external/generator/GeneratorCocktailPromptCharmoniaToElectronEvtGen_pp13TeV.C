// usage
// o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=GeneratorCocktailPromptCharmoniaToElectronEvtGen_pp13TeV.C;GeneratorExternal.funcName=GeneratorCocktailPromptCharmoniaToElectronEvtGen_pp13TeV()"
//

R__ADD_INCLUDE_PATH(${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH(${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/PromptQuarkonia)
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
    paramJpsi = new GeneratorParam(1, -1, PtJPsipp13TeV, YJPsipp13TeV, V2JPsipp13TeV, IpJPsipp13TeV);
    paramJpsi->SetMomentumRange(0., 1.e6);
    paramJpsi->SetPtRange(0., 1000.);
    paramJpsi->SetYRange(-1.0, 1.0);
    paramJpsi->SetPhiRange(0., 360.);
    paramJpsi->SetDecayer(new TPythia6Decayer()); // Pythia
    paramJpsi->SetForceDecay(kNoDecay);           // particle left undecayed
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
  static Double_t PtJPsipp13TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // prompt J/Psi pT
    // pp, 13TeV (tuned on pp 13 TeV, 2016-2018)
    //
    const Double_t kC = 2.28550e+00;
    const Double_t kpt0 = 3.73619e+00;
    const Double_t kn = 2.81708e+00;
    Double_t pt = px[0];

    return kC * pt / TMath::Power((1. + (pt / kpt0) * (pt / kpt0)), kn);
  }

  //-------------------------------------------------------------------------//
  static Double_t YJPsipp13TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // jpsi y in pp at 13 TeV, tuned on data, prompt jpsi ALICE+LHCb, 13 TeV
    Double_t y = *py;
    Float_t p0, p1, p2;
    p0 = 7.79382e+00;
    p1 = 2.87827e-06;
    p2 = 4.41847e+00;
    return p0 * TMath::Exp(-(1. / 2.) * TMath::Power(((y - p1) / p2), 2));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2JPsipp13TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpJPsipp13TeV(TRandom*)
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
    paramPsi = new GeneratorParam(1, -1, PtPsipp13TeV, YPsipp13TeV, V2Psipp13TeV, IpPsipp13TeV);
    paramPsi->SetMomentumRange(0., 1.e6);        // Momentum range added from me
    paramPsi->SetPtRange(0., 1000.);             // transverse of momentum range
    paramPsi->SetYRange(-1.0, 1.0);              // rapidity range
    paramPsi->SetPhiRange(0., 360.);             // phi range
    paramPsi->SetDecayer(new TPythia6Decayer()); // Pythia decayer
    paramPsi->SetForceDecay(kNoDecay);           // particle left undecayed
    setTGenerator(paramPsi);                     // Setting parameters to ParamPsi for Psi(2S)
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
  static Double_t PtPsipp13TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // prompt J/Psi pT
    // pp, 13TeV (tuned on pp 13 TeV, 2016-2018)
    //
    const Double_t kC = 2.28550e+00;
    const Double_t kpt0 = 3.73619e+00;
    const Double_t kn = 2.81708e+00;
    Double_t pt = px[0];

    return kC * pt / TMath::Power((1. + (pt / kpt0) * (pt / kpt0)), kn);
  }

  //-------------------------------------------------------------------------//
  static Double_t YPsipp13TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // jpsi y in pp at 13 TeV, tuned on data, prompt jpsi ALICE+LHCb, 13 TeV
    Double_t y = *py;
    Float_t p0, p1, p2;
    p0 = 7.79382e+00;
    p1 = 2.87827e-06;
    p2 = 4.41847e+00;
    return p0 * TMath::Exp(-(1. / 2.) * TMath::Power(((y - p1) / p2), 2));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2Psipp13TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpPsipp13TeV(TRandom*)
  {
    return 100443;
  }

 private:
  GeneratorParam* paramPsi = nullptr;
};

} // namespace eventgen
} // namespace o2

FairGenerator*
  GeneratorCocktailPromptCharmoniaToElectronEvtGen_pp13TeV()
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsi;
  genJpsi->SetNSignalPerEvent(1); // signal per event for J/Psi
  auto genPsi = new o2::eventgen::O2_GeneratorParamPsi;
  genPsi->SetNSignalPerEvent(1);               // signal per event for Psi(2s)
  genCocktailEvtGen->AddGenerator(genJpsi, 1); // add cocktail --> J/Psi
  genCocktailEvtGen->AddGenerator(genPsi, 1);  // add cocktail --> Psi(2s)

  TString pdgs = "443;100443";
  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  genCocktailEvtGen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    genCocktailEvtGen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  genCocktailEvtGen->SetForceDecay(kEvtDiElectron);

  // print debug
  genCocktailEvtGen->PrintDebug();

  return genCocktailEvtGen;
}
