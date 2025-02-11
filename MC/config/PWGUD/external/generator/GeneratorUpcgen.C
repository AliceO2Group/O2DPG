R__LOAD_LIBRARY(libUpcgenlib.so)
R__ADD_INCLUDE_PATH($Upcgen_ROOT/include)

#include "UpcGenerator.h"

// usage: o2-sim -n 100 -g external --configKeyValues 'GeneratorExternal.fileName=GeneratorUpcgen.C;GeneratorExternal.funcName=GeneratorUpcgen("kDiTau", ".", 5360.)'

namespace o2 {
namespace eventgen {
class GeneratorUPCgen_class : public Generator {
public:
  GeneratorUPCgen_class() { mUPCgen = new UpcGenerator(); };
  ~GeneratorUPCgen_class() = default;
  void selectConfiguration(std::string val) { mSelectedConfiguration = val; };
  void setLumiFileDirectory(std::string lumiFileDirectory) {
    mUPCgen->setLumiFileDirectory(lumiFileDirectory);
  };
  void setCollisionSystem(float energyCM, int beamZ, int beamA) {
    eCM = energyCM;
    projZ = beamZ;
    projA = beamA;
  };
  void setSeed(int seed) { mUPCgen->setSeed(seed); }

  // predefined generator configurations
  const static int nProcess = 5;
  const static int nElements = 9;
  const struct UpcgenConfig {
    std::string pnames[nElements]{"PROC_ID",   "LEP_A",      "ALP_MASS",
                                  "ALP_WIDTH", "PT_MIN",     "ETA_MIN",
                                  "ETA_MAX",   "FLUX_POINT", "BREAKUP_MODE"};
    const struct definitions {
      const char *name;
      std::string elements[nElements];
    } sets[nProcess] = {
        {"kDiElectron",
         {"11", "0.0", "0.0", "0.0", "0.0", "-1.0", "1.0", "1", "1"}},
        {"kDiMuon",
         {"13", "0.0", "0.0", "0.0", "0.0", "-1.0", "1.0", "1", "1"}},
        {"kDiTau", {"15", "0.0", "0.0", "0.0", "0.0", "-1.0", "1.0", "1", "1"}},
        {"kLightByLight",
         {"22", "0.0", "0.0", "0.0", "0.0", "-1.0", "1.0", "1", "1"}},
        {"kAxionLike",
         {"51", "0.0", "0.0", "0.0", "0.0", "-1.0", "1.0", "1", "1"}}};
  } upcgenConfig;

  bool Config() {
    // select a specific set of parameters
    int idx = -1;
    for (int i = 0; i < nProcess; ++i) {
      if (mSelectedConfiguration.compare(upcgenConfig.sets[i].name) == 0) {
        idx = i;
        break;
      }
    }

    if (idx == -1) {
      std::cout << "UPCGEN process " << mSelectedConfiguration
                << " is not supported" << std::endl;
      return false;
    }

    // new generator
    mUPCgen->setDebugLevel(0);
    mUPCgen->setNumThreads(1);

    // update generator parameters - configure
    // independent of process
    mUPCgen->setParameterValue("DO_PT_CUT", "0");
    mUPCgen->setParameterValue("DO_ETA_CUT", "0");
    mUPCgen->setParameterValue("FLUX_POINT", "0");
    mUPCgen->setParameterValue("USE_ROOT_OUTPUT", "0");
    mUPCgen->setParameterValue("USE_HEPMC_OUTPUT", "0");

    // process specific
    for (int i = 0; i < nElements; ++i) {
      mUPCgen->setParameterValue(upcgenConfig.pnames[i],
                                 upcgenConfig.sets[idx].elements[i]);
    }

    return true;
  }

  bool Init() override {
    Generator::Init();

    // initialize the generator
    mUPCgen->init();

    return true;
  };

  bool generateEvent() override {
    if (!mUPCgen) {
      std::cout << "GenerateEvent: upcgen class/object not properly constructed"
                << std::endl;
      return false;
    }

    // generate a new event
    vector<int> pdgs;
    vector<int> statuses;
    vector<int> mothers;
    vector<TLorentzVector> particles;
    // events can be rejected due to applied cuts
    bool goon = true;
    while (goon) {
      auto stat = mUPCgen->generateEvent(pdgs, statuses, mothers, particles);
      if (stat == 0) {
        nRejected++;
      } else {
        nAccepted++;
        goon = false;
      }
    }

    return true;
  };

  bool importParticles() override {
    std::cout << "\n";
    auto upcgenParticles = mUPCgen->getParticles();
    for (auto part : upcgenParticles) {
      TParticle particle(part.GetPdgCode(), 1, part.GetFirstMother(), -1,
                         part.GetFirstDaughter(), part.GetLastDaughter(),
                         part.Px(), part.Py(), part.Pz(), part.Energy(), 0., 0.,
                         0., 0.);
      mParticles.push_back(particle);
      o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(
          mParticles.back(), true);
    }
    return true;
  };

  long int acceptedEvents() { return nAccepted; }
  long int rejectedEvents() { return nRejected; }
  double fiducialXSection() {
    return mUPCgen->totNuclX() * nAccepted / (nAccepted + nRejected);
  }

private:
  UpcGenerator *mUPCgen = 0x0;
  std::string mSelectedConfiguration = "";

  // keep track of the rejected and accepted events
  long int nAccepted{0};
  long int nRejected{0};

  float eCM = 5020;
  int projZ = 82;
  int projA = 208;
};

} // namespace eventgen
} // namespace o2

FairGenerator *GeneratorUpcgen(std::string configuration = "kDiTau",
                               std::string lumiFileDirectory = ".",
                               float energyCM = 5020., int beamZ = 82,
                               int beamA = 208) {
  // create generator
  auto gen = new o2::eventgen::GeneratorUPCgen_class();

  // set generator parameters
  gen->selectConfiguration(configuration);
  gen->setLumiFileDirectory(lumiFileDirectory);
  gen->setCollisionSystem(energyCM, beamZ, beamA);

  // configure the generator
  cout << "Upcgen is initialized ...";
  gen->Config();
  cout << " config done ...";
  gen->Init();
  cout << " init done!\n";

  return gen;
}
