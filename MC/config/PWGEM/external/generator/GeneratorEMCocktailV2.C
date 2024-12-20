R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/external/generator)
R__LOAD_LIBRARY(libpythia6)
#include "GeneratorCocktail.C"

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

class GeneratorEMCocktailV2 : public GeneratorCocktail {
public:
  GeneratorEMCocktailV2()
      : fDecayer(nullptr), fDecayMode(kAll),
        fWeightingMode(kNonAnalog), fParametrizationFile(""),
        fParametrizationDir(""), fV2ParametrizationDir(""), fNPart(1000),
        fCollisionSystem(GeneratorParamEMlibV2::kpp7TeV),
        fCentrality(GeneratorParamEMlibV2::kpp),
        fV2Systematic(GeneratorParamEMlibV2::kNoV2Sys), fUseYWeighting(kFALSE),
        fDynPtRange(kFALSE), fForceConv(kFALSE), fSelectedParticles(0x3FFFFFF),
        fUseFixedEP(kFALSE) {}

  ~GeneratorEMCocktailV2() {}

  struct GeneratorIDs {
    Int_t LibID;
    const char *Name;
    Int_t ParticleID;
    Int_t GeneratorID;
  };

  GeneratorIDs Generators[GeneratorParamEMlibV2::kNParticles] = {
      {GeneratorParamEMlibV2::kPizero, "Pizero", 111, 0x00001},
      {GeneratorParamEMlibV2::kEta, "Eta", 221, 0x00002},
      {GeneratorParamEMlibV2::kRho0, "Rho", 113, 0x00004},
      {GeneratorParamEMlibV2::kOmega, "Omega", 223, 0x00008},
      {GeneratorParamEMlibV2::kEtaprime, "Etaprime", 331, 0x00010},
      {GeneratorParamEMlibV2::kPhi, "Phi", 333, 0x00020},
      {GeneratorParamEMlibV2::kJpsi, "Jpsi", 443, 0x00040},
      {GeneratorParamEMlibV2::kPsi2S, "Psi2S", 100443, 0x00080},
      {GeneratorParamEMlibV2::kUpsilon, "Upsilon", 553, 0x00100},
      {GeneratorParamEMlibV2::kSigma0, "Sigma0", 3212, 0x00200},
      {GeneratorParamEMlibV2::kK0s, "K0short", 310, 0x00400},
      {GeneratorParamEMlibV2::kDeltaPlPl, "DeltaPlPl", 2224, 0x00800},
      {GeneratorParamEMlibV2::kDeltaPl, "DeltaPl", 2214, 0x01000},
      {GeneratorParamEMlibV2::kDeltaMi, "DeltaMi", 1114, 0x02000},
      {GeneratorParamEMlibV2::kDeltaZero, "DeltaZero", 2114, 0x04000},
      {GeneratorParamEMlibV2::kRhoPl, "RhoPl", 213, 0x08000},
      {GeneratorParamEMlibV2::kRhoMi, "RhoMi", 213, 0x10000},
      {GeneratorParamEMlibV2::kK0star, "K0star", 313, 0x20000},
      {GeneratorParamEMlibV2::kK0l, "K0long", 130, 0x40000},
      {GeneratorParamEMlibV2::kLambda, "Lambda", 3122, 0x80000},
      {GeneratorParamEMlibV2::kKPl, "KPl", 321, 0x100000},
      {GeneratorParamEMlibV2::kKMi, "KMi", 321, 0x200000},
      {GeneratorParamEMlibV2::kOmegaPl, "OmegaPl", -3334, 0x400000},
      {GeneratorParamEMlibV2::kOmegaMi, "OmegaMi", 3334, 0x800000},
      {GeneratorParamEMlibV2::kXiPl, "XiPl", -3312, 0x1000000},
      {GeneratorParamEMlibV2::kXiMi, "XiMi", 3312, 0x2000000},
      {GeneratorParamEMlibV2::kSigmaPl, "SigamPl", 3224, 0x4000000},
      {GeneratorParamEMlibV2::kSigmaMi, "SigmaMi", 3114, 0x8000000},
      {GeneratorParamEMlibV2::kDirectRealGamma, "DirectRealGamma", 22,
       0x10000000},
      {GeneratorParamEMlibV2::kDirectVirtGamma, "DirectVirtGamma", 22,
       0x20000000}};

