/// \author R+Preghenella - April 2020

// Example of an implementation of an external event generator
// that is used and adapts it behavior in an embedding scenario.
//
//   usage: o2sim -g external --configKeyValues 'GeneratorExternal.fileName=adaptive_pythia8.C;GeneratorExternal.funcName="adaptive_pythia8(\"0.001 * x\")"'

using namespace o2::eventgen;

class Adaptive_Pythia8 : public GeneratorPythia8
{
 public:
  Adaptive_Pythia8(const char* formula = "0.01 * x") : GeneratorPythia8(), mFormula("formula", formula){};
  ~Adaptive_Pythia8() = default;

  // update the number of events to be generated
  // according to background primaries and formula
  void notifyEmbedding(const o2::dataformats::MCEventHeader* bkgHeader) override
  {
    auto nPrimaries = bkgHeader->GetNPrim();
    mEvents = mFormula.Eval(nPrimaries);
  };

  // generate event and import particles
  // multiple times according to background and formula
  Bool_t generateEvent() override
  {
    for (int iev = 0; iev < mEvents; ++iev) {
      if (!GeneratorPythia8::generateEvent())
        return false;
      if (!GeneratorPythia8::importParticles())
        return false;
    }
    return true;
  };

  // override this function to avoid importing particles
  // of the last event again as this is called by the base class
  Bool_t importParticles() override { return true; }

 private:
  int mEvents = 1;
  TFormula mFormula;
};

FairGenerator*
  adaptive_pythia8(const char* formula = "0.01 * x")
{
  std::cout << " --- adaptive_pythia8 initialising with formula: " << formula << std::endl;
  auto py8 = new Adaptive_Pythia8(formula);
  return py8;
}
