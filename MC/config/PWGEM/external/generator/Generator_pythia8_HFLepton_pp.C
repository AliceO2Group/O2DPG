#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"

#include <map>
#include <unordered_set>

using namespace Pythia8;

class GeneratorPythia8HFLeptonpp : public o2::eventgen::GeneratorPythia8
{
public:
  /// default constructor
  GeneratorPythia8HFLeptonpp() = default;

  /// constructor
  GeneratorPythia8HFLeptonpp(TString configsignal, int quarkPdg = 4, int lInputExternalID = 0)
  {

    lGeneratedEvents = 0;
    lExternalID = lInputExternalID;
    mQuarkPdg = quarkPdg;

    auto seed = (gRandom->TRandom::GetSeed() % 900000000);

    int offset = (int)(gRandom->Uniform(1)); // create offset to mitigate edge effects due to small number of events per job
    lGeneratedEvents += offset;

    cout << "Initalizing PYTHIA object used to generate signal events..." << endl;
    TString pathconfigSignal = gSystem->ExpandPathName(configsignal.Data());
    pythiaObjectSignal.readFile(pathconfigSignal.Data());
    pythiaObjectSignal.readString("Random:setSeed on");
    pythiaObjectSignal.readString("Random:seed " + std::to_string(seed));
    pythiaObjectSignal.readString("Beams:eCM = 5360.0");
    pythiaObjectSignal.init();
    cout << "Initalization of signal event is complete" << endl;

    // flag the generators using type
    // addCocktailConstituent(type, "interesting");
    // addCocktailConstitent(0, "minbias");
    // Add Sub generators
    addSubGenerator(1, "charm lepton");
    addSubGenerator(2, "beauty forced decay");
    addSubGenerator(3, "beauty no foced decay");
  }

  ///  Destructor
  ~GeneratorPythia8HFLeptonpp() = default;

  void addTriggerOnDaughter(int nb, int pdg)
  {
    mNbDaughter = nb;
    mPdgDaughter = pdg;
  };
  void setQuarkRapidity(float yMin, float yMax)
  {
    mQuarkRapidityMin = yMin;
    mQuarkRapidityMax = yMax;
  };
  void setDaughterRapidity(float yMin, float yMax)
  {
    mDaughterRapidityMin = yMin;
    mDaughterRapidityMax = yMax;
  };

protected:
  //__________________________________________________________________
  Bool_t generateEvent() override
  {
    /// reset event
    mPythia.event.reset();

    // Generate event of interest
    Bool_t lGenerationOK = kFALSE;
    while (!lGenerationOK) {
      if (pythiaObjectSignal.next()) {
        lGenerationOK = selectEvent(pythiaObjectSignal.event);
      }
    }
    mPythia.event = pythiaObjectSignal.event;
    notifySubGenerator(lExternalID);

    lGeneratedEvents++;
    // mPythia.next();

    return true;
  }

  bool selectEvent(const Pythia8::Event& event)
  {
    bool isGoodAtPartonLevel = false, isGoodAtDaughterLevel = (mPdgDaughter != 0) ? false : true;
    int nbDaughter = 0;
    for (auto iPart{0}; iPart < event.size(); ++iPart) {
      // search for Q-Qbar mother with at least one Q in rapidity window
      if (!isGoodAtPartonLevel) {
        auto daughterList = event[iPart].daughterList();
        bool hasQ = false, hasQbar = false, atSelectedY = false;
        for (auto iDau : daughterList) {
          if (event[iDau].id() == mQuarkPdg) {
            hasQ = true;
          }
          if (event[iDau].id() == -mQuarkPdg) {
            hasQbar = true;
          }
          if ((std::abs(event[iDau].id()) == mQuarkPdg) && (event[iDau].y() > mQuarkRapidityMin) && (event[iDau].y() < mQuarkRapidityMax))
            atSelectedY = true;
        }
        if (hasQ && hasQbar && atSelectedY) {
          isGoodAtPartonLevel = true;
        }
      }
      // search for mNbDaughter daughters of type mPdgDaughter in rapidity window
      if (!isGoodAtDaughterLevel) {
        int id = std::abs(event[iPart].id());
        float rap = event[iPart].y();
        if (id == mPdgDaughter) {
          int motherindexa = event[iPart].mother1();
          if (motherindexa > 0) {
            int idmother = std::abs(event[motherindexa].id());
            if (int(std::abs(idmother) / 100.) == 4 || int(std::abs(idmother) / 1000.) == 4 || int(std::abs(idmother) / 100.) == 5 || int(std::abs(idmother) / 1000.) == 5) {
              if (rap > mDaughterRapidityMin && rap < mDaughterRapidityMax) {
                nbDaughter++;
                if (nbDaughter >= mNbDaughter) isGoodAtDaughterLevel = true;
              }
            }
          }
        }
      }
      // we send the trigger
      if (isGoodAtPartonLevel && isGoodAtDaughterLevel) {
        return true;
      }
    }
    return false;
  };

private:
  // Interface to override import particles
  Pythia8::Event mOutputEvent;

  // Properties of selection
  int mQuarkPdg;
  float mQuarkRapidityMin;
  float mQuarkRapidityMax;
  int mPdgDaughter;
  int mNbDaughter;
  float mDaughterRapidityMin;
  float mDaughterRapidityMax;

  Long64_t lGeneratedEvents;
  // ID for different generators
  int lExternalID;

  // Base event generators
  Pythia8::Pythia pythiaObjectSignal;      ///Signal collision generator
};

// Predefined generators:

// Charm-enriched forced decay
FairGenerator* GeneratorPythia8CharmLepton(int inputExternalID, int pdgLepton, float yMinQ = -1.5, float yMaxQ = 1.5, float yMinL = -1, float yMaxL = 1)
{
  auto myGen = new GeneratorPythia8HFLeptonpp("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/pythia8/generator/pythia8_pp_cr2_forceddecayscharm.cfg", 4, inputExternalID);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yMinQ, yMaxQ);
  myGen->addTriggerOnDaughter(2, pdgLepton);
  myGen->setDaughterRapidity(yMinL, yMaxL);
  return myGen;
}

// Beauty-enriched forced decay
FairGenerator* GeneratorPythia8BeautyForcedDecays(int inputExternalID, int pdgLepton, float yMinQ = -1.5, float yMaxQ = 1.5, float yMinL = -1, float yMaxL = 1)
{
  auto myGen = new GeneratorPythia8HFLeptonpp("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/pythia8/generator/pythia8_bbbar_forceddecayscharmbeauty.cfg", 5, inputExternalID);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yMinQ, yMaxQ);
  myGen->addTriggerOnDaughter(2, pdgLepton);
  myGen->setDaughterRapidity(yMinL, yMaxL);
  return myGen;
}

// Beauty-enriched no forced decay
FairGenerator* GeneratorPythia8BeautyNoForcedDecays(int inputExternalID, int pdgLepton, float yMinQ = -1.5, float yMaxQ = 1.5, float yMinL = -1, float yMaxL = 1)
{
  auto myGen = new GeneratorPythia8HFLeptonpp("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGEM/pythia8/generator/pythia8_bbbar.cfg", 5, inputExternalID);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->setQuarkRapidity(yMinQ, yMaxQ);
  myGen->addTriggerOnDaughter(2, pdgLepton);
  myGen->setDaughterRapidity(yMinL, yMaxL);
  return myGen;
}
