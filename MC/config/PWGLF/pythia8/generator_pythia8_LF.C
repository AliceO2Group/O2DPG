///
/// \file   generator_pythia8_LF.C
/// \author Nicolò Jacazio nicolo.jacazio@cern.ch
/// \since  05/08/2022
/// \brief  Implementation of a gun generator for multiple particles, built on generator_pythia8_longlived.C
///         Needs PDG, Number of injected, minimum and maximum pT. These can be provided in three ways, bundeling variables, particles or from input file
///         usage:
///               `o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_LF.C;GeneratorExternal.funcName=generateLF({1000010020, 1000010030}, {10, 10}, {0.5, 0.5}, {10, 10})'`
///               Here PDG, Number injected, pT limits are separated and matched by index
///         or:
///               `o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_LF.C;GeneratorExternal.funcName=generateLF({{1000010020, 10, 0.5, 10}, {1000010030, 10, 0.5, 10}})'`
///               Here PDG, Number injected, pT limits are separated are divided per particle
///         or:
///               `o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_LF.C;GeneratorExternal.funcName=generateLF("${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/nuclei.gun")'`
///               Here PDG, Number injected, pT limits are provided via an intermediate configuration file
///

#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "SimulationDataFormat/MCGenStatus.h"
#include "SimulationDataFormat/MCUtils.h"
#include "fairlogger/Logger.h"
#include "TSystem.h"
#include <fstream>
#include "Generators/GeneratorPythia8Param.h"
#include "Generators/DecayerPythia8Param.h"
#endif
#include <nlohmann/json.hpp>
#include "generator_pythia8_longlived.C"

using namespace Pythia8;
using namespace o2::mcgenstatus;

class GeneratorPythia8LF : public o2::eventgen::GeneratorPythia8
{
 public:
  /// Parametric constructor
  GeneratorPythia8LF(bool injOnePerEvent /*= true*/,
                     int gapBetweenInjection /*= 0*/,
                     bool useTrigger /*= false*/,
                     std::string pythiaCfgMb /*= "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/pythia8_inel_minbias.cfg"*/,
                     std::string pythiaCfgSignal /*= "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/pythia8_inel_signal.cfg"*/) : GeneratorPythia8{},
                                                                                                                          mOneInjectionPerEvent{injOnePerEvent},
                                                                                                                          mGapBetweenInjection{gapBetweenInjection},
                                                                                                                          mUseTriggering{useTrigger}
  {
    LOG(info) << "GeneratorPythia8LF constructor";
    LOG(info) << "++ mOneInjectionPerEvent: " << mOneInjectionPerEvent;
    LOG(info) << "++ mGapBetweenInjection: " << mGapBetweenInjection;
    LOG(info) << "++ mUseTriggering: " << mUseTriggering;
    LOG(info) << "++ pythiaCfgMb: " << pythiaCfgMb;
    LOG(info) << "++ pythiaCfgSignal: " << pythiaCfgSignal;
    gRandom->SetSeed(0);
    if (useTrigger) {
      mPythia.readString("ProcessLevel:all off");
      if (pythiaCfgMb == "") { // If no configuration file is provided, use the one from the Pythia8Param
        auto& param = o2::eventgen::GeneratorPythia8Param::Instance();
        LOG(info) << "Instance LF \'Pythia8\' generator with following parameters for MB event";
        LOG(info) << param;
        pythiaCfgMb = param.config;
      }
      if (pythiaCfgSignal == "") { // If no configuration file is provided, use the one from the Pythia8Param
        auto& param = o2::eventgen::GeneratorPythia8Param::Instance();
        LOG(info) << "Instance LF \'Pythia8\' generator with following parameters for signal event";
        LOG(info) << param;
        pythiaCfgSignal = param.config;
      }
      pythiaCfgMb = gSystem->ExpandPathName(pythiaCfgMb.c_str());
      pythiaCfgSignal = gSystem->ExpandPathName(pythiaCfgSignal.c_str());
      LOG(info) << "  ++ Using trigger, initializing Pythia8 for trigger";
      if (!pythiaObjectMinimumBias.readFile(pythiaCfgMb)) {
        LOG(fatal) << "Could not pythiaObjectMinimumBias.readFile(\"" << pythiaCfgMb << "\")";
      }
      pythiaObjectMinimumBias.readString("Random:setSeed = on");
      pythiaObjectMinimumBias.readString("Random:seed =" + std::to_string(gRandom->Integer(900000000 - 2) + 1));

      if (!pythiaObjectMinimumBias.init()) {
        LOG(fatal) << "Could not pythiaObjectMinimumBias.init() from " << pythiaCfgMb;
      }
      if (!pythiaObjectSignal.readFile(pythiaCfgSignal)) {
        LOG(fatal) << "Could not pythiaObjectSignal.readFile(\"" << pythiaCfgSignal << "\")";
      }
      pythiaObjectSignal.readString("Random:setSeed = on");
      pythiaObjectSignal.readString("Random:seed =" + std::to_string(gRandom->Integer(900000000 - 2) + 1));
      if (!pythiaObjectSignal.init()) {
        LOG(fatal) << "Could not pythiaObjectSignal.init() from " << pythiaCfgSignal;
      }
    } else { // Using simple injection with internal decay (if needed). Fetching the parameters from the configuration file of the PythiaDecayer
      /** switch off process level **/
      mPythia.readString("ProcessLevel:all off");

      /** config **/
      auto& paramGen = o2::eventgen::GeneratorPythia8Param::Instance();
      if (!paramGen.config.empty()) {
        LOG(fatal) << "Configuration file provided for \'GeneratorPythia8\' should be empty for this injection scheme";
        return;
      }
      auto& param = o2::eventgen::DecayerPythia8Param::Instance();
      LOG(info) << "Init \'GeneratorPythia8LF\' with following parameters";
      LOG(info) << param;
      for (int i = 0; i < 8; ++i) {
        if (param.config[i].empty()) {
          continue;
        }
        std::string config = gSystem->ExpandPathName(param.config[i].c_str());
        LOG(info) << "GeneratorPythia8LF Reading configuration from file: " << config;
        if (!mPythia.readFile(config, true)) {
          LOG(fatal) << "Failed to init \'DecayerPythia8\': problems with configuration file "
                     << config;
          return;
        }
      }

      /** show changed particle data **/
      if (param.showChanged) {
        mPythia.readString(std::string("Init:showChangedParticleData on"));
      } else {
        mPythia.readString(std::string("Init:showChangedParticleData off"));
      }

      /** initialise **/
      if (!mPythia.init()) {
        LOG(fatal) << "Failed to init \'DecayerPythia8\': init returned with error";
        return;
      }
      if (pythiaCfgSignal != "") {
        LOG(fatal) << "Cannot use simple injection and have a configuration file. pythiaCfgSignal= `" << pythiaCfgSignal << "` must be empty";
      }
    }
  }

