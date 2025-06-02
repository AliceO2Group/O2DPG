R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
///#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "Generators/GeneratorPythia8Param.h"
#include "CommonUtils/FileSystemUtils.h"
#include <thread>
// Pythia8 generator with POWHEG
//
// Author: Marco Giacalone (marco.giacalone@cern.ch)

// o2-sim-dpl-eventgen --nEvents 10 --generator external\
   --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGGAJE/external/\
   generator/generator_pythia8_powheg.C;GeneratorExternal.funcName=\
   getGeneratorJEPythia8POWHEG(\"powheg.input\",\"${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGGAJE/pythia8/generator/pythia8_powheg.cfg\")"
// or with iniFile
// o2-sim -g external --noGeant -n 2 -j 8 --configFile $O2DPG_MC_CONFIG_ROOT/MC/config/PWGGAJE/ini/GeneratorPythia8POWHEG_beauty.ini

namespace o2
{
namespace eventgen
{

using namespace Pythia8;

// Pythia8 generator using POWHEG data that are generated partially during the initialization
// of the external generator and then during the generateEvent when mNMaxPerJob is reached. The first time
// all the configuration files are created so that the other jobs can be run much faster (and in parallel in the future)
// The POWHEG configuration file is copied to the current directory with the right name and the POWHEG events are generated
// using the executable specified via the type parameter, namely:
//    0: pwhg_main_hvq
//    1: pwhg_main_W
//    2: pwhg_main_Z
//    3: pwhg_main_dijet
//    4: pwhg_main_directphoton
class GeneratorJEPythia8POWHEG : public o2::eventgen::GeneratorPythia8
{
public:
  /// default constructor
  GeneratorJEPythia8POWHEG(std::string confpath = "pwgpath", short int type = 0, int maxEventsPerJob = 50)
  {
    // Assign events to generate with POWHEG
    unsigned int nPowhegEvents = getTotalNEvents();
    if (nPowhegEvents == 0) {
      LOG(fatal) << "Number of events not set or set to 0.";
      exit(1);
    }
    // POWHEG has an integer limit hardcoded for the nEvents, but
    // with the multiple jobs setup this is not an issue (an error will automatically be thrown)
    mNMaxPerJob = maxEventsPerJob;
    if (mNMaxPerJob < 1) {
      LOG(fatal) << "Number of events per job are set to 0 or lower.";
      exit(1);
    }
    mNFiles = nPowhegEvents / mNMaxPerJob;
    if (nPowhegEvents % mNMaxPerJob != 0)
    {
      mNFiles++;
    }
    gRandom->SetSeed(0);
    if(!confMaker(confpath))
    {
      LOG(fatal) << "Failed to edit POWHEG configuration file";
      exit(1);
    }
    mPowhegConf = confpath;
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
      mExePOW = mPowhegGen[type] + " &";
      system(mExePOW.c_str());
    }
  };

  Bool_t confMaker(std::string confpath = "pwgpath", bool parallel = false)
  {
    // Check if file exist and is not empty
    if (std::filesystem::exists(confpath) && std::filesystem::file_size(confpath) > 0) {
      // Copy the file to the current directory
      ifstream src(confpath);
      ofstream dst("powheg.input");
      int seed = gRandom->Integer(900000000);
      bool isseed = false;
      bool isnumevts = false;
      if (mCurrFile == mNFiles - 1 && getTotalNEvents() % mNMaxPerJob != 0) {
        mNMaxPerJob = getTotalNEvents() % mNMaxPerJob;
      }
      std::string line;
      while (std::getline(src, line))
      {
        if (line.find("iseed") != std::string::npos)
        {
          // Set the seed to the random number
          line = "iseed " + std::to_string(seed);
          isseed = true;
        }
        if (line.find("numevts") != std::string::npos)
        {
          // Set the number of events to the number of events defined in the configuration
          line = "numevts " + std::to_string(mNMaxPerJob);
          // replace it in the file
          isnumevts = true;
        }
        dst << line << std::endl;
      }
      if (!isseed)
      {
        dst << "iseed " << seed << std::endl;
      }
      if (!isnumevts)
      {
        dst << "numevts " << mNMaxPerJob << std::endl;
      }
      if (parallel)
      {
        dst << "manyseeds 1" << std::endl; // Enables the usage of pwgseeds.dat file to set the seed in parallel mode
        dst << "parallelstage 4" << std::endl; // Allows event generation based on pre-generated POWHEG configuration files (needed for certain configurations)
      }
      src.close();
      dst.close();
    } else {
      LOG(fatal) << "POWHEG configuration file not found or empty" << std::endl;
      return false;
    }
    return true;
  }

  Bool_t startPOW() 
  {
    if(mCurrFile == 1) {
      if (!confMaker(mPowhegConf, true)) {
        LOG(fatal) << "Failed to edit POWHEG configuration with parallelisation";
        return false;
      }
    }
    LOG(info) << "Starting POWHEG job " << mCurrFile+1 << " of " << mNFiles;
    system(("echo " + std::to_string(mCurrFile - 1) + " | " + mExePOW).c_str());
    return true;
  }

  Bool_t checkEOF() {
    // Check if the POWHEG generation is done
    int result = system(("grep -q /LesHouchesEvents " + mLHEFoutput).c_str());
    if (result == 0)
    {
      return true;
    } else {
      return false;
    }
  }

  Bool_t POWchecker() {
    // Check if the POWHEG events file exists
    LOG(info) << "Waiting for " << mLHEFoutput << " to exist";
    while (!std::filesystem::exists(mLHEFoutput.c_str()))
    {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    LOG(info) << "POWHEG events file for job " << mCurrFile << " found";
    while (!checkEOF())
    {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    LOG(info) << "POWHEG events ready";
    return true;
  }

  // Check for the POWHEG events file existance
  Bool_t Init() override
  {
    // Check if the POWHEG events file exists
    if(POWchecker()) {
      return GeneratorPythia8::Init();
    } else {
      return false;
    }
  };

  // Set Generator ReadEvent to wait for the POWHEG events
  Bool_t generateEvent() override
  {
    /** Reinitialise when EOF is reached **/
    if (mPythia.info.atEndOfFile())
    {
      if(mCurrFile == 0)
      {
        mPythia.readString("Beams:newLHEFsameInit = on");
        // Create pwgseeds.dat file with a random seed for each line
        std::ofstream seedfile("pwgseeds.dat");
        for (int i = 0; i < mNFiles - 1; i++)
        {
          seedfile << gRandom->Integer(900000000) << std::endl;
        }
        seedfile.close();
      }
      mCurrFile++;
      mLHEFoutput = Form("pwgevents-%04d.lhe", mCurrFile - 1);
      mPythia.readString(Form("Beams:LHEF = %s", mLHEFoutput.c_str()));
      if(!startPOW())
      { 
        return false;
      }
      if (POWchecker()) {
        // If Pythia fails to initialize, exit with error.
        if (!mPythia.init())
        {
          LOG(fatal) << "Failed to init \'Pythia8\': init returned with error";
          return false;
        }
      }
    }
    return GeneratorPythia8::generateEvent();
  };

private:
  const std::vector<std::string> mPowhegGen = {"pwhg_main_hvq", "pwhg_main_W", "pwhg_main_Z", "pwhg_main_dijet", "pwhg_main_directphoton"}; // POWHEG executables
  short int mNFiles = 1;
  short int mCurrFile = 0;
  std::string mExePOW = "";
  std::string mPowhegConf = "";
  std::string mLHEFoutput = "pwgevents.lhe";
  int mNMaxPerJob = 50;
};

} // namespace eventgen
} // namespace o2

/** generator instance and settings **/

FairGenerator *getGeneratorJEPythia8POWHEG(std::string powhegconf = "pwgpath", std::string pythia8conf = "", short int type = 0, int maxEventsPerJob = 1e4)
{
  using namespace o2::eventgen;
  // Expand paths for the POWHEG configuration file
  powhegconf = o2::utils::expandShellVarsInFileName(powhegconf);
  LOG(info) << "Using POWHEG configuration file: " << powhegconf;
  auto myGen = new GeneratorJEPythia8POWHEG(powhegconf, type, maxEventsPerJob);
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
