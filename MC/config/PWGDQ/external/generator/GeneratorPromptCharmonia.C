//
// generators for prompt charmonia considering different cases (prompt jpsi, prompt psi2S, prompt jpsi+psi2S) at midrapidity and forward rapidity
//
// usage:
// Jpsi+Psi2S midy: o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=$O2DPG_ROOT/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorCocktailPromptCharmoniaToElectronEvtGen_pp13TeV()"
// Jpsi midy:       o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=$O2DPG_ROOT/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV()"
// Psi2S midy:      o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=$O2DPG_ROOT/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorParamPromptPSiToElectronEvtGen_pp13TeV()"
// Jpsi+Psi2S fwdy: o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=$O2DPG_ROOT/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp13TeV()"
// Jpsi fwdy:       o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=$O2DPG_ROOT/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorParamPromptJpsiToMuonEvtGen_pp13TeV()"
// Psi2S fwdy:      o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=$O2DPG_ROOT/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorParamPromptPSiToMuonEvtGen_pp13TeV()"
//

R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__LOAD_LIBRARY(libpythia6)
#include "GeneratorCocktail.C"
#include "GeneratorEvtGen.C"

namespace o2
{
namespace eventgen
{

class O2_GeneratorParamJpsiMidY : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamJpsiMidY() : GeneratorTGenerator("ParamJpsiMidY")
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

  ~O2_GeneratorParamJpsiMidY()
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

class O2_GeneratorParamPsiMidY : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamPsiMidY() : GeneratorTGenerator("ParamPsi")
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

  ~O2_GeneratorParamPsiMidY()
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

class O2_GeneratorParamJpsiFwdY : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamJpsiFwdY() : GeneratorTGenerator("ParamJpsi")
  {
    paramJpsi = new GeneratorParam(1, -1, PtJPsipp13TeV, YJPsipp13TeV, V2JPsipp13TeV, IpJPsipp13TeV);
    paramJpsi->SetMomentumRange(0., 1.e6);
    paramJpsi->SetPtRange(0, 999.);
    paramJpsi->SetYRange(-4.2, -2.3);
    paramJpsi->SetPhiRange(0., 360.);
    paramJpsi->SetDecayer(new TPythia6Decayer());
    paramJpsi->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramJpsi->SetTrackingFlag(1);  // (from AliGenParam) -> check this
    setTGenerator(paramJpsi);
  };

  ~O2_GeneratorParamJpsiFwdY()
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
    // jpsi pT in pp at 13 TeV, tuned on data (2015)
    Double_t x = *px;
    Float_t p0, p1, p2, p3;
    p0 = 1;
    p1 = 4.75208;
    p2 = 1.69247;
    p3 = 4.49224;
    return p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3);
  }

  //-------------------------------------------------------------------------//
  static Double_t YJPsipp13TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // jpsi y in pp at 13 TeV, tuned on data (2015)
    Double_t y = *py;
    Float_t p0, p1, p2;
    p0 = 1;
    p1 = 0;
    p2 = 2.98887;
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

class O2_GeneratorParamPsiFwdY : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamPsiFwdY() : GeneratorTGenerator("ParamPsi")
  {
    paramPsi = new GeneratorParam(1, -1, PtPsipp13TeV, YPsipp13TeV, V2Psipp13TeV, IpPsipp13TeV);
    paramPsi->SetMomentumRange(0., 1.e6);
    paramPsi->SetPtRange(0, 999.);
    paramPsi->SetYRange(-4.2, -2.3);
    paramPsi->SetPhiRange(0., 360.);
    paramPsi->SetDecayer(new TPythia6Decayer());
    paramPsi->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramJpsi->SetTrackingFlag(1);  // check this
    setTGenerator(paramPsi);
  };

  ~O2_GeneratorParamPsiFwdY()
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
    // jpsi pT in pp at 13 TeV, tuned on data (2015)
    Double_t x = *px;
    Float_t p0, p1, p2, p3;
    p0 = 1;
    p1 = 4.75208;
    p2 = 1.69247;
    p3 = 4.49224;
    return p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3);
  }

  //-------------------------------------------------------------------------//
  static Double_t YPsipp13TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // jpsi y in pp at 13 TeV, tuned on data (2015)
    Double_t y = *py;
    Float_t p0, p1, p2;
    p0 = 1;
    p1 = 0;
    p2 = 2.98887;
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

  auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsiMidY;
  genJpsi->SetNSignalPerEvent(1); // signal per event for J/Psi
  auto genPsi = new o2::eventgen::O2_GeneratorParamPsiMidY;
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

FairGenerator*
  GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV(TString pdgs = "443")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::O2_GeneratorParamJpsiMidY>();
  gen->SetNSignalPerEvent(1); // number of jpsis per event

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtDiElectron);

  // print debug
  gen->PrintDebug();

  return gen;
}

FairGenerator*
  GeneratorParamPromptPsiToElectronEvtGen_pp13TeV(TString pdgs = "100443")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::O2_GeneratorParamPsiMidY>();
  gen->SetNSignalPerEvent(1); // number of jpsis per event

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtDiElectron);

  // print debug
  gen->PrintDebug();

  return gen;
}


FairGenerator* GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp13TeV()
{

  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsiFwdY;
  genJpsi->SetNSignalPerEvent(1); // 1 J/psi generated per event by GeneratorParam
  auto genPsi = new o2::eventgen::O2_GeneratorParamPsiFwdY;
  genPsi->SetNSignalPerEvent(1);               // 1 Psi(2S) generated per event by GeneratorParam
  genCocktailEvtGen->AddGenerator(genJpsi, 1); // add J/psi generator
  genCocktailEvtGen->AddGenerator(genPsi, 1);  // add Psi(2S) generator

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

FairGenerator*
  GeneratorParamPromptJpsiToMuonEvtGen_pp13TeV(TString pdgs = "443")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::O2_GeneratorParamJpsiFwdY>();
  gen->SetNSignalPerEvent(1); // number of jpsis per event

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtDiMuon);

  // print debug
  gen->PrintDebug();

  return gen;
}

FairGenerator*
  GeneratorParamPromptPsiToMuonEvtGen_pp13TeV(TString pdgs = "100443")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::O2_GeneratorParamPsiFwdY>();
  gen->SetNSignalPerEvent(1); // number of jpsis per event

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  gen->SetForceDecay(kEvtDiMuon);

  // print debug
  gen->PrintDebug();

  return gen;
}