  ///  Destructor
  ~GeneratorPythia8LF() = default;

  //__________________________________________________________________
  Bool_t generateEvent() override
  {
    if (!mUseTriggering) { // If the triggering is used we handle the the gap when generating the signal
      if (mGapBetweenInjection > 0) {
        if (mGapBetweenInjection == 1 && mEventCounter % 2 == 0) {
          LOG(info) << "Skipping event " << mEventCounter;
          return true;
        } else if (mEventCounter % mGapBetweenInjection != 0) {
          LOG(info) << "Skipping event " << mEventCounter;
          return true;
        }
      }
    }
    LOG(info) << "generateEvent " << mEventCounter;
    mPythia.event.reset();

    mConfigToUse = mOneInjectionPerEvent ? static_cast<int>(gRandom->Uniform(0.f, getNGuns())) : -1;
    LOG(info) << "Using configuration " << mConfigToUse << " out of " << getNGuns() << ", of which " << mGunConfigs.size() << " are transport decayed and " << mGunConfigsGenDecayed.size() << " are generator decayed";

    bool injectedForThisEvent = false;
    int nConfig = mGunConfigs.size(); // We start counting from the configurations of the transport decayed particles
    for (const ConfigContainer& cfg : mGunConfigsGenDecayed) {
      nConfig++;
      if (mConfigToUse >= 0 && (nConfig - 1) != mConfigToUse) {
        continue;
      }
      LOG(info) << "Using config container ";
      cfg.print();
      if (mUseTriggering) {   // Do the triggering
        bool doSignal{mEventCounter % (mGapBetweenInjection + 1) == 0}; // Do signal or gap

        if (doSignal) {
          LOG(info) << "Generating triggered signal event for particle";
          cfg.print();
          bool satisfiesTrigger = false;
          int nTries = 0;
          while (!satisfiesTrigger) {
            if (!pythiaObjectSignal.next()) {
              continue;
            }
            // Check if triggered condition satisfied
            for (Long_t j = 0; j < pythiaObjectSignal.event.size(); j++) {
              const int& pypid = pythiaObjectSignal.event[j].id();
              const float& pyeta = pythiaObjectSignal.event[j].eta();
              const float& pypt = pythiaObjectSignal.event[j].pT();
              if (pypid == cfg.mPdg && cfg.mEtaMin < pyeta && pyeta < cfg.mEtaMax && pypt > cfg.mPtMin && pypt < cfg.mPtMax) {
                LOG(info) << "Found particle " << j << " " << pypid << " with eta " << pyeta << " and pT " << pypt << " in event " << mEventCounter << " after " << nTries << " tries";
                satisfiesTrigger = true;
                break;
              }
            }
            nTries++;
          }
          mPythia.event = pythiaObjectSignal.event;
        } else {
          LOG(info) << "Generating background event " << mEventCounter;
          // Generate minimum-bias event
          bool lGenerationOK = false;
          while (!lGenerationOK) {
            lGenerationOK = pythiaObjectMinimumBias.next();
          }
          mPythia.event = pythiaObjectMinimumBias.event;
        }
        continue;
      }
      // Do the injection
      for (int i{0}; i < cfg.mNInject; ++i) {
        const double pt = gRandom->Uniform(cfg.mPtMin, cfg.mPtMax);
        const double eta = gRandom->Uniform(cfg.mEtaMin, cfg.mEtaMax);
        const double phi = gRandom->Uniform(0, TMath::TwoPi());
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double pz{pt * std::sinh(eta)};
        const double et{std::hypot(std::hypot(pt, pz), cfg.mMass)};

        Particle particle;
        particle.id(cfg.mPdg);
        particle.status(11);
        particle.m(cfg.mMass);
        particle.px(px);
        particle.py(py);
        particle.pz(pz);
        particle.e(et);
        particle.xProd(0.f);
        particle.yProd(0.f);
        particle.zProd(0.f);
        mPythia.particleData.mayDecay(cfg.mPdg, true); // force decay
        mPythia.event.append(particle);
      }
      injectedForThisEvent = true;
    }
    if (injectedForThisEvent) {
      LOG(info) << "Calling next!";
      mPythia.moreDecays();
      mPythia.next();
      if (mPythia.event.size() <= 2) {
        LOG(fatal) << "Event size is " << mPythia.event.size() << ", this is not good! Check that the decay actually happened or consider not using the generator decayed particles!";
      } else {
        LOG(info) << "Event size is " << mPythia.event.size() << " particles";
      }
    }

    if (mVerbose) {
      LOG(info) << "Eventlisting";
      mPythia.event.list(1);
      mPythia.stat();
    }
    return true;
  }

