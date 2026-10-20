#include <cmath>
#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
#include <fairlogger/Logger.h>
#include "TRandom.h"
#include "TParticle.h"
#include "TString.h"
#include "Generators/Generator.h"
#include "Generators/GeneratorFileOrCmd.h"
#include "CommonUtils/FileSystemUtils.h"
#include "SimulationDataFormat/MCEventHeader.h"
#include "SimulationDataFormat/MCUtils.h"

/// AMPT adapted external generator
///
/// @author Marco Giacalone (marco.giacalone@cern.ch)
/// @date 09/26
// The AMPT output (ana/ampt.dat) is converted directly into TParticles, without any HepMC step, as done in the past.
// Two modes are available:
//  - "run"  : the path is an AMPT input card (input.ampt). AMPT is started in the background in a dedicated
//             working directory, where ana/ampt.dat is a named pipe, so events are streamed to O2 as soon as
//             they are produced. NEVNT and the random seeds of the card are replaced by the macro.
//  - "file" : the path is an existing ampt.dat file, whose events are read sequentially.
// All the particles are transported, including the spectator nucleons (needed by the ZDC).
// This could be changed in case it's actually not needed. To verify

// o2-sim -g external --noGeant -n 2 --configFile ${O2DPG_MC_CONFIG_ROOT}/MC/config/common/ini/GeneratorAMPTPbPb536TeV.ini
// or, reading an existing AMPT output
// o2-sim -g external --noGeant -n 2 --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/common/external/generator/generator_AMPT.C;GeneratorExternal.funcName=generateAMPT(\"/path/to/ampt.dat\",\"file\")"

namespace o2
{
namespace eventgen
{

// Inheriting from GeneratorFileOrCmd as well to use the pipe mechanism
class GeneratorAMPT : public Generator, public GeneratorFileOrCmd
{
 public:
  GeneratorAMPT(const std::string& path, bool runAMPT, unsigned int nEvents) : mPath(path)
  {
    setNEvents(nEvents);
    if (runAMPT) {
      // AMPT does NSEED = 2 * NSEED + 1 internally, hence the seed must stay below 2^30
      setSeed(gRandom->Integer(536870911) + 1);
      mWorkDir = Form("ampt_%lu", mSeed);
      // AMPT always reads a number from stdin (used as seed only when ihjsed = 11). If AMPT fails,
      // the pipe is opened and closed by the shell, so the reader gets an end of file instead of hanging.
      // The timeout avoids a shell blocked forever on the pipe when the reader is gone (this was seen if o2-sim crashed mid-run for some reason)
      setCmd("cd " + mWorkDir + " && { echo 0 | \"$AMPT_ROOT/bin/ampt\" > ampt.log 2>&1 || timeout 60 sh -c ': > ana/ampt.dat'; }");
    }
  }
  ~GeneratorAMPT() override
  {
    stop();
    if (not mCmd.empty()) {
      removeTemp();
    }
  }

  Bool_t Init() override
  {
    if (mCmd.empty()) {
      mInput.open(mPath);
    } else {
      if (!getenv("AMPT_ROOT")) {
        LOG(fatal) << "AMPT_ROOT is not set, load the AMPT package";
        return false;
      }
      if (!prepareWorkDir() || !makeFifo() || !executeCmdLine(mCmd)) {
        return false;
      }
      LOG(info) << "AMPT started in " << mWorkDir << " with seed " << mSeed << " for " << mNEvents << " events";
      mInput.open(mTemporary); // blocks until AMPT opens the pipe for writing
    }
    if (!mInput.is_open()) {
      LOG(fatal) << "Cannot open AMPT output " << (mCmd.empty() ? mPath : mTemporary);
      return false;
    }
    return Generator::Init();
  }

  // Reads the next event from ampt.dat: one header line with 11 fields followed by
  // exactly nParticles lines with 9 fields (pdg px py pz m x y z t)
  Bool_t generateEvent() override
  {
    std::string line;
    if (!nextLine(line)) {
      LOG(fatal) << "AMPT output ended after " << mEventCounter << " events (" << mNEvents << " requested)"
                 << (mCmd.empty() ? "" : ", see " + mWorkDir + "/ampt.log");
      return false;
    }
    std::istringstream header(line);
    header >> mHeader.event >> mHeader.run >> mHeader.nParticles >> mHeader.b >> mHeader.nPartProj >> mHeader.nPartTarg >> mHeader.nElP >> mHeader.nInP >> mHeader.nElT >> mHeader.nInT >> mHeader.phiRP;
    if (header.fail() || mHeader.nParticles < 0) {
      LOG(fatal) << "Malformed AMPT event header: " << line;
      return false;
    }
    mTracks.clear();
    mTracks.reserve(mHeader.nParticles);
    for (int i = 0; i < mHeader.nParticles; ++i) {
      AMPTTrack t;
      if (!nextLine(line)) {
        LOG(fatal) << "AMPT event " << mHeader.event << " is truncated: " << i << " out of " << mHeader.nParticles << " particles";
        return false;
      }
      std::istringstream particle(line);
      particle >> t.pdg >> t.px >> t.py >> t.pz >> t.m;
      if (particle.fail()) {
        LOG(fatal) << "Malformed AMPT particle line: " << line;
        return false;
      }
      mTracks.push_back(t);
    }
    mEventCounter++;
    LOG(info) << "AMPT event " << mEventCounter << "/" << mNEvents << ": " << mHeader.nParticles << " particles, b = " << mHeader.b << " fm";
    return true;
  }