  void SetUseYWeighting(Bool_t useYWeighting) {
    fUseYWeighting = useYWeighting;
  }
  void SetDynamicalPtRange(Bool_t dynamicalPtRange) {
    fDynPtRange = dynamicalPtRange;
  }
  void SetParametrizationFile(TString paramFile) {
    fParametrizationFile = paramFile;
  }
  void SetParametrizationFileDirectory(TString paramDir) {
    fParametrizationDir = paramDir;
  }
  void SetParametrizationFileV2Directory(TString paramDir) {
    fV2ParametrizationDir = paramDir;
  }
  void SetDecayer(PythiaDecayerConfig *const decayer) { fDecayer = decayer; }
  void SetDecayMode(Decay_t decay) { fDecayMode = decay; }
  void SetWeightingMode(Weighting_t weight) { fWeightingMode = weight; }
  void SetNPart(Int_t npart) { fNPart = npart; }
  void SetCollisionSystem(GeneratorParamEMlibV2::CollisionSystem_t col) {
    fCollisionSystem = col;
  }
  void SetCentrality(GeneratorParamEMlibV2::Centrality_t cent) {
    fCentrality = cent;
  }
  void SetV2Systematic(GeneratorParamEMlibV2::v2Sys_t v2sys) {
    fV2Systematic = v2sys;
  }
  void SetForceGammaConversion(Bool_t force = kTRUE) { fForceConv = force; }
  void SetFixedEventPlane(Bool_t toFix = kTRUE) { fUseFixedEP = toFix; }
  void SetPtRange(Double_t ptmin, Double_t ptmax) {
    fPtMin = ptmin;
    fPtMax = ptmax;
  }
  void SetYRange(Double_t ymin, Double_t ymax) {
    fYMin = ymin;
    fYMax = ymax;
  }
  void SetPhiRange(Double_t phimin, Double_t phimax) {
    fPhiMin = phimin;
    fPhiMax = phimax;
  }
  void SelectMotherParticles(UInt_t part) { fSelectedParticles = part; }

  Bool_t SetPtParametrizations() {
    TF1 *tempFct = NULL;
    for (Int_t i = 0; i < GeneratorParamEMlibV2::kNHadrons + 1; i++) {
      tempFct = GeneratorParamEMlibV2::GetPtParametrization(i);
      if (!tempFct)
        return kFALSE;
      if (i < GeneratorParamEMlibV2::kNHadrons)
        fPtParametrization[i] = new TF1(*tempFct);
      else
        fParametrizationProton = new TF1(*tempFct);
    }
    return kTRUE;
  }

  //_________________________________________________________________________
  void SetMtScalingFactors() {
    TH1D *tempMtFactorHisto = GeneratorParamEMlibV2::GetMtScalingFactors();
    fMtScalingFactorHisto = new TH1D(*tempMtFactorHisto);
  }

  //_________________________________________________________________________
  Bool_t SetPtYDistributions() {
    TH2F *tempPtY = NULL;
    for (Int_t i = 0; i < GeneratorParamEMlibV2::kNHadrons; i++) {
      tempPtY = GeneratorParamEMlibV2::GetPtYDistribution(i);
      if (tempPtY)
        fPtYDistribution[i] = new TH2F(*tempPtY);
      else
        fPtYDistribution[i] = NULL;
    }

    return kTRUE;
  }

  /* not implemented
    void SetHeaviestHadron(ParticleGenerator_t part)
    {
      Int_t val=kGenPizero;
      while(val<part) val|=val<<1;

      fSelectedParticles=val;
      return;
    }*/