  //__________________________________________________________________
  Bool_t importParticles() override
  {
    if (!mUseTriggering) { // If the triggering is used we handle the the gap when generating the signal
      if (mGapBetweenInjection > 0) {
        if (mGapBetweenInjection == 1 && mEventCounter % 2 == 0) {
          LOG(info) << "Skipping importParticles event " << mEventCounter++;
          return true;
        } else if (mEventCounter % mGapBetweenInjection != 0) {
          LOG(info) << "Skipping importParticles event " << mEventCounter++;
          return true;
        }
      }
    }
    LOG(info) << "importParticles " << mEventCounter++;
    GeneratorPythia8::importParticles();
    int nConfig = 0;
    for (const ConfigContainer& cfg : mGunConfigs) {
      nConfig++;
      if (mConfigToUse >= 0 && (nConfig - 1) != mConfigToUse) {
        continue;
      }
      LOGF(info, "Injecting %i particles with PDG %i, pT in [%f, %f]", cfg.mNInject, cfg.mPdg, cfg.mPtMin, cfg.mPtMax);

      for (int i{0}; i < cfg.mNInject; ++i) {
        const double pt = gRandom->Uniform(cfg.mPtMin, cfg.mPtMax);
        const double eta = gRandom->Uniform(cfg.mEtaMin, cfg.mEtaMax);
        const double phi = gRandom->Uniform(0, TMath::TwoPi());
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double pz{pt * std::sinh(eta)};
        const double et{std::hypot(std::hypot(pt, pz), cfg.mMass)};

        // TParticle::TParticle(Int_t pdg,
        //                      Int_t status,
        //                      Int_t mother1, Int_t mother2,
        //                      Int_t daughter1, Int_t daughter2,
        //                      Double_t px, Double_t py, Double_t pz, Double_t etot,
        //                      Double_t vx, Double_t vy, Double_t vz, Double_t time)

        mParticles.push_back(TParticle(cfg.mPdg,
                                       MCGenStatusEncoding(1, 1).fullEncoding,
                                       -1, -1,
                                       -1, -1,
                                       px, py, pz, et,
                                       0., 0., 0., 0.));
        // make sure status code is encoded properly. Transport flag will be set by default and we have nothing
        // to do since all pushed particles should be tracked.
        o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back());
      }
      nConfig++;
    }
    if (mVerbose) {
      LOG(info) << "Printing particles that are appended";
      int n = 0;
      for (const auto& p : mParticles) {
        LOG(info) << "Particle " << n++ << " is a " << p.GetPdgCode() << " with status " << p.GetStatusCode() << " and px = " << p.Px() << " py = " << p.Py() << " pz = " << p.Pz();
      }
    }
    return true;
  }

  struct ConfigContainer {
    ConfigContainer(int input_pdg = 0, int n = 1,
                    float ptMin = 1, float ptMax = 10,
                    float etaMin = -1, float etaMax = 1) : mPdg{input_pdg},
                                                           mNInject{n},
                                                           mPtMin{ptMin},
                                                           mPtMax{ptMax},
                                                           mEtaMin{etaMin},
                                                           mEtaMax{etaMax}
    {
      mMass = GeneratorPythia8LongLivedGun::getMass(mPdg);
      if (mMass <= 0) {
        LOG(fatal) << "Could not find mass for mPdg " << mPdg;
      }
      LOGF(info, "ConfigContainer: mPdg = %i, mNInject = %i, mPtMin = %f, mPtMax = %f, mEtaMin = %f, mEtaMax = %f, mMass = %f",
           mPdg, mNInject, mPtMin, mPtMax, mEtaMin, mEtaMax, mMass);
    };

    ConfigContainer(TObjArray* arr) : ConfigContainer(atoi(arr->At(0)->GetName()),
                                                      atoi(arr->At(1)->GetName()),
                                                      atof(arr->At(2)->GetName()),
                                                      atof(arr->At(3)->GetName()),
                                                      atof(arr->At(4)->GetName()),
                                                      atof(arr->At(5)->GetName()))
    {
      bool hasGenDecayed = false;
      for (int i = 0; i < arr->GetEntries(); i++) {
        const TString n = arr->At(i)->GetName();
        std::cout << n << std::endl;
        if (n == "genDecayed") {
          hasGenDecayed = true;
          break;
        }
      }
      if (hasGenDecayed) {
        if (arr->GetEntries() != 7) {
          LOG(fatal) << "Wrong number of entries in the configuration array, should be 7, is " << arr->GetEntries();
        }
      } else {
        if (arr->GetEntries() != 6) {
          LOG(fatal) << "Wrong number of entries in the configuration array, should be 6, is " << arr->GetEntries();
        }
      }
    };
    ConfigContainer(TString line) : ConfigContainer(line.Tokenize(" ")){};
    ConfigContainer(const nlohmann::json& jsonParams) : ConfigContainer(jsonParams["pdg"],
                                                                        jsonParams["n"],
                                                                        jsonParams["ptMin"],
                                                                        jsonParams["ptMax"],
                                                                        jsonParams["etaMin"],
                                                                        jsonParams["etaMax"]){};

    // Data Members
    const int mPdg = 0;
    const int mNInject = 1;
    const float mPtMin = 1;
    const float mPtMax = 10;
    const float mEtaMin = -1.f;
    const float mEtaMax = 1.f;
    double mMass = 0.f;

    void print() const
    {
      LOGF(info, "int mPdg = %i", mPdg);
      LOGF(info, "int mNInject = %i", mNInject);
      LOGF(info, "float mPtMin = %f", mPtMin);
      LOGF(info, "float mPtMax = %f", mPtMax);
      LOGF(info, "float mEtaMin = %f", mEtaMin);
      LOGF(info, "float mEtaMax = %f", mEtaMax);
      LOGF(info, "double mMass = %f", mMass);
    }
  };

  //__________________________________________________________________
  ConfigContainer addGun(int input_pdg, int nInject = 1, float ptMin = 1, float ptMax = 10, float etaMin = 1, float etaMax = 10)
  {
    if (mUseTriggering) { // If in trigger mode, every particle needs to be generated from pythia
      return addGunGenDecayed(input_pdg, nInject, ptMin, ptMax, etaMin, etaMax);
    }
    ConfigContainer cfg{input_pdg, nInject, ptMin, ptMax, etaMin, etaMax};
    mGunConfigs.push_back(cfg);
    return cfg;
  }

  //__________________________________________________________________
  ConfigContainer addGun(ConfigContainer cfg) { return addGun(cfg.mPdg, cfg.mNInject, cfg.mPtMin, cfg.mPtMax, cfg.mEtaMin, cfg.mEtaMax); }

  //__________________________________________________________________
  ConfigContainer addGunGenDecayed(int input_pdg, int nInject = 1, float ptMin = 1, float ptMax = 10, float etaMin = 1, float etaMax = 10)
  {
    ConfigContainer cfg{input_pdg, nInject, ptMin, ptMax, etaMin, etaMax};
    mGunConfigsGenDecayed.push_back(cfg);
    return cfg;
  }

  //__________________________________________________________________
  ConfigContainer addGunGenDecayed(ConfigContainer cfg) { return addGunGenDecayed(cfg.mPdg, cfg.mNInject, cfg.mPtMin, cfg.mPtMax, cfg.mEtaMin, cfg.mEtaMax); }

  //__________________________________________________________________
  long int getNGuns() const { return mGunConfigs.size() + mGunConfigsGenDecayed.size(); }

  //__________________________________________________________________
  void print()
  {
    LOG(info) << "GeneratorPythia8LF configuration with " << getNGuns() << " guns:";
    LOG(info) << "Particles decayed by the transport:";
    int n = 0;
    for (const auto& cfg : mGunConfigs) {
      LOG(info) << n++ << "/" << mGunConfigs.size() << ":";
      cfg.print();
    }
    n = 0;
    LOG(info) << "Particles decayed by the generator:";
    for (const auto& cfg : mGunConfigsGenDecayed) {
      LOG(info) << n++ << "/" << mGunConfigs.size() << ":";
      cfg.print();
    }
  }

  void setVerbose(bool verbose = true) { mVerbose = verbose; }

 private:
  //  Configuration
  const bool mOneInjectionPerEvent = true; // if true, only one injection per event is performed, i.e. if multiple PDG (including antiparticles) are requested to be injected only one will be done per event
  const bool mUseTriggering = false;       // if true, use triggering instead of injection
  const int mGapBetweenInjection = 0;      // Gap between two signal events. 0 means injection at every event

  // Running variables
  int mConfigToUse = -1; // Index of the configuration to use
  int mEventCounter = 0; // Event counter
  bool mVerbose = true;  // Verbosity flag

  std::vector<ConfigContainer> mGunConfigs;           // List of gun configurations to use
  std::vector<ConfigContainer> mGunConfigsGenDecayed; // List of gun configurations to use that will be decayed by the generator
  Pythia8::Pythia pythiaObjectSignal;                          // Signal collision generator
  Pythia8::Pythia pythiaObjectMinimumBias;                     // Minimum bias collision generator
};

