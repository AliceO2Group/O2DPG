// usage
// o2-sim -j 4 -n 10 -g external  -o sgn  --configKeyValues "GeneratorExternal.fileName=GeneratorCocktailPromptCharmoniaToMuonEvtGen_PbPb5TeV.C;GeneratorExternal.funcName=GeneratorCocktailPromptCharmoniaToMuonEvtGen_PbPb5TeV()"
//
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/PromptQuarkonia)
#include "GeneratorCocktail.C"
#include "GeneratorEvtGen.C"

namespace o2 {
namespace eventgen {

class O2_GeneratorParamJpsi : public GeneratorTGenerator
{

public:

  O2_GeneratorParamJpsi() : GeneratorTGenerator("ParamJpsi") {
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


  ~O2_GeneratorParamJpsi() {
    delete paramJpsi;
  };

  Bool_t Init() override {
    GeneratorTGenerator::Init();
    paramJpsi->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig){paramJpsi->SetNumberParticles(nsig);}

  //-------------------------------------------------------------------------//
  static Double_t PtJPsiPbPb5TeV(const Double_t *px, const Double_t * /*dummy*/)
  {
  	// jpsi pT in PbPb, tuned on data (2015) -> Castillo embedding https://alice.its.cern.ch/jira/browse/ALIROOT-8174?jql=text%20~%20%22LHC19a2%22
	Double_t x=*px;
	Float_t p0,p1,p2,p3;
	p0 = 1.00715e6;
	p1 = 3.50274;
	p2 = 1.93403;
	p3 = 3.96363;
	return p0 *x / TMath::Power( 1. + TMath::Power(x/p1,p2), p3 );
  }

  //-------------------------------------------------------------------------//
  static Double_t YJPsiPbPb5TeV(const Double_t *py, const Double_t * /*dummy*/)
  {
  	// jpsi y in PbPb, tuned on data (2015) -> Castillo embedding https://alice.its.cern.ch/jira/browse/ALIROOT-8174?jql=text%20~%20%22LHC19a2%22
	Double_t y = *py;
	Float_t p0,p1,p2;
	p0 = 1.09886e6;
	p1 = 0;
	p2 = 2.12568;
	return p0*TMath::Exp(-(1./2.)*TMath::Power(((y-p1)/p2),2));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2JPsiPbPb5TeV(const Double_t * /*dummy*/, const Double_t * /*dummy*/)
  {
        //jpsi v2
        return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpJPsiPbPb5TeV(TRandom *)
  {
        return 443;
  }


private:

  GeneratorParam *paramJpsi = nullptr;

};

class O2_GeneratorParamPsi : public GeneratorTGenerator
{

public:

  O2_GeneratorParamPsi() : GeneratorTGenerator("ParamPsi") {
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

  ~O2_GeneratorParamPsi() {
    delete paramPsi;
  };

  Bool_t Init() override {
    GeneratorTGenerator::Init();
    paramPsi->Init();
    return true;
  }

  void SetNSignalPerEvent(Int_t nsig){paramPsi->SetNumberParticles(nsig);}

  //-------------------------------------------------------------------------//
  static Double_t PtPsiPbPb5TeV(const Double_t *px, const Double_t * /*dummy*/)
  {
  	// jpsi pT in PbPb, tuned on data (2015) -> Castillo embedding https://alice.its.cern.ch/jira/browse/ALIROOT-8174?jql=text%20~%20%22LHC19a2%22
	Double_t x=*px;
	Float_t p0,p1,p2,p3;
	p0 = 1.00715e6;
	p1 = 3.50274;
	p2 = 1.93403;
	p3 = 3.96363;
	return p0 *x / TMath::Power( 1. + TMath::Power(x/p1,p2), p3 );
  }

  //-------------------------------------------------------------------------//
  static Double_t YPsiPbPb5TeV(const Double_t *py, const Double_t * /*dummy*/)
  {
  	// jpsi y in PbPb, tuned on data (2015) -> Castillo embedding https://alice.its.cern.ch/jira/browse/ALIROOT-8174?jql=text%20~%20%22LHC19a2%22
	Double_t y = *py;
	Float_t p0,p1,p2;
	p0 = 1.09886e6;
	p1 = 0;
	p2 = 2.12568;
	return p0*TMath::Exp(-(1./2.)*TMath::Power(((y-p1)/p2),2));
  }

  //-------------------------------------------------------------------------//
  static Double_t V2PsiPbPb5TeV(const Double_t * /*dummy*/, const Double_t * /*dummy*/)
  {
        //jpsi v2
        return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpPsiPbPb5TeV(TRandom *)
  {
        return 100443;
  }


private:

  GeneratorParam *paramPsi = nullptr;

};


}}


FairGenerator* GeneratorCocktailPromptCharmoniaToMuonEvtGen_PbPb5TeV()
{

  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail_class>();

  auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsi;
  genJpsi->SetNSignalPerEvent(4); // 4 J/psi generated per event by GeneratorParam
  auto genPsi = new o2::eventgen::O2_GeneratorParamPsi;
  genPsi->SetNSignalPerEvent(2);  // 2 Psi(2S) generated per event by GeneratorParam
  genCocktailEvtGen->AddGenerator(genJpsi,1); // 2/3 J/psi
  genCocktailEvtGen->AddGenerator(genPsi,1);  // 1/3 Psi(2S)


  TString pdgs = "443;100443";
  std::string spdg;
  TObjArray *obj = pdgs.Tokenize(";");
  genCocktailEvtGen->SetSizePdg(obj->GetEntriesFast());
  for(int i=0; i<obj->GetEntriesFast(); i++) {
   spdg = obj->At(i)->GetName();
   genCocktailEvtGen->AddPdg(std::stoi(spdg),i);
   printf("PDG %d \n",std::stoi(spdg));
  }
  genCocktailEvtGen->SetForceDecay(kEvtDiMuon);

  return genCocktailEvtGen;
}
