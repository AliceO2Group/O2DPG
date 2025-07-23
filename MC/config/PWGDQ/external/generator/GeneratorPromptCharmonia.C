//
// generators for prompt charmonia considering different cases (prompt jpsi, prompt psi2S, prompt jpsi+psi2S) at midrapidity and forward rapidity
//
// usage:
// Jpsi+Psi2S midy: o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorCocktailPromptCharmoniaToElectronEvtGen_pp13TeV()"
// Jpsi midy:       o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV()"
// Psi2S midy:      o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorParamPromptPSiToElectronEvtGen_pp13TeV()"
// Jpsi+Psi2S fwdy: o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp13TeV()"
// Jpsi fwdy:       o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorParamPromptJpsiToMuonEvtGen_pp13TeV()"
// Psi2S fwdy:      o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorParamPromptPSiToMuonEvtGen_pp13TeV()"
// ChiC1+ChiC2 midy:o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorPromptCharmonia.C;GeneratorExternal.funcName=GeneratorCocktailChiCToElectronEvtGen_pp13TeV()"
//

//

R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
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

class O2_GeneratorParamJpsipp5TeV : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamJpsipp5TeV() : GeneratorTGenerator("ParamJpsi")
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

  ~O2_GeneratorParamJpsipp5TeV()
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

class O2_GeneratorParamPsipp5TeV : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamPsipp5TeV() : GeneratorTGenerator("ParamPsi")
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

  ~O2_GeneratorParamPsipp5TeV()
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
    Double_t y = *py;
    Float_t p0, p1, p2;
    p0 = 1;
    p1 = -17.4857;
    p2 = 2.98887;
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

class O2_GeneratorParamJpsiPbPb5TeV : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamJpsiPbPb5TeV() : GeneratorTGenerator("ParamJpsi")
  {
    paramJpsi = new GeneratorParam(1, -1, PtJPsiPbPb5TeV, YJPsiPbPb5TeV, V2JPsiPbPb5TeV, IpJPsiPbPb5TeV);
    paramJpsi->SetMomentumRange(0., 1.e6);
    paramJpsi->SetPtRange(0, 999.);
    paramJpsi->SetYRange(-4.2, -2.3);
    paramJpsi->SetPhiRange(0., 360.);
    paramJpsi->SetDecayer(new TPythia6Decayer());
    paramJpsi->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramJpsi->SetTrackingFlag(1);  // (from AliGenParam) -> check this
    setTGenerator(paramJpsi);
  };

  ~O2_GeneratorParamJpsiPbPb5TeV()
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
  static Double_t PtJPsiPbPb5TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // jpsi pT in PbPb, tuned on data (2015) -> Castillo embedding https://alice.its.cern.ch/jira/browse/ALIROOT-8174?jql=text%20~%20%22LHC19a2%22
    Double_t x = *px;
    Float_t p0, p1, p2, p3;
    p0 = 1.00715e6;
    p1 = 3.50274;
    p2 = 1.93403;
    p3 = 3.96363;
    return p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3);
  }

  //-------------------------------------------------------------------------//
  static Double_t YJPsiPbPb5TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // jpsi y in PbPb, tuned on data (2015) -> Castillo embedding https://alice.its.cern.ch/jira/browse/ALIROOT-8174?jql=text%20~%20%22LHC19a2%22
    Double_t y = *py;
    Float_t p0, p1, p2;
    p0 = 1.09886e6;
    p1 = 0;
    p2 = 2.12568;
    return p0 * TMath::Exp(-(1. / 2.) * TMath::Power(((y - p1) / p2), 2));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2JPsiPbPb5TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpJPsiPbPb5TeV(TRandom*)
  {
    return 443;
  }

 private:
  GeneratorParam* paramJpsi = nullptr;
};

