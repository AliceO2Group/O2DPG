#define SKIP_HEPMC_CONVERSION 1
#define HAVE_HEPMC3 1

// O2DPG and ROOT includes
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "fairlogger/Logger.h"
#include "TParticle.h"
#include "TLorentzVector.h"
#include <iostream>
#include <vector>
#include <string>

// ThePEG
#include "ThePEG/Repository/EventGenerator.h"
#include "ThePEG/EventRecord/Event.h"
#include "ThePEG/EventRecord/Particle.h"
#include "ThePEG/EventRecord/Step.h"
#include "ThePEG/Config/ThePEG.h"
#include "ThePEG/PDT/ParticleData.h"
#include "ThePEG/Repository/Repository.h"

// Herwig
#include "Herwig/API/HerwigAPI.h"
#include "Herwig/API/HerwigUI.h"

// Subclass of HerwigUI to provide minimal implementation of the abstract class
class SimpleHerwigUI : public Herwig::HerwigUI
{
public:
  SimpleHerwigUI(const std::string &inFile,
                 Herwig::RunMode::Mode mode = Herwig::RunMode::READ, int seed = 0)
      : m_inFile(inFile), m_mode(mode),
        m_in(inFile), m_out(std::cout), m_err(std::cerr), mSeed(seed)
  {
    if (!m_in)
    {
      LOG(fatal) << "Cannot open Herwig input file: " << inFile;
      exit(1);
    }
    std::string hDir = std::getenv("HERWIG_ROOT");
    if (!hDir.empty())
    {
      Dirs.push_back(hDir + "/share/Herwig");
    }
  }

  Herwig::RunMode::Mode runMode() const override { return m_mode; }

  std::string repository() const override { 
    std::string rpo = std::getenv("HERWIG_ROOT");
    rpo.append("/share/Herwig/HerwigDefaults.rpo");
    return rpo; 
  }
  std::string inputfile() const override { return m_inFile; }
  std::string setupfile() const override { return ""; }

  bool resume() const override { return false; }
  bool tics() const override { return false; }
  std::string tag() const override { return ""; }
  std::string integrationList() const override { return ""; }

  const std::vector<std::string> &prependReadDirectories() const override
  {
    return Dirs;
  }
  const std::vector<std::string> &appendReadDirectories() const override
  {
    static std::vector<std::string> empty;
    return empty;
  }

  long N() const override { return 1; } // number of events
  int seed() const override { return mSeed; }
  int jobs() const override { return 1; }
  unsigned int jobSize() const override { return 1; }
  unsigned int maxJobs() const override { return 1; }

  void quitWithHelp() const override { std::exit(1); }
  void quit() const override { std::exit(1); }

  std::ostream &outStream() const override { return m_out; }
  std::ostream &errStream() const override { return m_err; }
  std::istream &inStream() const override { return m_in; }

private:
  std::string m_inFile;
  Herwig::RunMode::Mode m_mode;
  mutable std::ifstream m_in;
  std::ostream &m_out;
  std::ostream &m_err;
  std::vector<std::string> Dirs;
  int mSeed = 0;
};

namespace o2
{
namespace eventgen
{

/// HERWIG7 event generator using ThePEG interface
/// Author: Marco Giacalone (marco.giacalone@cern.ch)
/// Based on the O2DPG external generator configurations
class GeneratorHerwig : public Generator
{
public:
  /// Default constructor
  GeneratorHerwig(const std::string& configFile = "LHC.in", int seed = -1)
    : mConfigFile(configFile)
    , mEventGenerator(nullptr)
  {
    LOG(info) << "HERWIG7 Generator construction";
    LOG(info) << "Config file: " << mConfigFile;
    std::string extension = mConfigFile.substr(mConfigFile.find_last_of("."));
    if( extension == ".in" ) {
      mIsInputFile = true;
      LOG(info) << "Using input file for configuration";
    } else if(extension == ".run") {
      mIsInputFile = false;
      LOG(info) << "Using run file for configuration";
    } else {
      LOG(fatal) << "No file extension found in config file: " << mConfigFile;
      exit(1);
    }
    if (seed < 0)
    {
      auto &conf = o2::conf::SimConfig::Instance();
      mSeed = gRandom->Integer(conf.getStartSeed());
    } else {
      mSeed = seed;
    }
    LOG(info) << "Using seed: " << mSeed << " for HERWIG simulation";
  }

  /// Destructor
  ~GeneratorHerwig() = default;

  /// Initialize the generator
  Bool_t Init() override
  {
    LOG(info) << "Initializing HERWIG7 Generator";
    if (mIsInputFile) {
      // Process .in file
      return initFromInputFile();
    } else {
      // Process .run file directly
      return initFromRunFile();
    }
  }

  /// Generate event
  Bool_t generateEvent() override
  {
    if (!mEventGenerator) {
      LOG(error) << "Event generator not initialized";
      return kFALSE;
    }
    // Clear previous event particles
    hParticles.clear();

    // Generate the event
    mPEGEvent = mEventGenerator->shoot();

    if (!mPEGEvent)
    {
      LOG(error) << "Failed to generate event";
      return kFALSE;
    }

    // Convert ThePEG event to TParticle format
    convertEvent(mPEGEvent);
    LOG(debug) << "Herwig7 generated " << hParticles.size() << " particles";

    return kTRUE;
  }