  TF1 *GetPtParametrization(Int_t np) {
    if (np < GeneratorParamEMlibV2::kNHadrons)
      return fPtParametrization[np];
    else if (np == GeneratorParamEMlibV2::kNHadrons)
      return fParametrizationProton;
    else
      return NULL;
  }

  TH1D *GetMtScalingFactors() { return fMtScalingFactorHisto; }

  TH2F *GetPtYDistribution(Int_t np) {
    if (np < GeneratorParamEMlibV2::kNHadrons)
      return fPtYDistribution[np];
    else
      return NULL;
  }

  void GetPtRange(Double_t &ptMin, Double_t &ptMax) {
    ptMin = fPtMin;
    ptMax = fPtMax;
  }

  Double_t GetMaxPtStretchFactor(Int_t pdgCode) {
    Double_t massParticle =
        TDatabasePDG::Instance()->GetParticle(pdgCode)->Mass();
    Double_t massPi0 = TDatabasePDG::Instance()->GetParticle(111)->Mass();
    Double_t factor = massParticle / massPi0;
    if (factor * fPtMax > 300)
      factor = 300. / fPtMax; // so far the input pt parametrizations are
                              // defined up to pt = 300 GeV/c
    return factor;
  }

  Double_t GetYWeight(Int_t np, TParticle *part) {
    if (!fUseYWeighting) {
      return 1.;
    }
    if (!fPtYDistribution[np]) {
      return 1.;
    }
    if (!(part->Pt() > fPtYDistribution[np]->GetXaxis()->GetXmin() &&
          part->Pt() < fPtYDistribution[np]->GetXaxis()->GetXmax())) {
      return 1.;
    }
    if (!(part->Y() > fPtYDistribution[np]->GetYaxis()->GetXmin() &&
          part->Y() < fPtYDistribution[np]->GetYaxis()->GetXmax())) {
      return 1.;
    }
    Double_t weight = 0.;
    weight = fPtYDistribution[np]->GetBinContent(
        fPtYDistribution[np]->GetXaxis()->FindBin(part->Pt()),
        fPtYDistribution[np]->GetYaxis()->FindBin(part->Y()));
    if (!weight) {
      return 1.;
    }
    return weight;
  }

  void AddSource2Generator(Char_t *nameSource, GeneratorParam *genSource,
                           Double_t maxPtStretchFactor = 1.) {
    printf("GeneratorEMCocktailV2: Add %s to generator\n", nameSource);
    // add sources to the cocktail
    Double_t phiMin = fPhiMin * 180. / TMath::Pi();
    Double_t phiMax = fPhiMax * 180. / TMath::Pi();

    genSource->SetPtRange(fPtMin, maxPtStretchFactor * fPtMax);
    genSource->SetPhiRange(phiMin, phiMax);
    genSource->SetYRange(fYMin, fYMax);
    genSource->SetWeighting(fWeightingMode);
    genSource->SetDecayer(fDecayer);
    genSource->SetForceDecay(fDecayMode);
    genSource->SetForceGammaConversion(kFALSE);
    genSource->Init();

    fGeneratorType.push_back(genSource->GetParam());

    CocktailParam *newgen = new CocktailParam(genSource);
    AddGenerator(newgen, 1);
  }

