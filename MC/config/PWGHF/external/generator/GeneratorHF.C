/// \author R+Preghenella - July 2020

// Example of an implementation of an event generator
// that provides HF signals for embedding in background

R__ADD_INCLUDE_PATH($PYTHIA_ROOT/include)

#include "Pythia8/Pythia.h"

namespace o2
{
namespace eventgen
{

class GeneratorHF : public GeneratorPythia8
{

 public:
  GeneratorHF() : GeneratorPythia8(){};
  ~GeneratorHF() = default;

  // We initialise the local Pythia8 event where we store the particles
  // of the signal event that is the sum of multiple Pythia8 events
  // generated according to the generateEvent() function below.
  Bool_t Init() override
  {
    mOutputEvent.init("(GeneratorHF output event)", &mPythia.particleData);
    return GeneratorPythia8::Init();
  }

  // This function is called by the primary generator
  // for each event in case we are in embedding mode.
  // We use it to setup the number of signal events
  // to be generated and to be embedded on the background.
  void notifyEmbedding(const o2::dataformats::MCEventHeader* bkgHeader) override
  {
    mEvents = mFormula.Eval(bkgHeader->GetB());
    std::cout << " --- notify embedding: impact parameter is " << bkgHeader->GetB() << ", generating " << mEvents << " signal events " << std::endl;
  };

  // We override this function to be able to generate multiple
  // events and build an output event that is the sum of them
  // where we have stripped out only the sub-event starting from
  // the c-cbar ancestor particle
  Bool_t generateEvent() override
  {

    // reset counter and event
    mOutputEvent.reset();

    // loop over number of events to be generated
    int nEvents = 0;
    while (nEvents < mEvents) {

      // generate event
      if (!GeneratorPythia8::generateEvent())
        return false;

      // find the c-cbar ancestor
      auto ancestor = findAncestor(mPythia.event);
      if (ancestor < 0)
        continue;

      // append ancestor and its daughters to the output event
      selectFromAncestor(ancestor, mPythia.event, mOutputEvent);
      nEvents++;
    }

    if (mVerbose)
      mOutputEvent.list();

    return true;
  };

  // We override this event to import the particles from the
  // output event that we have constructed as the sum of multiple
  // Pythia8 sub-events as generated above
  Bool_t importParticles() override
  {
    return GeneratorPythia8::importParticles(mOutputEvent);
  }

  // search for c-cbar mother with at least one c at midrapidity
  int findAncestor(Pythia8::Event& event)
  {
    for (int ipa = 0; ipa < event.size(); ++ipa) {
      auto daughterList = event[ipa].daughterList();
      bool hasq = false, hasqbar = false, atSelectedY = false;
      for (auto ida : daughterList) {
        if (event[ida].id() == mPDG)
          hasq = true;
        if (event[ida].id() == -mPDG)
          hasqbar = true;
        if ((event[ida].y() > mRapidityMin) && (event[ida].y() < mRapidityMax))
          atSelectedY = true;
      }
      if (hasq && hasqbar && atSelectedY)
        return ipa;
    }
    return -1;
  };

  void setPDG(int val) { mPDG = val; };
  void setRapidity(double valMin, double valMax)
  {
    mRapidityMin = valMin;
    mRapidityMax = valMax;
  };
  void setVerbose(bool val) { mVerbose = val; };
  void setFormula(std::string val) { mFormula.Compile(val.c_str()); };

 private:
  TFormula mFormula;
  int mEvents = 1;
  Pythia8::Event mOutputEvent;
  int mPDG = 4;
  double mRapidityMin = -1.5;
  double mRapidityMax = 1.5;
  bool mVerbose = false;
};

} // namespace eventgen
} // namespace o2

/** generator instance and settings **/

FairGenerator*
  GeneratorHF(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false)
{
  auto gen = new o2::eventgen::GeneratorHF();
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setVerbose(verbose);
  gen->setFormula("max(1.,120.*(x<5.)+80.*(1.-x/20.)*(x>5.)*(x<11.)+240.*(1.-x/13.)*(x>11.))");

  return gen;
}

FairGenerator*
  GeneratorHF_ccbar(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false)
{
  auto gen = new o2::eventgen::GeneratorHF();
  gen->setPDG(4);
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setVerbose(verbose);
  gen->setFormula("max(1.,120.*(x<5.)+80.*(1.-x/20.)*(x>5.)*(x<11.)+240.*(1.-x/13.)*(x>11.))");

  return gen;
}

FairGenerator*
  GeneratorHF_bbbar(double rapidityMin = -1.5, double rapidityMax = 1.5, bool verbose = false)
{
  auto gen = new o2::eventgen::GeneratorHF();
  gen->setPDG(5);
  gen->setRapidity(rapidityMin, rapidityMax);
  gen->setVerbose(verbose);
  gen->setFormula("max(1.,120.*(x<5.)+80.*(1.-x/20.)*(x>5.)*(x<11.)+240.*(1.-x/13.)*(x>11.))");

  return gen;
}
