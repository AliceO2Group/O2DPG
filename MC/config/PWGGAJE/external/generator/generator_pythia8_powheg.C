R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
///#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "Generators/GeneratorPythia8Param.h"
#include "CommonUtils/FileSystemUtils.h"
// Pythia8 generator with POWHEG
//
// Author: Marco Giacalone (marco.giacalone@cern.ch)

// o2-sim-dpl-eventgen --nEvents 10 --generator external\
   --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGGAJE/external/\
   generator/generator_pythia8_powheg.C;GeneratorExternal.funcName=\
   getGeneratorJEPythia8POWHEG(\"powheg.input\",\"${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGGAJE/pythia8/generator/pythia8_powheg.cfg\")"
// or with iniFile
// o2-sim -g external --noGeant -n 2 -j 8 --configFile $O2DPG_MC_CONFIG_ROOT/MC/config/PWGGAJE/ini/GeneratorPythia8POWHEG.ini

namespace o2
{
namespace eventgen
{

using namespace Pythia8;

// Pythia8 generator using POWHEG data that are generated during the initialization
// of the external generator. The POWHEG configuration file is copied to the current
// directory with the right name and the POWHEG events are generated using the executable
// specified via the type parameter, namely:
//    0: pwhg_main_hvq
//    1: pwhg_main_W
//    2: pwhg_main_Z
//    3: pwhg_main_dijet
//    4: pwhg_main_directphoton
class GeneratorJEPythia8POWHEG : public o2::eventgen::GeneratorPythia8
{
public:
  /// default constructor
  GeneratorJEPythia8POWHEG(std::string confpath = "pwgpath", short int type = 0)
  {
    // Assign events to generate with POWHEG
    unsigned int nPowhegEvents = getTotalNEvents();
    if (nPowhegEvents == 0) {
      LOG(fatal) << "Number of events not set or set to 0.";
      exit(1);
    }
    // Check on nEvents to generate with POWHEG
    // due to integer limit hardcoded in the generator
    if (nPowhegEvents > std::numeric_limits<int>::max()) {
      LOG(fatal) << "Number of events for POWHEG exceeds the maximum allowed value";
      exit(1);
    }
    // Check if file exist and is not empty
    if (std::filesystem::exists(confpath) && std::filesystem::file_size(confpath) > 0) {
      // Copy the file to the current directory
      ifstream src(confpath);
      ofstream dst("powheg.input");
      gRandom->SetSeed(0);
      int seed = gRandom->Integer(900000000);
      bool isseed = false;
      bool isnumevts = false;
      std::string line;
      while (std::getline(src, line)) {
        if (line.find("iseed") != std::string::npos)
        {
          // Set the seed to the random number
          line = "iseed " + std::to_string(seed);
          isseed = true;
        }
        if (line.find("numevts") != std::string::npos)
        {
          // Set the number of events to the number of events defined in the configuration
          line = "numevts " + std::to_string(nPowhegEvents);
          // replace it in the file
          isnumevts = true;
        }
        dst << line << std::endl;
      }
      if (!isseed) {
        dst << "iseed " << seed << std::endl;
      }
      if (!isnumevts) {
        dst << "numevts " << nPowhegEvents << std::endl;
      }
      src.close();
      dst.close();
    } else {
      LOG(fatal) << "POWHEG configuration file not found or empty" << std::endl;
      exit(1);
    }
    // Get POWHEG executable to use
    if (type >= mPowhegGen.size()) {
      LOG(warn) << "Available POWHEG generators are:";
      for (int k = 0; k < mPowhegGen.size(); k++)
      {
        LOG(warn) << "\t" << k << ": " << mPowhegGen[k];
      }
      LOG(fatal) << "POWHEG generator type " << type << " not found";
      exit(1);
    } else {
      LOG(info) << "Running POWHEG using the " << mPowhegGen[type] << " executable";
      // Generate the POWHEG events
      system(mPowhegGen[type].c_str());
    }
  };

private:
  const std::vector<std::string> mPowhegGen = {"pwhg_main_hvq", "pwhg_main_W", "pwhg_main_Z", "pwhg_main_dijet", "pwhg_main_directphoton"}; // POWHEG executables
};

} // namespace eventgen
} // namespace o2

/** generator instance and settings **/

FairGenerator *getGeneratorJEPythia8POWHEG(std::string powhegconf = "pwgpath", std::string pythia8conf = "", short int type = 0)
{
  using namespace o2::eventgen;
  // Expand paths for the POWHEG configuration file
  powhegconf = o2::utils::expandShellVarsInFileName(powhegconf);
  LOG(info) << "Using POWHEG configuration file: " << powhegconf;
  auto myGen = new GeneratorJEPythia8POWHEG(powhegconf, type);
  if(GeneratorPythia8Param::Instance().config.empty() && pythia8conf.empty()) {
    LOG(fatal) << "No configuration provided for Pythia8";
  }
  else if (!pythia8conf.empty())
  {
    // Force the configuration for Pythia8 in case it is provided.
    // Useful for setting up the generator in the hybrid configuration
    // making it more versatile and not relying entirely on the parameters provided
    // by ini file or static parameters
    myGen->setConfig(pythia8conf);
  }
  return myGen;
}