  void CreateCocktail() {
    // create and add sources to the cocktail

    // Set kinematic limits
    Double_t ptMin = fPtMin;
    Double_t ptMax = fPtMax;
    Double_t yMin = fYMin;
    ;
    Double_t yMax = fYMax;
    ;
    Double_t phiMin = fPhiMin * 180. / TMath::Pi();
    Double_t phiMax = fPhiMax * 180. / TMath::Pi();
    printf("GeneratorEMCocktailV2: Ranges pT:%4.1f : %4.1f GeV/c, y:%4.2f : "
           "%4.2f, Phi:%5.1f : %5.1f degrees\n",
           ptMin, ptMax, yMin, yMax, phiMin, phiMax);
    printf("GeneratorEMCocktailV2: the parametrised sources uses the decay "
           "mode %d\n",
           fDecayMode);
    printf("GeneratorEMCocktailV2: generating %d particles per source\n",
           fNPart);
    printf("GeneratorEMCocktailV2: Selected Params:collision system - %d , "
           "centrality - %d\n",
           fCollisionSystem, fCentrality);
    // Initialize user selection for Pt Parameterization and centrality:

    GeneratorParamEMlibV2::SelectParams(fCollisionSystem, fCentrality,
                                        fV2Systematic);
    GeneratorParamEMlibV2::SetMtScalingFactors(fParametrizationFile,
                                               fParametrizationDir);
    SetMtScalingFactors();
    GeneratorParamEMlibV2::SetPtParametrizations(fParametrizationFile,
                                                 fParametrizationDir);
    SetPtParametrizations();
    // Check consistency of pT and flow parameterizations: same centrality?
    if (fV2ParametrizationDir.Length() > 0) { // flow specified
      TRegexp cent("_[0-9][0-9][0-9][0-9]_");
      if (fParametrizationDir(cent) != fV2ParametrizationDir(cent)) {
        printf("GeneratorEMCocktailV2: WARNING: Centrality for pT "
               "parameterization %s differs from centrality for flow "
               "parameterization: %s\n",
               fParametrizationDir.Data(), fV2ParametrizationDir.Data());
      }
      GeneratorParamEMlibV2::SetFlowParametrizations(fParametrizationFile,
                                                     fV2ParametrizationDir);
    }

    if (fDynPtRange)
      printf(
          "GeneratorEMCocktailV2: Dynamical adaption of pT range was chosen, "
          "the number of generated particles will also be adapted\n");

    if (fUseYWeighting) {
      printf("GeneratorEMCocktailV2: Rapidity weighting will be used\n");
      GeneratorParamEMlibV2::SetPtYDistributions(fParametrizationFile,
                                                 fParametrizationDir);
      SetPtYDistributions();
    }

    for (GeneratorIDs g : Generators) {
      // Create and add electron sources to the generator
      if ((g.LibID == GeneratorParamEMlibV2::kDirectRealGamma) ||
          (g.LibID == GeneratorParamEMlibV2::kDirectVirtGamma))
        continue;
      if (fSelectedParticles & g.GeneratorID) {
        Double_t maxPtStretchFactor = 1.;
        if (fDynPtRange)
          maxPtStretchFactor = GetMaxPtStretchFactor(g.ParticleID);
        GeneratorParam *genNew = 0;
        Char_t nameNew[10];
        snprintf(nameNew, 10, g.Name);
        genNew =
            new GeneratorParam((Int_t)(maxPtStretchFactor * fNPart),
                               new GeneratorParamEMlibV2(), g.LibID, "DUMMY");
        AddSource2Generator(nameNew, genNew, maxPtStretchFactor);
        TF1 *fPtNew = genNew->GetPt();
        fYieldArray[g.LibID] =
            fPtNew->Integral(fPtMin, maxPtStretchFactor * fPtMax, 1.e-6);
      }
    }

    TParticlePDG *elPDG = TDatabasePDG::Instance()->GetParticle(11);
    TDatabasePDG::Instance()->AddParticle(
        "ForcedConversionElecton-", "ForcedConversionElecton-", elPDG->Mass(),
        true, 0, elPDG->Charge(), elPDG->ParticleClass(), 220011, 0);
    TDatabasePDG::Instance()->AddParticle(
        "ForcedConversionElecton+", "ForcedConversionElecton+", elPDG->Mass(),
        true, 0, -elPDG->Charge(), elPDG->ParticleClass(), -220011, 0);

    if (fDecayMode != kGammaEM)
      return;
    // gamma not implemented
  }

