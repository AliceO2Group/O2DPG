#include <Ditto/Ditto.h>
#include <Generators/GeneratorPythia8.h>

#include <FairGenerator.h>

#include <cstdint>
#include <cstdlib>
#include <stdexcept>
#include <string>

// Ditto event generator
class GeneratorDittoMC : public o2::eventgen::GeneratorPythia8
{
 public:
  /// Constructor
  explicit GeneratorDittoMC(const TString& tuneFile) : mGenerator(makeConfig(tuneFile))
  {
    // We use the Pythia8 event only as the container passed to the O2
    // GeneratorPythia8 machinery. Particle production is handled by Ditto.
    mPythia.readString("ProcessLevel:all = off");
  }

  /// Generate one Ditto event and export it to the Pythia8 event record.
  bool generateEvent() override
  {
    mGenerator.generate();
    mGenerator.loadParticles(mPythia.event, true);
    return true;
  }

  /// Destructor
  ~GeneratorDittoMC() override = default;

 private:
  /// Build the Ditto runtime configuration.
  static Ditto::Config makeConfig(const TString& tuneFile)
  {
    if (tuneFile.IsNull()) {
      throw std::runtime_error("Ditto tune file must be specified");
    }

    Ditto::Config config;
    config.mTuneFile = tuneFile.Data();

    // Use the Grid process ID as the Ditto seed when available.
    // Outside the Grid, seed 0 is used.
    if (const char* alienProcId = std::getenv("ALIEN_PROC_ID")) {
      config.mSeed = static_cast<std::uint64_t>(std::strtoull(alienProcId, nullptr, 10));
    } else {
      config.mSeed = static_cast<std::uint64_t>(std::time(nullptr));
    }

    Printf("Using Ditto tune: %s and seed: %llu", config.mTuneFile.c_str(), static_cast<unsigned long long>(config.mSeed));

    return config;
  }

  Ditto::Generator mGenerator;
};

FairGenerator* generator_DittoMC(const TString& tuneFile)
{
  return new GeneratorDittoMC(tuneFile);
}