  /// Import particles for transport
  Bool_t importParticles() override
  {
    if (hParticles.empty()) {
      LOG(warning) << "No particles to import";
      return kFALSE;
    }

    // Add particles to the primary generator
    for (const auto& particle : hParticles) {
      mParticles.push_back(particle);
    }
    
    return kTRUE;
  }

private:
  std::string mConfigFile;                           ///< HERWIG config file (.in or .run)
  Bool_t mIsInputFile = false;                       ///< True for .in files, false for .run files
  ThePEG::EGPtr mEventGenerator;                     ///< ThePEG event generator
  std::vector<TParticle> hParticles;                 ///< Generated Herwig particles
  ThePEG::EventPtr mPEGEvent;                        ///< Pointer to Current event
  int mSeed = 0;                                     ///< Random seed for Herwig

  void printHerwigSearchPaths()
  {
    const auto &list = ThePEG::Repository::listReadDirs();

    LOG(info) << "Append directories:\n";
    for (const auto &p : list)
      LOG(info) << "  " << p << "\n";
  }

  /// Initialize from .in file
  Bool_t initFromInputFile()
  {
    LOG(info) << "Initializing from .in file: " << mConfigFile;
    
    using namespace ThePEG;
    SimpleHerwigUI ui(mConfigFile, Herwig::RunMode::READ, mSeed);
    Herwig::API::read(ui);
    // For debugging, print the search paths
    // printHerwigSearchPaths();
    // Currently the .run filename is set inside the .in file itself with
    // the line "saverun LHC EventGenerator" or similar. We assume this is the same as
    // the .in file name with .run extension, so change that string accordingly in your .in files.
    std::string runFile = mConfigFile;
    size_t pos = runFile.find_last_of('.');
    runFile.replace(pos, 4, ".run");
    pos = runFile.find_last_of('/');
    runFile = (pos != std::string::npos) ? runFile.substr(pos + 1) : runFile;
    mConfigFile = runFile;
    LOG(info) << "Generated run file: " << runFile;
    auto res = initFromRunFile();
    if (!res) {
      LOG(error) << "Failed to initialize from generated run file";
      return kFALSE;
    }
    return kTRUE;
  }
  
  /// Initialize from .run file
  Bool_t initFromRunFile()
  {
    LOG(info) << "Initializing from .run file: " << mConfigFile;
    
    using namespace ThePEG;

    if (!std::ifstream(mConfigFile))
    {
      LOG(info) << "Run file does not exist: " << mConfigFile;
      return kFALSE;
    }
    SimpleHerwigUI runui(mConfigFile, Herwig::RunMode::RUN, mSeed);
    // Prepare the generator
    mEventGenerator = Herwig::API::prepareRun(runui);
    if (!mEventGenerator)
    {
      LOG(fatal) << "Error: prepareRun() returned null.";
      return kFALSE;
    }

    mEventGenerator->initialize();
    LOG(info) << "Herwig generator initialized successfully.";
    return kTRUE;
  }

  /// Convert ThePEG event to TParticle format
  void convertEvent(ThePEG::EventPtr event)
  {
    if (!event) return;
    
    // Get all particles from the event
    const ThePEG::tPVector& particles = event->getFinalState();
    
    for (size_t i = 0; i < particles.size(); ++i) {
      ThePEG::tPPtr particle = particles[i];
      if (!particle) continue;
      
      // Get particle properties
      int pdgCode = particle->id();
      int status = getFinalStateStatus(particle);
      
      // Get 4-momentum
      ThePEG::LorentzMomentum momentum = particle->momentum();
      double px = momentum.x() / ThePEG::GeV;  // Convert to GeV
      double py = momentum.y() / ThePEG::GeV;
      double pz = momentum.z() / ThePEG::GeV;
      double e = momentum.e() / ThePEG::GeV;
      
      // Get production vertex
      const ThePEG::LorentzPoint &vertex = particle->vertex();
      double vx = vertex.x() / ThePEG::mm;  // Convert to mm
      double vy = vertex.y() / ThePEG::mm;
      double vz = vertex.z() / ThePEG::mm;
      double vt = vertex.t() / ThePEG::mm;  // Convert to mm/c
      
      // Create TParticle
      TParticle tparticle(
        pdgCode, status,
        -1, -1, -1, -1,  // mother and daughter indices (to be set properly)
        px, py, pz, e,
        vx, vy, vz, vt
      );
      tparticle.SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(tparticle.GetStatusCode(), 0).fullEncoding);
      tparticle.SetBit(ParticleStatus::kToBeDone, //
                       o2::mcgenstatus::getHepMCStatusCode(tparticle.GetStatusCode()) == 1);

      hParticles.push_back(tparticle);
    }
    
    LOG(debug) << "Converted " << hParticles.size() << " particles from HERWIG7 event";
  }
  
  /// Determine final state status for particle
  int getFinalStateStatus(ThePEG::tPPtr particle)
  {
    // In HERWIG/ThePEG, check if particle is stable
    if (particle->children().empty()) {
      return 1;  // Final state particle
    } else {
      return 2;  // Intermediate particle
    }
  }
};

} // namespace eventgen
} // namespace o2

/// HERWIG7 generator from .in/.run file. If seed is -1, a random seed is chosen
/// based on the SimConfig starting seed.
FairGenerator* generateHerwig7(const std::string inputFile = "LHC.in", int seed = -1)
{
  auto filePath = gSystem->ExpandPathName(inputFile.c_str());
  auto generator = new o2::eventgen::GeneratorHerwig(filePath, seed);
  return generator;
}