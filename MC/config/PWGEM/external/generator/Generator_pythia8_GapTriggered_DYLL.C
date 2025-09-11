#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TString.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"

#include <map>
#include <unordered_set>

using namespace Pythia8;

class GeneratorPythia8GapTriggeredDY : public o2::eventgen::GeneratorPythia8
{
public:
  /// default constructor
  GeneratorPythia8GapTriggeredDY() = default;

  /// constructor
  GeneratorPythia8GapTriggeredDY(TString configsignal, int leptonPdg = 11, int lInputTriggerRatio = 5, int lInputExternalID = 1, int idA = 2212, int idB = 2212, float eCM = 13600.0)
  {
    lGeneratedEvents = 0;
    lInverseTriggerRatio = lInputTriggerRatio;
    lExternalID = lInputExternalID;
    mLeptonPdg = leptonPdg;

    auto seed = (gRandom->TRandom::GetSeed() % 900000000);

    int offset = (int)(gRandom->Uniform(lInverseTriggerRatio)); // create offset to mitigate edge effects due to small number of events per job
    lGeneratedEvents += offset;
    
    cout << "Initalizing extra PYTHIA object used to generate min-bias events..." << endl;
    TString pathconfigMB = gSystem->ExpandPathName("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/pythia8/generator/pythia8_MB_gapevent.cfg");
    pythiaObjectMinimumBias.readFile(pathconfigMB.Data());
    pythiaObjectMinimumBias.readString("Random:setSeed on");
    pythiaObjectMinimumBias.readString("Random:seed " + std::to_string(seed));
    // overwrite basic configration
    pythiaObjectMinimumBias.readString(Form("Beams:idA %d", idA));
    pythiaObjectMinimumBias.readString(Form("Beams:idB %d", idB));
    pythiaObjectMinimumBias.readString(Form("Beams:eCM %f", eCM));
    pythiaObjectMinimumBias.init();
    cout << "Initalization complete" << endl;
    cout << "Initalizing extra PYTHIA object used to generate signal events..." << endl;
    TString pathconfigSignal = gSystem->ExpandPathName(configsignal.Data());
    pythiaObjectSignal.readFile(pathconfigSignal.Data());
    pythiaObjectSignal.readString("Random:setSeed on");
    pythiaObjectSignal.readString("Random:seed " + std::to_string(seed));
    pythiaObjectSignal.readString(Form("23:onIfMatch %d %d", -mLeptonPdg, mLeptonPdg));
    // overwrite basic configration
    pythiaObjectSignal.readString(Form("Beams:idA %d", idA));
    pythiaObjectSignal.readString(Form("Beams:idB %d", idB));
    pythiaObjectSignal.readString(Form("Beams:eCM %f", eCM));

    pythiaObjectSignal.init();
    cout << "Initalization complete" << endl;
    addSubGenerator(0, "default generator");
    addSubGenerator(lExternalID, "Drell-Yan");
  }

  ///  Destructor
  ~GeneratorPythia8GapTriggeredDY() = default;

  void setZRapidity(float yMin, float yMax)
  {
    mZRapidityMin = yMin;
    mZRapidityMax = yMax;
  };

protected:
  //__________________________________________________________________
  Bool_t generateEvent() override
  {
    /// reset event
    mPythia.event.reset();

    // Simple straightforward check to alternate generators
    if (lGeneratedEvents % lInverseTriggerRatio == 0) {
      // Generate event of interest
      Bool_t lGenerationOK = kFALSE;
      while (!lGenerationOK) {
        if (pythiaObjectSignal.next()) {
          lGenerationOK = selectEvent(pythiaObjectSignal.event);
        }
      }
      mPythia.event = pythiaObjectSignal.event;
      notifySubGenerator(lExternalID);
    } else {
      // Generate minimum-bias event
      Bool_t lGenerationOK = kFALSE;
      while (!lGenerationOK) {
        lGenerationOK = pythiaObjectMinimumBias.next();
      }
      mPythia.event = pythiaObjectMinimumBias.event;
      notifySubGenerator(0);
    }

    lGeneratedEvents++;
    // mPythia.next();

    return true;
  }

  bool selectEvent(const Pythia8::Event& event)
  {
    for (size_t iPart = 0; iPart < event.size(); ++iPart) {
      if (event[iPart].id() == 23 && event[iPart].daughterList().size() == 2 && (mZRapidityMin < event[iPart].y() && event[iPart].y() < mZRapidityMax)
          && std::abs(event[event[iPart].daughter1()].id()) == mLeptonPdg && std::abs(event[event[iPart].daughter2()].id()) == mLeptonPdg && event[event[iPart].daughter1()].id() * event[event[iPart].daughter2()].id() < 0) { // Z/gamma* -> l+l-
        printf("Z/gamma* is found. rapidity = %f, event[iPart].daughterList().size() = %zu\n", event[iPart].y(), event[iPart].daughterList().size());
        printf("event[event[iPart].daughter1()].id() = %d\n", event[event[iPart].daughter1()].id());
        printf("event[event[iPart].daughter2()].id() = %d\n", event[event[iPart].daughter2()].id());
        return true;
      }
    } // end of particle loop
    return false;
  };

private:
  // Interface to override import particles
  Pythia8::Event mOutputEvent;

  // Properties of selection
  int mLeptonPdg;
  float mZRapidityMin;
  float mZRapidityMax;

  // Control gap-triggering
  Long64_t lGeneratedEvents;
  int lInverseTriggerRatio;
  // ID for different generators
  int lExternalID;

  // Base event generators
  Pythia8::Pythia pythiaObjectMinimumBias; ///Minimum bias collision generator
  Pythia8::Pythia pythiaObjectSignal;      ///Signal collision generator
};

// Predefined generators:

FairGenerator* GeneratorPythia8GapTriggeredDYll(int inputTriggerRatio, int inputExternalID, int pdgLepton = 11, float yMin = -1.5, float yMax = 1.5, int idA = 2212, int idB = 2212, float eCM = 13600.0)
{
  auto myGen = new GeneratorPythia8GapTriggeredDY("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/pythia8/generator/pythia8_DY.cfg", pdgLepton, inputTriggerRatio, inputExternalID, idA, idB, eCM);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setZRapidity(yMin, yMax);
  return myGen;
}