  // add particles, shift mother/daughter indices and set normaliziation
  bool importParticles() override {
    auto generators = getGenerators();
    int generatorCounter = 0;
    // loop over all generators
    for (auto &g : *generators) {
      int nPart = mParticles.size();
      Int_t type = fGeneratorType[generatorCounter];
      double dNdy = fYieldArray[type];
      g->importParticles();
      // loop over all particles of this generator
      for (auto p : g->getParticles()) {
        // add the particle
        mParticles.push_back(p);
        auto &pEdit = mParticles.back();
        o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(pEdit, o2::mcgenstatus::getHepMCStatusCode(pEdit.GetStatusCode())==1);
        // set the normalization
        double weight = dNdy * pEdit.GetWeight();
        if (fUseYWeighting) {
          weight *= GetYWeight(type, &pEdit);
        }
        pEdit.SetWeight(weight);
        // shift mother/daughter indices
        if (pEdit.GetFirstMother() > -1)
          pEdit.SetFirstMother(pEdit.GetFirstMother() + nPart);
        if (pEdit.GetSecondMother() > -1)
          pEdit.SetLastMother(pEdit.GetSecondMother() + nPart);
        if (pEdit.GetFirstDaughter() > -1)
          pEdit.SetFirstDaughter(pEdit.GetFirstDaughter() + nPart);
        if (pEdit.GetLastDaughter() > -1)
          pEdit.SetLastDaughter(pEdit.GetLastDaughter() + nPart);
      }
      g->clearParticles();
      generatorCounter++;
    }
    return true;
  };

private:
  PythiaDecayerConfig *fDecayer;
  Decay_t fDecayMode; // decay mode in which resonances are forced to decay,
                      // default: kAll
  Weighting_t fWeightingMode;    // weighting mode: kAnalog or kNonAnalog
  TString fParametrizationFile;  // parametrization file
  TString fParametrizationDir;   // parametrization file directory
  TString fV2ParametrizationDir; // parametrization file directory for flow
  Int_t fNPart;                  // multiplicity of each source per event
  Double_t fYieldArray[GeneratorParamEMlibV2::kNParticles]; // array of dN/dy
                                                            // for each source
  TF1 *fPtParametrization[GeneratorParamEMlibV2::kNHadrons]; // pt paramtrizations
  TF1 *fParametrizationProton;       //
  TH1D *fMtScalingFactorHisto;       // mt scaling factors
  TH2F *fPtYDistribution[GeneratorParamEMlibV2::kNHadrons];  // pt-y distribution
  Double_t fPtMin;
  Double_t fPtMax;
  Double_t fYMin;
  Double_t fYMax;
  Double_t fPhiMin;
  Double_t fPhiMax;
  GeneratorParamEMlibV2::CollisionSystem_t
      fCollisionSystem;                            // selected collision system
  GeneratorParamEMlibV2::Centrality_t fCentrality; // selected centrality
  GeneratorParamEMlibV2::v2Sys_t
      fV2Systematic;     // selected systematic error for v2 parameters
  Bool_t fUseYWeighting; // select if input pt-y distributions should be used
                         // for weighting in generation
  Bool_t
      fDynPtRange;   // select if the pt range for the generation should be
                     // adapted to different mother particle weights dynamically
  Bool_t fForceConv; // select whether you want to force all gammas to convert
                     // imidediately
  UInt_t fSelectedParticles; // which particles to simulate, allows to switch on
                             // and off 32 different particles
  Bool_t fUseFixedEP;
  std::vector<Int_t>
      fGeneratorType; // vector that contains the type of the mother particle
                      // for each generator in the list
};

} // namespace eventgen
} // namespace o2