  Bool_t importParticles() override
  {
    mParticles.clear();
    for (const auto& t : mTracks) {
      // AMPT uses PDG codes, apart from (anti)deuterons
      int pdg = std::abs(t.pdg) == 42 ? (t.pdg > 0 ? 1 : -1) * 1000010020 : t.pdg;
      double e = std::sqrt(t.px * t.px + t.py * t.py + t.pz * t.pz + t.m * t.m);
      // Freeze-out coordinates are in fm, hence negligible: particles are produced at the interaction vertex
      TParticle particle(pdg, 1, -1, -1, -1, -1, t.px, t.py, t.pz, e, 0., 0., 0., 0.);
      o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(particle, true);
      mParticles.push_back(particle);
    }
    return true;
  }

  void updateHeader(o2::dataformats::MCEventHeader* eventHeader) override
  {
    using Key = o2::dataformats::MCInfoKeys;
    eventHeader->putInfo<std::string>(Key::generator, "ampt");
    eventHeader->SetB(mHeader.b);
    eventHeader->putInfo<float>(Key::impactParameter, mHeader.b);
    eventHeader->putInfo<int>(Key::nPart, mHeader.nPartProj + mHeader.nPartTarg);
    eventHeader->putInfo<int>(Key::nPartProjectile, mHeader.nPartProj);
    eventHeader->putInfo<int>(Key::nPartTarget, mHeader.nPartTarg);
    eventHeader->putInfo<double>(Key::planeAngle, mHeader.phiRP);
    // Participant nucleons from elastic and inelastic collisions in projectile and target
    eventHeader->putInfo<int>("ampt_NELP", mHeader.nElP);
    eventHeader->putInfo<int>("ampt_NINP", mHeader.nInP);
    eventHeader->putInfo<int>("ampt_NELT", mHeader.nElT);
    eventHeader->putInfo<int>("ampt_NINTHJ", mHeader.nInT);
  }

  void stop() override
  {
    mInput.close();
    if (not mCmd.empty()) {
      // AMPT exits by itself once all the events are written, otherwise it is terminated
      terminateCmd(sStopGraceMillis);
    }
  }

 private:
  struct AMPTHeader {
    int event = 0, run = 0, nParticles = 0;
    double b = 0.;
    int nPartProj = 0, nPartTarg = 0, nElP = 0, nInP = 0, nElT = 0, nInT = 0;
    double phiRP = 0.;
  };
  struct AMPTTrack {
    int pdg = 0;
    double px = 0., py = 0., pz = 0., m = 0.;
  };

  // Creates the working directory with the edited card. ana/ampt.dat becomes the named pipe, while
  // the outputs growing with the number of events and not needed here points to /dev/null
  bool prepareWorkDir()
  {
    std::filesystem::create_directories(mWorkDir + "/ana");
    // AMPT reads the card sequentially, one value per line: lines are replaced by their position
    const std::map<int, std::string> replacements = {
      {9, std::to_string(mNEvents) + "\t\t! NEVNT (set by generator_AMPT.C)"},
      {28, "0\t\t! ihjsed (set by generator_AMPT.C)"},
      {29, std::to_string(mSeed) + "\t\t! random seed for HIJING (set by generator_AMPT.C)"},
      {30, std::to_string(gRandom->Integer(536870911) + 1) + "\t\t! random seed for parton cascade (set by generator_AMPT.C)"}};
    std::ifstream src(mPath);
    std::ofstream dst(mWorkDir + "/input.ampt");
    std::string line;
    for (int lineNumber = 1; std::getline(src, line); ++lineNumber) {
      auto replacement = replacements.find(lineNumber);
      dst << (replacement != replacements.end() ? replacement->second : line) << "\n";
    }
    for (const auto& file : {"zpc.dat", "npart-xy.dat"}) {
      std::filesystem::remove(mWorkDir + "/ana/" + file);
      std::filesystem::create_symlink("/dev/null", mWorkDir + "/ana/" + file);
    }
    // Named pipe used by makeFifo and removed by removeTemp
    mTemporary = mWorkDir + "/ana/ampt.dat";
    mFileNames = {mTemporary};
    return true;
  }

  bool nextLine(std::string& line)
  {
    while (std::getline(mInput, line)) {
      if (line.find_first_not_of(" \t\r") != std::string::npos) {
        return true;
      }
    }
    return false;
  }

  std::string mPath;
  std::string mWorkDir;
  std::ifstream mInput;
  unsigned int mEventCounter = 0;
  AMPTHeader mHeader;
  std::vector<AMPTTrack> mTracks;
};

} // namespace eventgen
} // namespace o2

// path : AMPT input card (mode "run") or existing ampt.dat file (mode "file")
// maxEvents : number of events for AMPT when the total number of events is not known (e.g. hyperloop)
FairGenerator* generateAMPT(std::string path, std::string mode = "run", int maxEvents = 2147483647)
{
  path = o2::utils::expandShellVarsInFileName(path);
  if (mode != "run" && mode != "file") {
    LOG(fatal) << "Unknown AMPT generator mode " << mode << ", use \"run\" or \"file\"";
    return nullptr;
  }
  if (!std::filesystem::exists(path)) {
    LOG(fatal) << "AMPT " << (mode == "run" ? "input card " : "output file ") << path << " does not exist";
    return nullptr;
  }
  unsigned int nEvents = o2::eventgen::Generator::getTotalNEvents();
  if (nEvents == 0) {
    nEvents = maxEvents;
  }
  LOG(info) << "AMPT generator in \"" << mode << "\" mode using " << path;
  return new o2::eventgen::GeneratorAMPT(path, mode == "run", nEvents);
}
