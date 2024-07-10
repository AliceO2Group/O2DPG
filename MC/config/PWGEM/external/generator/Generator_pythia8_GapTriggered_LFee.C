R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGDQ/external/generator)
R__ADD_INCLUDE_PATH($O2DPG_ROOT/MC/config/PWGEM/external/generator)
R__LOAD_LIBRARY(libpythia6)
R__LOAD_LIBRARY(libEGPythia6)
#include "GeneratorEvtGen.C"
#include "GeneratorCocktail.C"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"

using namespace std;
using namespace Pythia8;

namespace o2 {
namespace eventgen {

class CocktailParam : public GeneratorTGenerator {
public:
 CocktailParam(GeneratorParam *thisGenerator)
    : GeneratorTGenerator(thisGenerator->GetName()) {
   setTGenerator(thisGenerator);
 };

  ~CocktailParam() { delete thisGenerator; };

private:
   GeneratorParam *thisGenerator = nullptr;
};

class O2_GeneratorParamJpsi : public GeneratorTGenerator {
  public:
    O2_GeneratorParamJpsi() : GeneratorTGenerator("ParamJpsi")
  {
    paramJpsi = new GeneratorParam(1, -1, Flat, Flat, V2JPsi, IpJPsi);
    paramJpsi->SetMomentumRange(0., 25.);
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

class O2_GeneratorParamPsi : public GeneratorTGenerator {
  public:
    O2_GeneratorParamPsi() : GeneratorTGenerator("ParamPsi")
  {
    paramPsi = new GeneratorParam(1, -1, PtPsi, YPsi, V2Psi, IpPsi);
    paramPsi->SetMomentumRange(0., 25.);        // Momentum range added from me
    paramPsi->SetPtRange(0., 25.);               // transverse of momentum range
    paramPsi->SetYRange(-1.2, 1.2);              // rapidity range
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

//my generator class
class GeneratorPythia8GapTriggeredLFee : public GeneratorPythia8 {

  public:
    GeneratorPythia8GapTriggeredLFee() : GeneratorPythia8() {
      mGeneratedEvents = 0;
      mInverseTriggerRatio = 1;
      fGeneratorCocktail = 0x0;
      mMode = -1;
      mTargetPDG = 0;
    };

    GeneratorPythia8GapTriggeredLFee(int lInputTriggerRatio, float yMin, float yMax, int nPart, int mode) : GeneratorPythia8() {
      mGeneratedEvents = 0;
      mInverseTriggerRatio = lInputTriggerRatio;
      mMode = mode;
      // LMee cocktail settings:
      float minPt  = 0;
      float maxPt  = 25;
      float phiMin = 0.;
      float phiMax = 360.;
      Weighting_t weightMode = kNonAnalog;

      //create cocktail generator : pi0, eta, eta', rho, omega, phi, j/psi, psi(2s)
      fGeneratorCocktail = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

      // EXODUS decayer
      TString O2DPG_ROOT = TString(getenv("O2DPG_ROOT"));
      auto decayer = new PythiaDecayerConfig();
      decayer->SetDecayerExodus();
      TString useLMeeDecaytable = "$O2DPG_ROOT/MC/config/PWGEM/decaytables/decaytable_LMee.dat";
      useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("$O2DPG_ROOT",O2DPG_ROOT);
      useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("${O2DPG_ROOT}",O2DPG_ROOT);
      decayer->SetDecayTableFile(useLMeeDecaytable.Data());
      decayer->ReadDecayTable();

      //Param
      GeneratorParamEMlib *emlib = new GeneratorParamEMlib();

      // pi0
      auto genPizero = new GeneratorParam(nPart, emlib, GeneratorParamEMlib::kPizero, "pizero"); // 111
      genPizero->SetName("pizero");
      genPizero->SetMomentumRange(0., 25.);
      genPizero->SetPtRange(minPt, maxPt);
      genPizero->SetYRange(yMin, yMax);
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
      geneta->SetMomentumRange(0., 25.);
      geneta->SetPtRange(minPt, maxPt);
      geneta->SetYRange(yMin, yMax);
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
      genetaprime->SetMomentumRange(0., 25.);
      genetaprime->SetPtRange(minPt, maxPt);
      genetaprime->SetYRange(yMin, yMax);
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
      genrho->SetMomentumRange(0., 25.);
      genrho->SetPtRange(minPt, maxPt);
      genrho->SetYRange(yMin, yMax);
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
      genomega->SetMomentumRange(0., 25.);
      genomega->SetPtRange(minPt, maxPt);
      genomega->SetYRange(yMin, yMax);
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
      genphi->SetMomentumRange(0., 25.);
      genphi->SetPtRange(minPt, maxPt);
      genphi->SetYRange(yMin, yMax);
      genphi->SetPhiRange(phiMin, phiMax);
      genphi->SetWeighting(weightMode); // flat pt, y and v2 zero 
      genphi->SetDecayer(decayer); // EXOUS;
      genphi->SetForceDecay(kDiElectronEM); // Dielectrons
      genphi->SetForceGammaConversion(kFALSE);
      genphi->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
      genphi->Init();
      CocktailParam *newgenphi = new CocktailParam(genphi);

//      // J/psi and psi(2S) need to be slightly different since no EXODUS but EvtGen decayer
//      auto genJpsi = new o2::eventgen::O2_GeneratorParamJpsi;
//      genJpsi->SetNSignalPerEvent(nPart); // signal per event for J/Psi
//
//      auto genPsi = new o2::eventgen::O2_GeneratorParamPsi;
//      genPsi->SetNSignalPerEvent(nPart); // signal per event for Psi(2s)
//
//      TString pdgs = "443;100443";
//      std::string spdg;
//      TObjArray* obj = pdgs.Tokenize(";");
//      fGeneratorCocktail->SetSizePdg(obj->GetEntriesFast());
//      for (int i = 0; i < obj->GetEntriesFast(); i++) {
//        spdg = obj->At(i)->GetName();
//        fGeneratorCocktail->AddPdg(std::stoi(spdg), i);
//        printf("PDG %d \n", std::stoi(spdg));
//      }
//      fGeneratorCocktail->SetForceDecay(kEvtDiElectron);

      int target_pdg = 1;

      if (mMode < 0) {
        target_pdg = 1;
        cout << "all-particle mode is selected. all 6 mesons are injected in each event" << endl;
        cout << "add pi0 for signal" << endl;
        fGeneratorCocktail->AddGenerator(newgenpizero, 1);
        cout << "add eta for signal" << endl;
        fGeneratorCocktail->AddGenerator(newgeneta, 1);
        cout << "add etaprime for signal" << endl;
        fGeneratorCocktail->AddGenerator(newgenetaprime, 1);
        cout << "add rho for signal" << endl;
        fGeneratorCocktail->AddGenerator(newgenrho, 1);
        cout << "add omega for signal" << endl;
        fGeneratorCocktail->AddGenerator(newgenomega, 1);
        cout << "add phi for signal" << endl;
        fGeneratorCocktail->AddGenerator(newgenphi, 1);
        //cout << "add j/psi for signal" << endl;
        //fGeneratorCocktail->AddGenerator(genJpsi, 1); // add cocktail --> J/Psi
        //cout << "add psi(2S) for signal" << endl;
        //fGeneratorCocktail->AddGenerator(genPsi, 1);  // add cocktail --> Psi(2s)
      } else if (mMode < 100) {
        cout << "1-particle Mode is selected. 1 meson selected randomly per job is injected in each event" << endl;
        TRandom3 *r3 = new TRandom3(0);
        double rndm = r3->Rndm();
        printf("rndm = %f\n", rndm);

        if(rndm < 1/6.) {
          cout << "add pi0 for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenpizero, 1);
          target_pdg = 111;
        } else if (rndm < 2/6.) {
          cout << "add eta for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgeneta, 1);
          target_pdg = 221;
        } else if (rndm < 3/6.) {
          cout << "add etaprime for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenetaprime, 1);
          target_pdg = 331;
        } else if (rndm < 4/6.) {
          cout << "add rho for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenrho, 1);
          target_pdg = 113;
        } else if (rndm < 5/6.) {
          cout << "add omega for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenomega, 1);
          target_pdg = 223;
        } else if (rndm < 6/6.) {
          cout << "add phi for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenphi, 1);
          target_pdg = 333;
        }
        //else if (rndm < 7/8.) {
        //  cout << "add j/psi for signal" << endl;
        //  fGeneratorCocktail->AddGenerator(genJpsi, 1); // add cocktail --> J/Psi
        //  target_pdg = 443;
        //} else {
        //  cout << "add psi(2S) for signal" << endl;
        //  fGeneratorCocktail->AddGenerator(genPsi, 1);  // add cocktail --> Psi(2s)
        //  target_pdg = 100443;
        //}
        delete r3;
      } else { //directly select meson pdg
        target_pdg = mMode;
        switch (mMode) {
          case 111 : 
            cout << "add pi0 for signal" << endl;
            fGeneratorCocktail->AddGenerator(newgenpizero, 1);
            break;
          case 221 : 
            cout << "add eta for signal" << endl;
            fGeneratorCocktail->AddGenerator(newgeneta, 1);
            break;
          case 331 : 
            cout << "add etaprime for signal" << endl;
            fGeneratorCocktail->AddGenerator(newgenetaprime, 1);
            break;
          case 113 : 
            cout << "add rho for signal" << endl;
            fGeneratorCocktail->AddGenerator(newgenrho, 1);
            break;
          case 223 : 
            cout << "add omega for signal" << endl;
            fGeneratorCocktail->AddGenerator(newgenomega, 1);
            break;
          case 333 : 
            cout << "add phi for signal" << endl;
            fGeneratorCocktail->AddGenerator(newgenphi, 1);
            break;
//          case 443 : 
//            cout << "add j/psi for signal" << endl;
//            fGeneratorCocktail->AddGenerator(genJpsi, 1); // add cocktail --> J/Psi
//            break;
//          case 100443 : 
//            cout << "add psi(2S) for signal" << endl;
//            fGeneratorCocktail->AddGenerator(genPsi, 1);  // add cocktail --> Psi(2s)
//            break;
          default:
            cout << "!WARNING! default : nothing is added to cocktail generator" << endl;
            target_pdg = 1;
            break;
        }
      }

      // print debug
      fGeneratorCocktail->PrintDebug();
      fGeneratorCocktail->Init();

      cout << "target_pdg for subGeneratorId is " << target_pdg << endl;
      addSubGenerator(0, "gap mb pythia");
      addSubGenerator(target_pdg, "injected cocktail");
      mTargetPDG = target_pdg;
    };

    ~GeneratorPythia8GapTriggeredLFee() = default;

  protected:
    bool generateEvent() override
    {
      GeneratorPythia8::generateEvent();

      if (mGeneratedEvents % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
        fGeneratorCocktail->generateEvent();
        notifySubGenerator(mTargetPDG);
      } else { // gap event
        notifySubGenerator(0);
      }
      mGeneratedEvents++;
      return true;
    }

    bool importParticles() override
    {
      GeneratorPythia8::importParticles();

      bool genOk = false;
      if ((mGeneratedEvents-1) % mInverseTriggerRatio == 0){ // add injected prompt signals to the stack
        fGeneratorCocktail->importParticles();
        int originalSize = mParticles.size();
        for(int ipart=0; ipart < fGeneratorCocktail->getParticles().size(); ipart++){
          TParticle part = TParticle(fGeneratorCocktail->getParticles().at(ipart));
          if(part.GetFirstMother() >= 0) part.SetFirstMother(part.GetFirstMother() + originalSize);
          if(part.GetFirstDaughter() >= 0) part.SetFirstDaughter(part.GetFirstDaughter() + originalSize);
          if(part.GetLastDaughter() >= 0) part.SetLastDaughter(part.GetLastDaughter() + originalSize);
          mParticles.push_back(part);
          // encodeParticleStatusAndTracking method already called in GeneratorEvtGen.C
        }
        fGeneratorCocktail->clearParticles();
      }

      return true;
    }

  private:
    GeneratorEvtGen<GeneratorCocktail> *fGeneratorCocktail;
    // Control gap-triggering
    unsigned long long mGeneratedEvents;
    int mInverseTriggerRatio;
    int mMode;
    int mTargetPDG;
};

} // close eventgen
} // close o2

// Predefined generators: // this function should be called in ini file.
FairGenerator *GeneratorPythia8GapTriggeredLFee_ForEM(int inputTriggerRatio = 5, float yMin=-1.2, float yMax=1.2, int nPart = 1, int mode = -1) {
  auto myGen = new GeneratorPythia8GapTriggeredLFee(inputTriggerRatio, yMin, yMax, nPart, mode);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