// =======================================================================================================
FairGenerator *
GenerateEMCocktail(Int_t collisionsSystem = GeneratorParamEMlibV2::kpp7TeV,
                   Int_t centrality = GeneratorParamEMlibV2::kpp,
                   Int_t decayMode = 3, Int_t selectedMothers = 63,
                   TString paramFile = "", TString paramFileDir = "",
                   Int_t numberOfParticles = 100, Double_t minPt = 0.,
                   Double_t maxPt = 20., Int_t pythiaErrorTolerance = 2000,
                   Bool_t externalDecayer = 0, // not implemented
                   Bool_t decayLongLived = 1, Bool_t dynamicalPtRange = 0,
                   Bool_t useYWeights = 0, TString paramV2FileDir = "",
                   Bool_t toFixEP = 0, // notimplemented
                   Double_t yGenRange = 0.1, TString useLMeeDecaytable = "",
                   Int_t weightingMode = 1) {

  TString O2DPG_ROOT = TString(getenv("O2DPG_MC_CONFIG_ROOT"));
  paramFile=paramFile.ReplaceAll("$O2DPG_MC_CONFIG_ROOT",O2DPG_ROOT);
  paramFile=paramFile.ReplaceAll("${O2DPG_MC_CONFIG_ROOT}",O2DPG_ROOT);
  useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("$O2DPG_MC_CONFIG_ROOT",O2DPG_ROOT);
  useLMeeDecaytable=useLMeeDecaytable.ReplaceAll("${O2DPG_MC_CONFIG_ROOT}",O2DPG_ROOT);
  if (paramFile.BeginsWith("alien://")){
    TGrid::Connect("alien://");
  }

  auto gener = new o2::eventgen::GeneratorEMCocktailV2();
  auto decayer = new PythiaDecayerConfig();
  if (externalDecayer) decayer->SetDecayerExodus();
  if (decayLongLived) decayer->DecayLongLivedParticles();

  if (useLMeeDecaytable.Length() > 0) {
    decayer->SetDecayTableFile(useLMeeDecaytable.Data());
    decayer->ReadDecayTable();
  }
  (TPythia6::Instance())
      ->SetMSTU(22, pythiaErrorTolerance); // tolerance for error due to rhos


  gener->SetParametrizationFile(paramFile);
  gener->SetParametrizationFileDirectory(paramFileDir);
  gener->SetNPart(numberOfParticles);
  gener->SetPtRange(minPt, maxPt);
  gener->SetFixedEventPlane(toFixEP);
  gener->SetDynamicalPtRange(dynamicalPtRange);
  gener->SetUseYWeighting(useYWeights);
  gener->SetYRange(-yGenRange, yGenRange);
  gener->SetPhiRange(0., 360. * (TMath::Pi() / 180.));
  // gener->SetOrigin(0.,0.,0.);
  // gener->SetSigma(0.,0.,0.);
  // gener->SetVertexSmear(kPerEvent);
  // gener->SetTrackingFlag(0);
  gener->SelectMotherParticles(selectedMothers);
  gener->SetCollisionSystem(
      (GeneratorParamEMlibV2::CollisionSystem_t)collisionsSystem);
  gener->SetCentrality((GeneratorParamEMlibV2::Centrality_t)centrality);
  if (paramV2FileDir.Length() > 0)
    gener->SetParametrizationFileV2Directory(paramV2FileDir);
  // gener->SetV2Systematic((GeneratorParamEMlibV2::v2Sys_t)GeneratorParamEMlibV2::kNoV2Sys);

  if (decayMode == 1) {
    gener->SetDecayMode(kGammaEM); // kGammaEM      => single photon
  } else if (decayMode == 2) {
    gener->SetDecayMode(kElectronEM); // kElectronEM   => single electron
  } else if (decayMode == 3) {
    gener->SetDecayMode(kDiElectronEM); // kDiElectronEM => electron-positron
  }

  gener->SetDecayer(decayer);

  if (weightingMode == 0) {
    gener->SetWeightingMode(kAnalog); // kAnalog    => weight ~ 1
  } else if (weightingMode == 1) {
    gener->SetWeightingMode(kNonAnalog); // kNonAnalog => weight ~ dN/dp_T
  }

  gener->CreateCocktail();

  return gener;
}