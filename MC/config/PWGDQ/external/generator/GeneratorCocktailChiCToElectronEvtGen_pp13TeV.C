// usage
// o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=GeneratorCocktailChiCToElectronEvtGen_pp13TeV.C;GeneratorExternal.funcName=GeneratorCocktailChiCToElectronEvtGen_pp13TeV()"
//

R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/PromptQuarkonia)
#include "GeneratorCocktail.C"
#include "GeneratorEvtGen.C"

namespace o2
{
namespace eventgen
{

class O2_GeneratorParamChiC1 : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamChiC1() : GeneratorTGenerator("ParamChiC1")
  {
    paramChiC1 = new GeneratorParam(1, -1, PtChiC1pp13TeV, YChiC1pp13TeV, V2ChiC1pp13TeV, IpChiC1pp13TeV);
    paramChiC1->SetMomentumRange(0., 1.e6);
    paramChiC1->SetPtRange(0., 1000.);
    paramChiC1->SetYRange(-1.0, 1.0);
    paramChiC1->SetPhiRange(0., 360.);
    paramChiC1->SetDecayer(new TPythia6Decayer()); // Pythia
    paramChiC1->SetForceDecay(kNoDecay);           // particle left undecayed
    setTGenerator(paramChiC1);
  };

  ~O2_GeneratorParamChiC1()
  {
    delete paramChiC1;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    paramChiC1->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig) { paramChiC1->SetNumberParticles(nsig); }

  //-------------------------------------------------------------------------//
  static Double_t PtChiC1pp13TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // prompt J/Psi pT
    // pp, 13TeV (tuned on pp 13 TeV, 2016-2018)
    //
    // ChiC1   R/(1+R12) Jpsi R= Ra+Rb pT(Jpsi), R12 = R12a + R12b pT(Jpsi)+ R12c pT(Jpsi)^2
    // C. Rosenthal, Y. Pachmayer. LHCb chiC/Jpsi and chiC1/chiC2,
    // PLB 718 (2012) 431
    // JHEP 10 (2013) 115, PLB 714 (2012) 215
    // Linear function for chiC to Jpsi and quadratic for ChiC2/ChiC1 

    const Double_t Ra = 0.121;
    const Double_t Rb = 0.011;

    const Double_t R12a = 1.43953;
    const Double_t R12b = -0.145874;
    const Double_t R12c = 0.00638469;

    const Double_t kC = 2.28550e+00;
    const Double_t kpt0 = 3.73619e+00;
    const Double_t kn = 2.81708e+00;
    Double_t pt = px[0];

    Double_t scaleChiC1 = (Ra+ Rb*pt)/(1+R12a+R12b*pt+R12c*pt*pt);	


    return scaleChiC1 * kC * pt / TMath::Power((1. + (pt / kpt0) * (pt / kpt0)), kn);
  }

  //-------------------------------------------------------------------------//
  static Double_t YChiC1pp13TeV(const Double_t* py, const Double_t* /*dummy*/)
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
  static Double_t V2ChiC1pp13TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpChiC1pp13TeV(TRandom*)
  {
    return 20443;
  }

 private:
  GeneratorParam* paramChiC1 = nullptr;
};

class O2_GeneratorParamChiC2 : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamChiC2() : GeneratorTGenerator("ParamChiC2")
  {
    paramChiC2 = new GeneratorParam(1, -1, PtChiC2pp13TeV, YChiC2pp13TeV, V2ChiC2pp13TeV, IpChiC2pp13TeV);
    paramChiC2->SetMomentumRange(0., 1.e6);        // Momentum range added from me
    paramChiC2->SetPtRange(0., 1000.);             // transverse of momentum range
    paramChiC2->SetYRange(-1.0, 1.0);              // rapidity range
    paramChiC2->SetPhiRange(0., 360.);             // phi range
    paramChiC2->SetDecayer(new TPythia6Decayer()); // Pythia decayer
    paramChiC2->SetForceDecay(kNoDecay);           // particle left undecayed
    setTGenerator(paramChiC2);                     // Setting parameters to ParamPsi for Psi(2S)
  };

  ~O2_GeneratorParamChiC2()
  {
    delete paramChiC2;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    paramChiC2->Init();
    return true;
  }
  void SetNSignalPerEvent(Int_t nsig) { paramChiC2->SetNumberParticles(nsig); }

  //-------------------------------------------------------------------------//
  static Double_t PtChiC2pp13TeV(const Double_t* px, const Double_t* /*dummy*/)
  {

    // ChiC2   R/(1+1/R12) Jpsi R= Ra+Rb pT(Jpsi), R12 = R12a + R12b pT(Jpsi)+ R12c pT(Jpsi)^2
    // prompt J/Psi pT
    // pp, 13TeV (tuned on pp 13 TeV, 2016-2018)
    //
    const Double_t Ra = 0.121;
    const Double_t Rb = 0.011;

    const Double_t R12a = 1.43953;
    const Double_t R12b = -0.145874;
    const Double_t R12c = 0.00638469;




    const Double_t kC = 2.28550e+00;
    const Double_t kpt0 = 3.73619e+00;
    const Double_t kn = 2.81708e+00;
    Double_t pt = px[0];
    Double_t scaleChiC2 = (Ra+ Rb*pt)/(1.+1./(R12a+R12b*pt+R12c*pt*pt));	


    return scaleChiC2 * kC * pt / TMath::Power((1. + (pt / kpt0) * (pt / kpt0)), kn);
  }

  //-------------------------------------------------------------------------//
  static Double_t YChiC2pp13TeV(const Double_t* py, const Double_t* /*dummy*/)
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
  static Double_t V2ChiC2pp13TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpChiC2pp13TeV(TRandom*)
  {
    return 445;
  }

 private:
  GeneratorParam* paramChiC2 = nullptr;
};

} // namespace eventgen
} // namespace o2

FairGenerator*
  GeneratorCocktailChiCToElectronEvtGen_pp13TeV()
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genChiC1 = new o2::eventgen::O2_GeneratorParamChiC1;
  genChiC1->SetNSignalPerEvent(1); // signal per event for ChiC1
  auto genChiC2 = new o2::eventgen::O2_GeneratorParamChiC2;
  genChiC2->SetNSignalPerEvent(1);               // signal per event for ChiC2
  genCocktailEvtGen->AddGenerator(genChiC1, 2); // add cocktail --> ChiC1
  genCocktailEvtGen->AddGenerator(genChiC2, 2);  // add cocktail --> ChiC2

  TString pdgs = "20443;445";
  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  genCocktailEvtGen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    genCocktailEvtGen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
//  genCocktailEvtGen->SetForceDecay(kEvtDiElectron);
  genCocktailEvtGen->SetForceDecay(kEvtChiToJpsiGammaToElectronElectron);
  // print debug
  genCocktailEvtGen->PrintDebug();

  return genCocktailEvtGen;
}
