// Set include paths for ThePEG headers
R__ADD_INCLUDE_PATH($THEPEG_ROOT/include/)
R__ADD_INCLUDE_PATH($THEPEG_ROOT/../../GSL/latest/include/)
R__ADD_INCLUDE_PATH($HEPMC3_ROOT/include/)
R__ADD_INCLUDE_PATH($HERWIG_ROOT/include/)
#define SKIP_HEPMC_CONVERSION 1
#define HAVE_HEPMC3 1
#define ThePEG_DEBUG_LEVEL 1

// O2DPG and ROOT includes
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "fairlogger/Logger.h"
#include "TRandom3.h"
#include "TParticle.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "TLorentzVector.h"
#include "TMath.h"
#include <fstream>
#include <iostream>
#include <vector>
#include <string>
#include <memory>

// Undefine conflicting macros before including ThePEG headers
#ifdef B0
#undef B0
#endif
#ifdef B50
#undef B50
#endif
#ifdef B75
#undef B75
#endif
#ifdef B110
#undef B110
#endif
#ifdef B134
#undef B134
#endif
#ifdef B150
#undef B150
#endif
#ifdef B200
#undef B200
#endif
#ifdef B300
#undef B300
#endif
#ifdef B600
#undef B600
#endif
#ifdef B1200
#undef B1200
#endif
#ifdef B1800
#undef B1800
#endif
#ifdef B2400
#undef B2400
#endif
#ifdef B4800
#undef B4800
#endif
#ifdef B9600
#undef B9600
#endif
#ifdef B19200
#undef B19200
#endif
#ifdef B38400
#undef B38400
#endif

// ThePEG and Herwig includes
#include "ThePEG/Repository/EventGenerator.h"
#include "ThePEG/EventRecord/Event.h"
#include "ThePEG/EventRecord/Particle.h"
#include "ThePEG/EventRecord/Step.h"
#include "ThePEG/Config/ThePEG.h"
#include "ThePEG/PDT/ParticleData.h"
#include "ThePEG/Vectors/HepMCConverter.h"
#include "ThePEG/Repository/Repository.h"
#include "ThePEG/Repository/BaseRepository.h"
#include "ThePEG/Utilities/DynamicLoader.h"
#include "ThePEG/Persistency/PersistentIStream.h"

// Herwig specific includes
#include "Herwig/API/HerwigAPI.h"
#include "Herwig/API/HerwigUI.h"

// Subclass of HerwigUI to provide minimal implementation for our use case
class SimpleHerwigUI : public Herwig::HerwigUI
{
public:
  SimpleHerwigUI(const std::string &inFile,
                 Herwig::RunMode::Mode mode = Herwig::RunMode::READ)
      : m_inFile(inFile), m_mode(mode),
        m_in(inFile), m_out(std::cout), m_err(std::cerr)
  {
    if (!m_in)
      throw std::runtime_error("Cannot open Herwig input file: " + inFile);
    Dirs.reserve(5);
    std::string hDir = std::getenv("HERWIG_ROOT");
    if (!hDir.empty())
      Dirs.push_back(hDir + "/share/Herwig");
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

  long N() const override { return 10; } // number of events
  int seed() const override { return 1234; }
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
};

namespace o2
{
namespace eventgen
{

/// HERWIG7 event generator using ThePEG interface
/// Author: Marco Giacalone (marco.giacalone@cern.ch)
/// Based on the O2DPG external generator patterns
class GeneratorHerwig : public Generator
{
public:
  /// Default constructor
  GeneratorHerwig(const std::string& configFile = "LHC.in")
    : mConfigFile(configFile)
    , mEventGenerator(nullptr)
  {
    LOG(info) << "HERWIG7 Generator initialized";
    LOG(info) << "Config file: " << mConfigFile;
    std::string extension = mConfigFile.substr(mConfigFile.find_last_of("."));
    if( extension == ".in" ) {
      mIsInputFile = true;
      LOG(info) << "Using input file for configuration";
    } else if(std::find(mConfigFile.end()-4, mConfigFile.end(), '.run') != mConfigFile.end()) {
      mIsInputFile = false;
      LOG(info) << "Using run file for configuration";
    } else {
      LOG(fatal) << "No file extension found in config file: " << mConfigFile;
      exit(1);
    }
  }

