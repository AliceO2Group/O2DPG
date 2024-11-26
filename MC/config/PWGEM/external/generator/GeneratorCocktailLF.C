//
//
//

R__ADD_INCLUDE_PATH(${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH(${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGDQ/external/generator)
#include "GeneratorCocktail.C"
#include "GeneratorEvtGen.C"

namespace o2 {
namespace eventgen {


class CocktailParam : public GeneratorTGenerator {
public:
 CocktailParam(GeneratorParam *thisGenerator)
    : GeneratorTGenerator("thisGenerator") {
   setTGenerator(thisGenerator);
 };

  ~CocktailParam() { delete thisGenerator; };

private:
   GeneratorParam *thisGenerator = nullptr;
};

class O2_GeneratorJpsi : public GeneratorTGenerator
{

 public:
  O2_GeneratorJpsi() : GeneratorTGenerator("ParamJpsi")
  {
    paramJpsi = new GeneratorParam(1, -1, Flat, Flat, V2JPsi, IpJPsi);
    paramJpsi->SetMomentumRange(0., 1.e6);
    paramJpsi->SetPtRange(0., 25.);
    paramJpsi->SetYRange(-1.2, 1.2);
    paramJpsi->SetPhiRange(0., 360.);
    paramJpsi->SetDecayer(new TPythia6Decayer()); // Pythia
    paramJpsi->SetForceDecay(kNoDecay);           // particle left undecayed
    setTGenerator(paramJpsi);
  };

  ~O2_GeneratorJpsi()
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
  static Double_t Flat(const Double_t* px, const Double_t* /*dummy*/)
  {
    return 1.;
  }

  //-------------------------------------------------------------------------//
  static Double_t V2JPsi(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // jpsi v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpJPsi(TRandom*)
  {
    return 443;
  }

 private:
  GeneratorParam* paramJpsi = nullptr;
};


} // close eventgen
} // close o2

FairGenerator*
GeneratorCocktailLF(int nPart, bool ispp)
{
  // Cocktail
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

  // EXODUS decayer
  TString O2DPG_ROOT = TString(getenv("O2DPG_MC_CONFIG_ROOT"));
  auto decayer = new PythiaDecayerConfig();
  decayer->SetDecayerExodus();
  TString useLMeeDecaytable = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/decaytables/decaytable_LMee.dat";
  useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("$O2DPG_MC_CONFIG_ROOT",O2DPG_ROOT);
  useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("${O2DPG_MC_CONFIG_ROOT}",O2DPG_ROOT);
  decayer->SetDecayTableFile(useLMeeDecaytable.Data());
  decayer->ReadDecayTable();

  //Param
  GeneratorParamEMlib *emlib = new GeneratorParamEMlib();

  // LMee cocktail settings:
  Float_t minPt  = 0;
  Float_t maxPt  = 25;
  Float_t minRap = -1.2;
  Float_t maxRap = 1.2;
  Float_t phiMin = 0.;
  Float_t phiMax = 360.;
  Weighting_t weightMode = kNonAnalog;


  // pi0
  auto genPizero = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kPizero,"pizero");
  genPizero->SetMomentumRange(0., 1.e6);
  genPizero->SetPtRange(minPt, maxPt);
  genPizero->SetYRange(minRap, maxRap);
  genPizero->SetPhiRange(phiMin, phiMax);
  genPizero->SetWeighting(weightMode); // flat pt, y and v2 zero 
  genPizero->SetDecayer(decayer); // EXOUS;
  genPizero->SetForceDecay(kDiElectronEM); // Dielectrons
  genPizero->SetForceGammaConversion(kFALSE);
  genPizero->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
  genPizero->Init();
  CocktailParam *newgenpizero = new CocktailParam(genPizero);	

  // eta
  auto geneta = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kEta,"eta");
  geneta->SetMomentumRange(0., 1.e6);
  geneta->SetPtRange(minPt, maxPt);
  geneta->SetYRange(minRap, maxRap);
  geneta->SetPhiRange(phiMin, phiMax);
  geneta->SetWeighting(weightMode); // flat pt, y and v2 zero 
  geneta->SetDecayer(decayer); // EXOUS;
  geneta->SetForceDecay(kDiElectronEM); // Dielectrons
  geneta->SetForceGammaConversion(kFALSE);
  geneta->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
  geneta->Init();
  CocktailParam *newgeneta = new CocktailParam(geneta);

  // etaprime
  auto genetaprime = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kEtaprime,"etaprime");
  genetaprime->SetMomentumRange(0., 1.e6);
  genetaprime->SetPtRange(minPt, maxPt);
  genetaprime->SetYRange(minRap, maxRap);
  genetaprime->SetPhiRange(phiMin, phiMax);
  genetaprime->SetWeighting(weightMode); // flat pt, y and v2 zero 
  genetaprime->SetDecayer(decayer); // EXOUS;
  genetaprime->SetForceDecay(kDiElectronEM); // Dielectrons
  genetaprime->SetForceGammaConversion(kFALSE);
  genetaprime->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
  genetaprime->Init();
  CocktailParam *newgenetaprime = new CocktailParam(genetaprime);


  // rho
  auto genrho = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kRho0,"rho"); 
  genrho->SetMomentumRange(0., 1.e6);
  genrho->SetPtRange(minPt, maxPt);
  genrho->SetYRange(minRap, maxRap);
  genrho->SetPhiRange(phiMin, phiMax);
  genrho->SetWeighting(weightMode); // flat pt, y and v2 zero 
  genrho->SetDecayer(decayer); // EXOUS;
  genrho->SetForceDecay(kDiElectronEM); // Dielectrons
  genrho->SetForceGammaConversion(kFALSE);
  genrho->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
  genrho->Init();
  CocktailParam *newgenrho = new CocktailParam(genrho);

  // Omega
  auto genomega = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kOmega,"omega");
  genomega->SetMomentumRange(0., 1.e6);
  genomega->SetPtRange(minPt, maxPt);
  genomega->SetYRange(minRap, maxRap);
  genomega->SetPhiRange(phiMin, phiMax);
  genomega->SetWeighting(weightMode); // flat pt, y and v2 zero 
  genomega->SetDecayer(decayer); // EXOUS;
  genomega->SetForceDecay(kDiElectronEM); // Dielectrons
  genomega->SetForceGammaConversion(kFALSE);
  genomega->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
  genomega->Init();
  CocktailParam *newgenomega = new CocktailParam(genomega);


  // phi
  auto genphi = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kPhi,"phi");
  genphi->SetMomentumRange(0., 1.e6);
  genphi->SetPtRange(minPt, maxPt);
  genphi->SetYRange(minRap, maxRap);
  genphi->SetPhiRange(phiMin, phiMax);
  genphi->SetWeighting(weightMode); // flat pt, y and v2 zero 
  genphi->SetDecayer(decayer); // EXOUS;
  genphi->SetForceDecay(kDiElectronEM); // Dielectrons
  genphi->SetForceGammaConversion(kFALSE);
  genphi->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
  genphi->Init();
  CocktailParam *newgenphi = new CocktailParam(genphi);


  // J/Psi Need to be slightly different since no EXODUS but EvtGen decayer
  auto genjpsi = new o2::eventgen::O2_GeneratorJpsi;
  genjpsi->SetNSignalPerEvent(nPart); // signal per event for J/Psi
  
  // Add all
  if (!ispp) {

    genCocktailEvtGen->AddGenerator(newgenpizero, 1);
    genCocktailEvtGen->AddGenerator(newgeneta, 1);
    genCocktailEvtGen->AddGenerator(newgenetaprime, 1);
    genCocktailEvtGen->AddGenerator(newgenrho, 1);
    genCocktailEvtGen->AddGenerator(newgenomega, 1);
    genCocktailEvtGen->AddGenerator(newgenphi, 1);
    genCocktailEvtGen->AddGenerator(genjpsi, 1);

    // Treat J/Psi decay
    TString pdgs = "443";
    std::string spdg;
    TObjArray* obj = pdgs.Tokenize(";");
    genCocktailEvtGen->SetSizePdg(obj->GetEntriesFast());
    for (int i = 0; i < obj->GetEntriesFast(); i++) {
      spdg = obj->At(i)->GetName();
      genCocktailEvtGen->AddPdg(std::stoi(spdg), i);
      printf("PDG %d \n", std::stoi(spdg));
    }
    genCocktailEvtGen->SetForceDecay(kEvtDiElectron);

  } else {

    Int_t flag = (Int_t)gRandom->Uniform(0,100);
    Double_t pa = 16; 
    Double_t pb = 33;
    Double_t pc = 50;
    Double_t pd = 67;
    Double_t pe = 84;
    Double_t pf = 100;

   if ((flag>=0) && (flag<pa)) {
     genCocktailEvtGen->AddGenerator(newgenpizero, 1);
   } else if((flag>=pa) && (flag<pb)) {
     genCocktailEvtGen->AddGenerator(newgenetaprime, 1);
   } else if((flag>=pb) && (flag<pc)) {
     genCocktailEvtGen->AddGenerator(newgenrho, 1);
   } else if((flag>=pc) && (flag<pd)) {
     genCocktailEvtGen->AddGenerator(newgenomega, 1);
   } else if((flag>=pd) && (flag<pe)) {
     genCocktailEvtGen->AddGenerator(newgenphi, 1);
   } else if((flag>=pe) && (flag<pf)) {
     genCocktailEvtGen->AddGenerator(newgeneta, 1);
   }
  
  }

  // print debug
  genCocktailEvtGen->PrintDebug();

  return genCocktailEvtGen;
}