///___________________________________________________________
/// Create generator via arrays of entries. By default injecting in every event and all particles
FairGenerator* generateLF(std::vector<int> PDGs, std::vector<int> nInject, std::vector<float> ptMin, std::vector<float> ptMax)
{
  const std::vector<unsigned long> entries = {PDGs.size(), nInject.size(), ptMin.size(), ptMax.size()};
  if (!std::equal(entries.begin() + 1, entries.end(), entries.begin())) {
    LOGF(fatal, "Not equal number of entries, check configuration");
    return nullptr;
  }
  GeneratorPythia8LF* multiGun = new GeneratorPythia8LF(false, 0, false, "", "");
  for (unsigned long i = 0; i < entries[0]; i++) {
    multiGun->addGun(PDGs[i], nInject[i], ptMin[i], ptMax[i]);
  }
  return multiGun;
}

///___________________________________________________________
/// Create generator via an array of configurations
FairGenerator* generateLF(std::vector<GeneratorPythia8LF::ConfigContainer> cfg,
                          std::vector<GeneratorPythia8LF::ConfigContainer> cfgGenDecayed,
                          bool injectOnePDGPerEvent = true,
                          int gapBetweenInjection = 0,
                          bool useTrigger = false,
                          std::string pythiaCfgMb = "",
                          std::string pythiaCfgSignal = "")
{
  GeneratorPythia8LF* multiGun = new GeneratorPythia8LF(injectOnePDGPerEvent, gapBetweenInjection, useTrigger, pythiaCfgMb, pythiaCfgSignal);
  for (const auto& c : cfg) {
    LOGF(info, "Adding gun %i", multiGun->getNGuns());
    c.print();
    multiGun->addGun(c);
  }
  for (const auto& c : cfgGenDecayed) {
    LOGF(info, "Adding gun %i, particle will be decayed by the generator", multiGun->getNGuns());
    c.print();
    multiGun->addGunGenDecayed(c);
  }
  multiGun->print();
  return multiGun;
}

