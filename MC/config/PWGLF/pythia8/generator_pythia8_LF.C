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
///               `o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_LF.C;GeneratorExternal.funcName=generateLF("${O2DPG_ROOT}/MC/config/PWGLF/pythia8/generator/nuclei.gun")'`
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
                     std::string pythiaCfgMb /*= "${O2DPG_ROOT}/MC/config/PWGLF/pythia8/pythia8_inel_minbias.cfg"*/,
                     std::string pythiaCfgSignal /*= "${O2DPG_ROOT}/MC/config/PWGLF/pythia8/pythia8_inel_signal.cfg"*/) : GeneratorPythia8{},
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
      if (!pythiaObjectMinimumBias.init()) {
        LOG(fatal) << "Could not pythiaObjectMinimumBias.init() from " << pythiaCfgMb;
      }
      if (!pythiaObjectSignal.readFile(pythiaCfgSignal)) {
        LOG(fatal) << "Could not pythiaObjectSignal.readFile(\"" << pythiaCfgSignal << "\")";
      }
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
    gRandom->SetSeed(0);
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
        bool doSignal = true; // Do signal or gap
        if (mGapBetweenInjection > 0) {
          if (mGapBetweenInjection == 1 && mEventCounter % 2 == 0) {
            doSignal = false;
          } else if (mEventCounter % mGapBetweenInjection != 0) {
            doSignal = false;
          }
        }

        if (doSignal) {
          LOG(info) << "Generating triggered signal event for particle";
          cfg.print();
          bool satisfiesTrigger = false;
          int nTries = 0;
          while (!satisfiesTrigger) {
            if (!pythiaObjectSignal.next()) {
              continue;
            }
            //Check if triggered condition satisfied
            for (Long_t j = 0; j < pythiaObjectSignal.event.size(); j++) {
              const int& pypid = pythiaObjectSignal.event[j].id();
              const float& pyeta = pythiaObjectSignal.event[j].eta();
              const float& pypt = pythiaObjectSignal.event[j].pT();
              if (pypid == cfg.pdg && cfg.etaMin < pyeta && pyeta < cfg.etaMax && pypt > cfg.ptMin && pypt < cfg.ptMax) {
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
      for (int i{0}; i < cfg.nInject; ++i) {
        const double pt = gRandom->Uniform(cfg.ptMin, cfg.ptMax);
        const double eta = gRandom->Uniform(cfg.etaMin, cfg.etaMax);
        const double phi = gRandom->Uniform(0, TMath::TwoPi());
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double pz{pt * std::sinh(eta)};
        const double et{std::hypot(std::hypot(pt, pz), cfg.mass)};

        Particle particle;
        particle.id(cfg.pdg);
        particle.status(11);
        particle.m(cfg.mass);
        particle.px(px);
        particle.py(py);
        particle.pz(pz);
        particle.e(et);
        particle.xProd(0.f);
        particle.yProd(0.f);
        particle.zProd(0.f);
        mPythia.particleData.mayDecay(cfg.pdg, true); // force decay
      }
    }
    if (!mUseTriggering) {
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
      LOGF(info, "Injecting %i particles with PDG %i, pT in [%f, %f]", cfg.nInject, cfg.pdg, cfg.ptMin, cfg.ptMax);

      for (int i{0}; i < cfg.nInject; ++i) {
        const double pt = gRandom->Uniform(cfg.ptMin, cfg.ptMax);
        const double eta = gRandom->Uniform(cfg.etaMin, cfg.etaMax);
        const double phi = gRandom->Uniform(0, TMath::TwoPi());
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double pz{pt * std::sinh(eta)};
        const double et{std::hypot(std::hypot(pt, pz), cfg.mass)};

        // TParticle::TParticle(Int_t pdg,
        //                      Int_t status,
        //                      Int_t mother1, Int_t mother2,
        //                      Int_t daughter1, Int_t daughter2,
        //                      Double_t px, Double_t py, Double_t pz, Double_t etot,
        //                      Double_t vx, Double_t vy, Double_t vz, Double_t time)

        mParticles.push_back(TParticle(cfg.pdg,
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
    ConfigContainer(int input_pdg = 0, int n = 1, float p = 1, float P = 10) : pdg{input_pdg},
                                                                               nInject{n},
                                                                               ptMin{p},
                                                                               ptMax{P}
    {
      mass = GeneratorPythia8LongLivedGun::getMass(pdg);
      if (mass <= 0) {
        LOG(fatal) << "Could not find mass for pdg " << pdg;
      }
      LOGF(info, "ConfigContainer: pdg = %i, nInject = %i, ptMin = %f, ptMax = %f, mass = %f", pdg, nInject, ptMin, ptMax, mass);
    };
    ConfigContainer(TObjArray* arr) : ConfigContainer(atoi(arr->At(0)->GetName()),
                                                      atoi(arr->At(1)->GetName()),
                                                      atof(arr->At(2)->GetName()),
                                                      atof(arr->At(3)->GetName())){};

    int pdg = 0;
    int nInject = 1;
    float ptMin = 1;
    float ptMax = 10;
    float etaMin = -1.f;
    float etaMax = 1.f;
    double mass = 0.f;
    void print() const
    {
      LOGF(info, "int pdg = %i", pdg);
      LOGF(info, "int nInject = %i", nInject);
      LOGF(info, "float ptMin = %f", ptMin);
      LOGF(info, "float ptMax = %f", ptMax);
      LOGF(info, "float etaMin = %f", etaMin);
      LOGF(info, "float etaMax = %f", etaMax);
      LOGF(info, "double mass = %f", mass);
    }
  };

  //__________________________________________________________________
  ConfigContainer addGun(int input_pdg, int nInject = 1, float ptMin = 1, float ptMax = 10)
  {
    if (mUseTriggering) { // If in trigger mode, every particle needs to be generated from pythia
      return addGunGenDecayed(input_pdg, nInject, ptMin, ptMax);
    }
    ConfigContainer cfg{input_pdg, nInject, ptMin, ptMax};
    mGunConfigs.push_back(cfg);
    return cfg;
  }

  //__________________________________________________________________
  ConfigContainer addGun(ConfigContainer cfg) { return addGun(cfg.pdg, cfg.nInject, cfg.ptMin, cfg.ptMax); }

  //__________________________________________________________________
  ConfigContainer addGunGenDecayed(int input_pdg, int nInject = 1, float ptMin = 1, float ptMax = 10)
  {
    ConfigContainer cfg{input_pdg, nInject, ptMin, ptMax};
    mGunConfigsGenDecayed.push_back(cfg);
    return cfg;
  }

  //__________________________________________________________________
  ConfigContainer addGunGenDecayed(ConfigContainer cfg) { return addGunGenDecayed(cfg.pdg, cfg.nInject, cfg.ptMin, cfg.ptMax); }

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
  Pythia pythiaObjectSignal;                          // Signal collision generator
  Pythia pythiaObjectMinimumBias;                     // Minimum bias collision generator
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
FairGenerator* generateLF(std::string configuration = "${O2DPG_ROOT}/MC/config/PWGLF/pythia8/generator/nuclei.gun",
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
  if (inputFile.is_open()) {
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
        cfgVecGenDecayed.push_back(GeneratorPythia8LF::ConfigContainer{line.Tokenize(" ")});
      } else {
        cfgVec.push_back(GeneratorPythia8LF::ConfigContainer{line.Tokenize(" ")});
      }
    }
  } else {
    LOGF(fatal, "Can't open '%s' !", configuration.c_str());
    return nullptr;
  }
  return generateLF(cfgVec, cfgVecGenDecayed, injectOnePDGPerEvent, gapBetweenInjection, useTrigger, pythiaCfgMb, pythiaCfgSignal);
}

///___________________________________________________________
/// Create generator via input file for the triggered mode
FairGenerator* generateLFTriggered(std::string configuration = "${O2DPG_ROOT}/MC/config/PWGLF/pythia8/generator/nuclei.gun",
                                   int gapBetweenInjection = 0,
                                   std::string pythiaCfgMb = "",
                                   std::string pythiaCfgSignal = "")
{
  return generateLF(configuration, /*injectOnePDGPerEvent=*/true, gapBetweenInjection, /*useTrigger=*/true, pythiaCfgMb, pythiaCfgSignal);
}

///___________________________________________________________
void generator_pythia8_LF(bool testInj = true, bool testTrg = false)
{
  LOG(info) << "Compiled correctly!";
  if (!testInj && !testTrg) {
    return;
  }
  // Injected mode
  if (testInj) {
    LOG(info) << "Testing the injected mode";
    auto* gen = static_cast<GeneratorPythia8LF*>(generateLF("/home/njacazio/alice/O2DPG/MC/config/PWGLF/pythia8/generator/strangeparticlelist.gun"));
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
    GeneratorPythia8LF* gen = static_cast<GeneratorPythia8LF*>(generateLFTriggered("/home/njacazio/alice/O2DPG/MC/config/PWGLF/pythia8/generator/strangeparticlelist.gun",
                                                                                   /*gapBetweenInjection=*/0,
                                                                                   /*pythiaCfgMb=*/"/home/njacazio/alice/O2DPG/MC/config/PWGLF/pythia8/generator/inel136tev.cfg",
                                                                                   /*pythiaCfgSignal=*/"/home/njacazio/alice/O2DPG/MC/config/PWGLF/pythia8/generator/inel136tev.cfg"));
    gen->setVerbose();
    gen->Print();
    gen->print();
    gen->Init();
    gen->generateEvent();
    gen->importParticles();
  }
}