class O2_GeneratorParamPsiPbPb5TeV : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamPsiPbPb5TeV() : GeneratorTGenerator("ParamPsi")
  {
    paramPsi = new GeneratorParam(1, -1, PtPsiPbPb5TeV, YPsiPbPb5TeV, V2PsiPbPb5TeV, IpPsiPbPb5TeV);
    paramPsi->SetMomentumRange(0., 1.e6);
    paramPsi->SetPtRange(0, 999.);
    paramPsi->SetYRange(-4.2, -2.3);
    paramPsi->SetPhiRange(0., 360.);
    paramPsi->SetDecayer(new TPythia6Decayer());
    paramPsi->SetForceDecay(kNoDecay); // particle left undecayed
    // - - paramJpsi->SetTrackingFlag(1);  // check this
    setTGenerator(paramPsi);
  };

  ~O2_GeneratorParamPsiPbPb5TeV()
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
  static Double_t PtPsiPbPb5TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // jpsi pT in PbPb, tuned on data (2015) -> Castillo embedding https://alice.its.cern.ch/jira/browse/ALIROOT-8174?jql=text%20~%20%22LHC19a2%22
    Double_t x = *px;
    Float_t p0, p1, p2, p3;
    p0 = 1.00715e6;
    p1 = 3.50274;
    p2 = 1.93403;
    p3 = 3.96363;
    return p0 * x / TMath::Power(1. + TMath::Power(x / p1, p2), p3);
  }

  //-------------------------------------------------------------------------//
  static Double_t YPsiPbPb5TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // jpsi y in PbPb, tuned on data (2015) -> Castillo embedding https://alice.its.cern.ch/jira/browse/ALIROOT-8174?jql=text%20~%20%22LHC19a2%22
    Double_t y = *py;
    Float_t p0, p1, p2;
    p0 = 1.09886e6;
    p1 = 0;
    p2 = 2.12568;
    return p0 * TMath::Exp(-(1. / 2.) * TMath::Power(((y - p1) / p2), 2));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2PsiPbPb5TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpPsiPbPb5TeV(TRandom*)
  {
    return 100443;
  }

 private:
  GeneratorParam* paramPsi = nullptr;
};


class O2_GeneratorParamX3872MidY : public GeneratorTGenerator
{

 public:
  O2_GeneratorParamX3872MidY() : GeneratorTGenerator("ParamX3872MidY")
  {
    paramX3872 = new GeneratorParam(1, -1, PtX3872pp13TeV, YX3872pp13TeV, V2X3872pp13TeV, IpX3872pp13TeV);
    paramX3872->SetMomentumRange(0., 1.e6);
    paramX3872->SetPtRange(0., 1000.);
    paramX3872->SetYRange(-1.0, 1.0);
    paramX3872->SetPhiRange(0., 360.);
    paramX3872->SetDecayer(new TPythia6Decayer()); // Pythia
    paramX3872->SetForceDecay(kNoDecay);           // particle left undecayed
    setTGenerator(paramX3872);
  };

  ~O2_GeneratorParamX3872MidY()
  {
    delete paramX3872;
  };

  Bool_t Init() override
  {
    GeneratorTGenerator::Init();
    paramX3872->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig) { paramX3872->SetNumberParticles(nsig); }

  //-------------------------------------------------------------------------//
  static Double_t PtX3872pp13TeV(const Double_t* px, const Double_t* /*dummy*/)
  {
    // prompt X3872 pT
    // pp, 13TeV (tuned LHCb pp 13 TeV)
    //
    const Double_t kC = 7.64519e+00 ;
    const Double_t kpt0 = 5.30628e+00;
    const Double_t kn = 3.30887e+00;
    Double_t pt = px[0];
    return kC * pt / TMath::Power((1. + (pt / kpt0) * (pt / kpt0)), kn);
  }

  //-------------------------------------------------------------------------//
  static Double_t YX3872pp13TeV(const Double_t* py, const Double_t* /*dummy*/)
  {
    // flat rapidity distribution assumed at midrapidity
    return 1.;
  }