///___________________________________________________________
/// Create generator via input file
FairGenerator* generateLF(std::string configuration = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/nuclei.gun",
                          bool injectOnePDGPerEvent = true,
                          int gapBetweenInjection = 0,
                          bool useTrigger = false,
                          std::string pythiaCfgMb = "",
                          std::string pythiaCfgSignal = "")
{
  configuration = gSystem->ExpandPathName(configuration.c_str());
  LOGF(info, "Using configuration file '%s'", configuration.c_str());
  std::ifstream inputFile(configuration.c_str(), ios::in);
  std::vector<GeneratorPythia8LF::ConfigContainer> cfgVec;
  std::vector<GeneratorPythia8LF::ConfigContainer> cfgVecGenDecayed;
  if (!inputFile.is_open()) {
    LOGF(fatal, "Can't open '%s' !", configuration.c_str());
    return nullptr;
  }
  if (TString(configuration.c_str()).EndsWith(".json")) { // read from JSON file
    nlohmann::json paramfile = nlohmann::json::parse(inputFile);
    std::cout << "paramfile " << paramfile << std::endl;
    for (const auto& param : paramfile) {
      std::cout << param << std::endl;
      // cfgVecGenDecayed.push_back(GeneratorPythia8LF::ConfigContainer{paramfile[n].template get<int>(), param});
      if (param["genDecayed"]) {
        cfgVecGenDecayed.push_back(GeneratorPythia8LF::ConfigContainer{param});
      } else {
        cfgVec.push_back(GeneratorPythia8LF::ConfigContainer{param});
      }
    }
  } else {
    std::string l;
    int n = 0;
    while (getline(inputFile, l)) {
      TString line = l;
      line.Strip(TString::kBoth, ' ');
      std::cout << n++ << " '" << line << "'" << endl;
      if (line.IsNull() || line.IsWhitespace()) {
        continue;
      }
      if (line.BeginsWith("#")) {
        std::cout << "Skipping\n";
        continue;
      }
      if (line.Contains("genDecayed")) {
        cfgVecGenDecayed.push_back(GeneratorPythia8LF::ConfigContainer{line});
      } else {
        cfgVec.push_back(GeneratorPythia8LF::ConfigContainer{line});
      }
    }
  }
  return generateLF(cfgVec, cfgVecGenDecayed, injectOnePDGPerEvent, gapBetweenInjection, useTrigger, pythiaCfgMb, pythiaCfgSignal);
}

