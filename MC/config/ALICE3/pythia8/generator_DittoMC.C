#include "Ditto.h"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <stdexcept>

#if !defined(__CLING__) || defined(__ROOTCLING__)

#include <SimulationDataFormat/MCGenProperties.h>

#include <Generators/GeneratorPythia8.h>
#include <Pythia8/Pythia.h>

#include <FairGenerator.h>
#include <FairPrimaryGenerator.h>

#endif

// Ditto event generator

class GeneratorDittoMC : public o2::eventgen::GeneratorPythia8
{
 public:
  /// Constructor
  GeneratorDittoMC(const TString& tuneFile) : mGenerator(makeConfig(tuneFile))
  {
    mPythia.readString("ProcessLevel:all = off");
  }

  bool generateEvent() override
  {
    mGenerator.generate();
    mGenerator.loadParticles(mPythia.event, true);
    return true;
  }

  ///  Destructor
  ~GeneratorDittoMC() = default;

 private:
  static Ditto::Config makeConfig(const TString& tuneFile)
  {
    Ditto::Config config;
    if (tuneFile.IsNull()) {
      throw std::runtime_error("DITTO_TUNE_FILE must point to a Ditto tune file");
    }
    config.tuneFile = tuneFile;

    const char* alienProcId = std::getenv("ALIEN_PROC_ID");
    config.seed = alienProcId ? static_cast<std::uint64_t>(std::atoll(alienProcId)) : 0;
    Printf("Using Ditto tune: %s and seed: %lu\n", config.tuneFile.c_str(), config.seed);
    return config;
  }

  Ditto::Generator mGenerator;
};

FairGenerator* generator_DittoMC(const TString& tuneFile)
{
  return new GeneratorDittoMC(tuneFile);
}
