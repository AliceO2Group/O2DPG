R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/EvtGen)
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/external/generator)
R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGEM/external/generator)
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


//my generator class
class GeneratorPythia8GapTriggeredLFmumu : public GeneratorPythia8 {

  public:
    GeneratorPythia8GapTriggeredLFmumu() : GeneratorPythia8() {
      mGeneratedEvents = 0;
      mInverseTriggerRatio = 1;
      fGeneratorCocktail = 0x0;
      mMode = -1;
      mTargetPDG = 0;
    };

    GeneratorPythia8GapTriggeredLFmumu(int lInputTriggerRatio, float yMin, float yMax, int nPart, int mode) : GeneratorPythia8() {
      mGeneratedEvents = 0;
      mInverseTriggerRatio = lInputTriggerRatio;
      mMode = mode;
      // LMee cocktail settings:
      float minPt  = 0;
      float maxPt  = 25;
      float phiMin = 0.;
      float phiMax = 360.;
      Weighting_t weightMode = kNonAnalog;

      //create cocktail generator : eta, eta', rho, omega, phi
      fGeneratorCocktail = new o2::eventgen::GeneratorEvtGen<GeneratorCocktail>();

      // EXODUS decayer
      TString O2DPG_ROOT = TString(getenv("O2DPG_MC_CONFIG_ROOT"));
      auto decayer = new PythiaDecayerConfig();
      decayer->SetDecayerExodus();
      TString useLMeeDecaytable = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/decaytables/decaytable_LMee.dat";
      useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("$O2DPG_MC_CONFIG_ROOT",O2DPG_ROOT);
      useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("${O2DPG_MC_CONFIG_ROOT}",O2DPG_ROOT);
      decayer->SetDecayTableFile(useLMeeDecaytable.Data());
      decayer->ReadDecayTable();
      decayer->DecayToDimuons();

      //Param
      GeneratorParamEMlib *emlib = new GeneratorParamEMlib();

      // eta
      auto geneta = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kEta,"eta"); // 221
      geneta->SetName("eta");
      geneta->SetMomentumRange(0., 200.);
      geneta->SetPtRange(minPt, maxPt);
      geneta->SetYRange(yMin, yMax);
      geneta->SetPhiRange(phiMin, phiMax);
      geneta->SetWeighting(weightMode); // flat pt, y and v2 zero 
      geneta->SetDecayer(decayer); // EXOUS;
      geneta->SetForceDecay(kDiMuon); // Dielectrons
      geneta->SetForceGammaConversion(kFALSE);
      geneta->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
      geneta->Init();
      CocktailParam *newgeneta = new CocktailParam(geneta);

      // etaprime
      auto genetaprime = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kEtaprime,"etaprime"); // 331
      genetaprime->SetName("etaprime");
      genetaprime->SetMomentumRange(0., 200.);
      genetaprime->SetPtRange(minPt, maxPt);
      genetaprime->SetYRange(yMin, yMax);
      genetaprime->SetPhiRange(phiMin, phiMax);
      genetaprime->SetWeighting(weightMode); // flat pt, y and v2 zero 
      genetaprime->SetDecayer(decayer); // EXOUS;
      genetaprime->SetForceDecay(kDiMuon); // Dielectrons
      genetaprime->SetForceGammaConversion(kFALSE);
      genetaprime->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
      genetaprime->Init();
      CocktailParam *newgenetaprime = new CocktailParam(genetaprime);

      // rho
      auto genrho = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kRho0,"rho"); // 113
      genrho->SetName("rho");
      genrho->SetMomentumRange(0., 200.);
      genrho->SetPtRange(minPt, maxPt);
      genrho->SetYRange(yMin, yMax);
      genrho->SetPhiRange(phiMin, phiMax);
      genrho->SetWeighting(weightMode); // flat pt, y and v2 zero 
      genrho->SetDecayer(decayer); // EXOUS;
      genrho->SetForceDecay(kDiMuon); // Dielectrons
      genrho->SetForceGammaConversion(kFALSE);
      genrho->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
      genrho->Init();
      CocktailParam *newgenrho = new CocktailParam(genrho);

      // Omega
      auto genomega = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kOmega,"omega"); //223
      genomega->SetName("omega");
      genomega->SetMomentumRange(0., 200.);
      genomega->SetPtRange(minPt, maxPt);
      genomega->SetYRange(yMin, yMax);
      genomega->SetPhiRange(phiMin, phiMax);
      genomega->SetWeighting(weightMode); // flat pt, y and v2 zero 
      genomega->SetDecayer(decayer); // EXOUS;
      genomega->SetForceDecay(kDiMuon); // Dielectrons
      genomega->SetForceGammaConversion(kFALSE);
      genomega->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
      genomega->Init();
      CocktailParam *newgenomega = new CocktailParam(genomega);

      // phi
      auto genphi = new GeneratorParam(nPart,emlib,GeneratorParamEMlib::kPhi,"phi"); //333
      genphi->SetName("phi");
      genphi->SetMomentumRange(0., 200.);
      genphi->SetPtRange(minPt, maxPt);
      genphi->SetYRange(yMin, yMax);
      genphi->SetPhiRange(phiMin, phiMax);
      genphi->SetWeighting(weightMode); // flat pt, y and v2 zero 
      genphi->SetDecayer(decayer); // EXOUS;
      genphi->SetForceDecay(kDiMuon); // Dielectrons
      genphi->SetForceGammaConversion(kFALSE);
      genphi->SetSelectAll(kTRUE); // Store also the gamma in pi0->e+e-gamma
      genphi->Init();
      CocktailParam *newgenphi = new CocktailParam(genphi);

      int target_pdg = 1;

      if (mMode < 0) {
        target_pdg = 1;
        cout << "all-particle mode is selected. all 5 mesons are injected in each event" << endl;
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
      } else if (mMode < 100) {
        cout << "1-particle Mode is selected. 1 meson selected randomly per job is injected in each event" << endl;
        TRandom3 *r3 = new TRandom3(0);
        double rndm = r3->Rndm();
        printf("rndm = %f\n", rndm);

        if (rndm < 1/5.) {
          cout << "add eta for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgeneta, 1);
          target_pdg = 221;
        } else if (rndm < 2/5.) {
          cout << "add etaprime for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenetaprime, 1);
          target_pdg = 331;
        } else if (rndm < 3/5.) {
          cout << "add rho for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenrho, 1);
          target_pdg = 113;
        } else if (rndm < 4/5.) {
          cout << "add omega for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenomega, 1);
          target_pdg = 223;
        } else if (rndm < 5/5.) {
          cout << "add phi for signal" << endl;
          fGeneratorCocktail->AddGenerator(newgenphi, 1);
          target_pdg = 333;
        }
        delete r3;
      } else { //directly select meson pdg
        target_pdg = mMode;
        switch (mMode) {
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

    ~GeneratorPythia8GapTriggeredLFmumu() = default;

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
FairGenerator *GeneratorPythia8GapTriggeredLFmumu_ForEM(int inputTriggerRatio = 5, float yMin=-4.3, float yMax=-2.2, int nPart = 1, int mode = -1) {
  auto myGen = new GeneratorPythia8GapTriggeredLFmumu(inputTriggerRatio, yMin, yMax, nPart, mode);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