///___________________________________________________________
/// Create generator via input file for the triggered mode
FairGenerator* generateLFTriggered(std::string configuration = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/nuclei.gun",
                                   int gapBetweenInjection = 0,
                                   std::string pythiaCfgMb = "",
                                   std::string pythiaCfgSignal = "")
{
  return generateLF(configuration, /*injectOnePDGPerEvent=*/true, gapBetweenInjection, /*useTrigger=*/true, pythiaCfgMb, pythiaCfgSignal);
}

///___________________________________________________________
void generator_pythia8_LF(bool testInj = true, bool testTrg = false, const char* particleListFile = "cfg.json")
{
  LOG(info) << "Compiled correctly!";
  if (!testInj && !testTrg) {
    return;
  }
  // Injected mode
  if (testInj) {
    LOG(info) << "Testing the injected mode";
    auto* gen = static_cast<GeneratorPythia8LF*>(generateLF(particleListFile));
    gen->setVerbose();
    gen->Print();
    gen->print();
    gen->Init();
    gen->generateEvent();
    gen->importParticles();
  }

  // Triggered mode
  if (testTrg) {
    LOG(info) << "Testing the triggered mode";
    GeneratorPythia8LF* gen = static_cast<GeneratorPythia8LF*>(generateLFTriggered(particleListFile,
                                                                                   /*gapBetweenInjection=*/0,
                                                                                   /*pythiaCfgMb=*/"inel136tev.cfg",
                                                                                   /*pythiaCfgSignal=*/"inel136tev.cfg"));
    gen->setVerbose();
    gen->Print();
    gen->print();
    gen->Init();
    gen->generateEvent();
    gen->importParticles();
  }
}