  /// Destructor
  ~GeneratorHerwig(){
    delete mEventGenerator;
  };

  /// Initialize the generator
  Bool_t Init() override
  {
    LOG(info) << "Initializing HERWIG7 Generator";
    
    try {
      if (mIsInputFile) {
        // Process .in file
        return initFromInputFile();
      } else {
        // Process .run file directly
        return initFromRunFile();
      }
      
    } catch (const std::exception& e) {
      LOG(fatal) << "Exception during HERWIG7 initialization: " << e.what();
      return kFALSE;
    }
  }

  /// Generate event
  Bool_t generateEvent() override
  {
    if (!mEventGenerator) {
      LOG(error) << "Event generator not initialized";
      return kFALSE;
    }
    try {
      // Clear previous event particles
      hParticles.clear();
      
      // Generate the event
      ThePEG::EventPtr event = mEventGenerator->shoot();
      
      if (!event) {
        LOG(error) << "Failed to generate event";
        return kFALSE;
      }
      
      // Convert ThePEG event to TParticle format
      convertEvent(event);
      LOG(debug) << "Herwig7 generated " << hParticles.size();

      return kTRUE;
      
    } catch (const std::exception& e) {
      LOG(error) << "Exception during event generation: " << e.what();
      return kFALSE;
    }
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
  Bool_t mIsInputFile = false;                               ///< True for .in files, false for .run files
  ThePEG::EGPtr mEventGenerator;                     ///< ThePEG event generator
  std::vector<TParticle> hParticles;                 ///< Generated Herwig particles

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
    
    try {
      using namespace ThePEG;
      SimpleHerwigUI ui(mConfigFile, Herwig::RunMode::READ);

      Herwig::API::read(ui);
      printHerwigSearchPaths();
      std::string runFile = mConfigFile;
      size_t pos = runFile.find_last_of('.');
      runFile.replace(pos, 4, ".run");
      mConfigFile = runFile;
      LOG(info) << "Generated run file: " << runFile;
      auto res = initFromRunFile();
      if (!res) {
        LOG(error) << "Failed to initialize from generated run file";
        return kFALSE;
      }  
      return kTRUE;
    }
    catch (const std::exception &e)
    {
      std::cerr << "Exception: " << e.what() << std::endl;
      return kFALSE;
    }
  }
  
  /// Initialize from .run file
  Bool_t initFromRunFile()
  {
    LOG(info) << "Initializing from .run file: " << mConfigFile;
    
    try {
      using namespace ThePEG;

      if (!std::ifstream(mConfigFile))
      {
        LOG(info) << "Run file does not exist: " << mConfigFile;
        return kFALSE;
      }
      SimpleHerwigUI runui(mConfigFile, Herwig::RunMode::RUN);
      // Prepare the generator
      mEventGenerator = Herwig::API::prepareRun(runui);
      if (!mEventGenerator)
      {
        std::cerr << "Error: prepareRun() returned null." << std::endl;
        return kFALSE;
      }

      mEventGenerator->initialize();
      std::cout << "Herwig generator initialized successfully." << std::endl;
      return kTRUE;
    }
    catch (const std::exception &ex) {
      LOG(error) << "Standard exception: " << ex.what();
      return kFALSE;
    }
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

/// Factory function to create HERWIG7 generator from .in file
/// @param inputFile HERWIG input/run file (e.g., "LHC.in"/"LHC.run")
FairGenerator* generateHerwig7(const std::string& inputFile = "LHC.in")
{
  auto generator = new o2::eventgen::GeneratorHerwig(inputFile);
  return generator;
}