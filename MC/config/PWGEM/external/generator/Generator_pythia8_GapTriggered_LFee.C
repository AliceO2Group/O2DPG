R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/external/generator)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGEM/external/generator)
R__LOAD_LIBRARY(libpythia6)
R__LOAD_LIBRARY(libEGPythia6)
#include "GeneratorCocktailWithGap.C"
#include "GeneratorEvtGen.C"

using namespace std;
using namespace Pythia8;

namespace o2 {
namespace eventgen {

class CocktailParam : public GeneratorTGenerator {
public:
 CocktailParam(GeneratorParam *thisGenerator)
    //: GeneratorTGenerator("thisGenerator") {
    : GeneratorTGenerator(thisGenerator->GetName()) {
   setTGenerator(thisGenerator);
 };

  ~CocktailParam() { delete thisGenerator; };

private:
   GeneratorParam *thisGenerator = nullptr;
};

class O2_GeneratorParamJpsi : public GeneratorTGenerator
{
 public:
  O2_GeneratorParamJpsi() : GeneratorTGenerator("ParamJpsi")
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

class O2_GeneratorParamPsi : public GeneratorTGenerator
{
 public:
  O2_GeneratorParamPsi() : GeneratorTGenerator("ParamPsi")
  {
    paramPsi = new GeneratorParam(1, -1, PtPsi, YPsi, V2Psi, IpPsi);
    paramPsi->SetMomentumRange(0., 1.e6);        // Momentum range added from me
    paramPsi->SetPtRange(0., 25.);               // transverse of momentum range
    paramPsi->SetYRange(-1.0, 1.0);              // rapidity range
    paramPsi->SetPhiRange(0., 360.);             // phi range
    paramPsi->SetDecayer(new TPythia6Decayer()); // Pythia decayer
    paramPsi->SetForceDecay(kNoDecay);           // particle left undecayed
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
  static Double_t PtPsi(const Double_t* px, const Double_t* /*dummy*/)
  {
    return 1.;
  }

  //-------------------------------------------------------------------------//
  static Double_t YPsi(const Double_t* py, const Double_t* /*dummy*/)
  {
    return 1.;
  }

  //-------------------------------------------------------------------------//
  static Double_t V2Psi(const Double_t* /*dummy*/, const Double_t* /*dummy*/)
  {
    // psi(2s) v2
    return 0.;
  }

  //-------------------------------------------------------------------------//
  static Int_t IpPsi(TRandom*)
  {
    return 100443;
  }

 private:
  GeneratorParam* paramPsi = nullptr;
};

} // close eventgen
} // close o2

// Predefined generators:
// this function should be called in ini file.
FairGenerator *GeneratorPythia8GapTriggeredLFee_ForEM(TString configsignal = "$O2DPG_ROOT/MC/config/PWGEM/pythia8/generator/pythia8_MB_gapevent.cfg", int inputTriggerRatio = 5, float yMin=-1.2, float yMax=1.2, int nPart = 1) {
  printf("configsignal = %s\n", configsignal.Data());

  //create cocktail generator : mb pythia8, pi0, eta, eta', rho, omega, phi, j/psi, psi(2s)
  auto genCocktailEvtGen = new o2::eventgen::GeneratorEvtGen<GeneratorCocktailWithGap>();
  genCocktailEvtGen->setInputTriggerRatio(inputTriggerRatio);

  // EXODUS decayer
  TString O2DPG_ROOT = TString(getenv("O2DPG_ROOT"));
  auto decayer = new PythiaDecayerConfig();
  decayer->SetDecayerExodus();
  TString useLMeeDecaytable = "$O2DPG_ROOT/MC/config/PWGEM/decaytables/decaytable_LMee.dat";
  useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("$O2DPG_ROOT",O2DPG_ROOT);
  useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("${O2DPG_ROOT}",O2DPG_ROOT);
  decayer->SetDecayTableFile(useLMeeDecaytable.Data());
  decayer->ReadDecayTable();

  // pythia8
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  o2::eventgen::GeneratorPythia8* mb_p8 = new o2::eventgen::GeneratorPythia8("mb_p8", "mb_p8");
  configsignal = configsignal.ReplaceAll("$O2DPG_ROOT",O2DPG_ROOT);
  configsignal = configsignal.ReplaceAll("${O2DPG_ROOT}",O2DPG_ROOT);
  mb_p8->readFile(configsignal.Data());
  mb_p8->readString("Random:setSeed on");
  mb_p8->readString("Random:seed " + std::to_string(seed));
  mb_p8->Init();

  cout << "add mb pythia8 for gap" << endl;
  genCocktailEvtGen->addGeneratorGap(mb_p8, 1);

  cout << "add mb pythia8 for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(mb_p8, 1);

  //Param
  GeneratorParamEMlib *emlib = new GeneratorParamEMlib();

  // LMee cocktail settings:
  float minPt  = 0;
  float maxPt  = 25;
  float minRap = yMin;
  float maxRap = yMax;
  float phiMin = 0.;
  float phiMax = 360.;
  Weighting_t weightMode = kNonAnalog;

  // pi0
  auto genPizero = new GeneratorParam(nPart, emlib, GeneratorParamEMlib::kPizero, "pizero"); // 111
  genPizero->SetName("pizero");
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
  auto geneta = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kEta,"eta"); // 221
  geneta->SetName("eta");
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
  auto genetaprime = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kEtaprime,"etaprime"); // 331
  genetaprime->SetName("etaprime");
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
  auto genrho = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kRho0,"rho"); // 113
  genrho->SetName("rho");
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
  auto genomega = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kOmega,"omega"); //223
  genomega->SetName("omega");
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
  auto genphi = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kPhi,"phi"); //333
  genphi->SetName("phi");
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

  cout << "add pi0 for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(newgenpizero, 1);
  cout << "add eta for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(newgeneta, 1);
  cout << "add etaprime for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(newgenetaprime, 1);
  cout << "add rho for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(newgenrho, 1);
  cout << "add omega for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(newgenomega, 1);
  cout << "add phi for signal" << endl;
  genCocktailEvtGen->addGeneratorSig(newgenphi, 1);

  // J/psi and psi(2S) need to be slightly different since no EXODUS but EvtGen decayer
  auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsi;
  genJpsi->SetNSignalPerEvent(nPart); // signal per event for J/Psi
  genCocktailEvtGen->addGeneratorSig(genJpsi, 1); // add cocktail --> J/Psi
  cout << "add j/psi for signal" << endl;

  auto genPsi = new o2::eventgen::O2_GeneratorParamPsi;
  genPsi->SetNSignalPerEvent(nPart); // signal per event for Psi(2s)
  genCocktailEvtGen->addGeneratorSig(genPsi, 1);  // add cocktail --> Psi(2s)
  cout << "add psi(2S) for signal" << endl;

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