  //-------------------------------------------------------------------------//
  static Double_t V2X3872pp13TeV(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // X3872 v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpX3872pp13TeV(TRandom*)
  {
    return 9920443;
  }

 private:
  GeneratorParam* paramX3872 = nullptr;
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

FairGenerator *
GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV(TString pdgs = "443", int nSignalPerEvent = 1)
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::O2_GeneratorParamJpsiMidY>();
  gen->SetNSignalPerEvent(nSignalPerEvent); // number of jpsis per event

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

FairGenerator* GeneratorCocktailPromptCharmoniaToMuonEvtGen_pp5TeV()
{

  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsipp5TeV;
  genJpsi->SetNSignalPerEvent(1); // 1 J/psi generated per event by GeneratorParam
  auto genPsi = new o2::eventgen::O2_GeneratorParamPsipp5TeV;
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
  GeneratorParamPromptPsiToJpsiPiPiEvtGen_pp13TeV(TString pdgs = "100443")
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
  TString pathO2 = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/EvtGen/DecayTablesEvtgen");
  gen->SetDecayTable(Form("%s/PSITOJPSIPIPI.DEC", pathO2.Data()));

  // print debug
  gen->PrintDebug();

  return gen;
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



FairGenerator*
  GeneratorCocktailChiCToElectronEvtGen_pp13TeV()
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genChiC1 = new o2::eventgen::O2_GeneratorParamChiC1;
  genChiC1->SetNSignalPerEvent(1); // signal per event for ChiC1
  auto genChiC2 = new o2::eventgen::O2_GeneratorParamChiC2;
  genChiC2->SetNSignalPerEvent(1);               // signal per event for ChiC2
  genCocktailEvtGen->AddGenerator(genChiC1, 1); // add cocktail --> ChiC1
  genCocktailEvtGen->AddGenerator(genChiC2, 1);  // add cocktail --> ChiC2


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

FairGenerator* 
  GeneratorCocktailPromptCharmoniaToMuonEvtGen_PbPb5TeV()
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsiPbPb5TeV;
  genJpsi->SetNSignalPerEvent(4); // 4 J/psi generated per event by GeneratorParam
  auto genPsi = new o2::eventgen::O2_GeneratorParamPsiPbPb5TeV;
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


FairGenerator*
  GeneratorParamX3872ToJpsiEvtGen_pp13TeV(TString pdgs = "9920443")
{
  auto gen = new o2::eventgen::GeneratorEvtGen<o2::eventgen::O2_GeneratorParamX3872MidY>();
  gen->SetNSignalPerEvent(1); // number of jpsis per event

  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  gen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    gen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  TString pathO2 = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/EvtGen/DecayTablesEvtgen");
  gen->SetDecayTable(Form("%s/X3872TOJPSIPIPI.DEC", pathO2.Data()));

  // print debug
  gen->PrintDebug();

  return gen;
}


FairGenerator* GeneratorCocktailX3872AndPsi2StoJpsi_pp13TeV()
{
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  auto genX3872 = new o2::eventgen::O2_GeneratorParamX3872MidY;
  genX3872->SetNSignalPerEvent(1); // number of jpsis per event
  auto genPsi2S = new o2::eventgen::O2_GeneratorParamPsiMidY;
  genPsi2S->SetNSignalPerEvent(1); // number of jpsis per event
  genCocktailEvtGen->AddGenerator(genX3872, 1); // add J/psi generator
  genCocktailEvtGen->AddGenerator(genPsi2S, 1);  // add Psi(2S) generator

  TString pdgs = "9920443;100443";
  std::string spdg;
  TObjArray* obj = pdgs.Tokenize(";");
  genCocktailEvtGen->SetSizePdg(obj->GetEntriesFast());
  for (int i = 0; i < obj->GetEntriesFast(); i++) {
    spdg = obj->At(i)->GetName();
    genCocktailEvtGen->AddPdg(std::stoi(spdg), i);
    printf("PDG %d \n", std::stoi(spdg));
  }
  TString pathO2 = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/EvtGen/DecayTablesEvtgen");
  genCocktailEvtGen->SetDecayTable(Form("%s/X3872ANDPSI2STOJPSIPIPI.DEC", pathO2.Data()));

  return genCocktailEvtGen;
}


