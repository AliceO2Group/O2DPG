/// \file   generator_pythia8_LF_flat_mass.C
/// \author Sawan sawan.sawan@cern.ch
/// \brief  Modified LF Gun Generator for Flat Mass PHSP PWA Acceptance/Efficiency MC.
///         Adapted from generator_pythia8_LF_rapidity_width.C

#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"

#include "TDatabasePDG.h"
#include "TMath.h"
#include "TParticlePDG.h"
#include "TRandom3.h"

#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#if __has_include("SimulationDataFormat/MCGenStatus.h")
#include "SimulationDataFormat/MCGenStatus.h"
#else
#include "SimulationDataFormat/MCGenProperties.h"
#endif
#if __has_include("SimulationDataFormat/MCUtils.h")
#include "SimulationDataFormat/MCUtils.h"
#endif
#include "TSystem.h"

#include "Generators/GeneratorPythia8Param.h"
#include "fairlogger/Logger.h"

#include <cmath>
#include <fstream>
#endif
// DecayerPythia8Param needs to be included after the #endif to work with Cling
#include "Generators/DecayerPythia8Param.h"
#if defined(__CLING__) && !defined(__ROOTCLING__)
#if __has_include("SimulationDataFormat/MCGenStatus.h")
#include "SimulationDataFormat/MCGenStatus.h"
#elif __has_include("SimulationDataFormat/MCGenProperties.h")
#include "SimulationDataFormat/MCGenProperties.h"
#endif
#if __has_include("SimulationDataFormat/MCUtils.h")
#include "SimulationDataFormat/MCUtils.h"
#endif
#pragma cling load("libO2Generators")
#endif
#include "generator_pythia8_longlived.C"

#include <nlohmann/json.hpp>

using namespace Pythia8;
using namespace o2::mcgenstatus;

class GeneratorPythia8LFRapidity : public o2::eventgen::GeneratorPythia8
{
public:
  /// Parametric constructor
  GeneratorPythia8LFRapidity(bool injOnePerEvent = true,
                             int gapBetweenInjection = 0,
                             bool useTrigger = false,
                             bool useRapidity = false,
                             std::string pythiaCfgMb = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/pythia8_inel_136tev.cfg",
                             std::string pythiaCfgSignal = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/pythia8_inel_136tev.cfg") : GeneratorPythia8{},
                                                                                                                                                  mOneInjectionPerEvent{injOnePerEvent},
                                                                                                                                                  mGapBetweenInjection{gapBetweenInjection},
                                                                                                                                                  mUseTriggering{useTrigger},
                                                                                                                                                  mUseRapidity{useRapidity}
  {
    LOG(info) << "GeneratorPythia8LFRapidity constructor (Flat Mass PHSP mode)";
    LOG(info) << "++ mOneInjectionPerEvent: " << mOneInjectionPerEvent;
    LOG(info) << "++ mGapBetweenInjection: " << mGapBetweenInjection;
    LOG(info) << "++ mUseTriggering: " << mUseTriggering;
    LOG(info) << "++ mUseRapidity: " << mUseRapidity;
    LOG(info) << "++ pythiaCfgMb: " << pythiaCfgMb;
    LOG(info) << "++ pythiaCfgSignal: " << pythiaCfgSignal;
    gRandom->SetSeed(0);

    // Register PDG 10331 f0(1710) in ROOT TDatabasePDG if missing to prevent Geant4 / TDatabase crashes
    if (!TDatabasePDG::Instance()->GetParticle(10331))
    {
      TDatabasePDG::Instance()->AddParticle("f0_1710", "f0_1710", 1.710, true, 0.150, 0, "meson", 10331);
    }

    if (useTrigger)
    {
      mPythia.readString("ProcessLevel:all off");
      if (pythiaCfgMb == "")
      {
        auto &param = o2::eventgen::GeneratorPythia8Param::Instance();
        pythiaCfgMb = param.config;
      }
      if (pythiaCfgSignal == "")
      {
        auto &param = o2::eventgen::GeneratorPythia8Param::Instance();
        pythiaCfgSignal = param.config;
      }
      pythiaCfgMb = gSystem->ExpandPathName(pythiaCfgMb.c_str());
      pythiaCfgSignal = gSystem->ExpandPathName(pythiaCfgSignal.c_str());
      if (!pythiaObjectMinimumBias.readFile(pythiaCfgMb))
      {
        LOG(fatal) << "Could not pythiaObjectMinimumBias.readFile(\"" << pythiaCfgMb << "\")";
      }
      pythiaObjectMinimumBias.readString("Random:setSeed = on");
      pythiaObjectMinimumBias.readString("Random:seed =" + std::to_string(gRandom->Integer(900000000 - 2) + 1));

      if (!pythiaObjectSignal.readFile(pythiaCfgSignal))
      {
        LOG(fatal) << "Could not pythiaObjectSignal.readFile(\"" << pythiaCfgSignal << "\")";
      }
      pythiaObjectSignal.readString("Random:setSeed = on");
      pythiaObjectSignal.readString("Random:seed =" + std::to_string(gRandom->Integer(900000000 - 2) + 1));
      pythiaObjectMinimumBias.particleData.addParticle(1000100200, "20Ne", 6, 30, 0, 19.992440);
      mPythiaGun.particleData.addParticle(1000100200, "20Ne", 6, 30, 0, 19.992440);
      if (!pythiaObjectMinimumBias.init())
      {
        LOG(fatal) << "Could not pythiaObjectMinimumBias.init() from " << pythiaCfgMb;
      }
      if (!pythiaObjectSignal.init())
      {
        LOG(fatal) << "Could not pythiaObjectSignal.init() from " << pythiaCfgSignal;
      }
    }
    else
    {
      if (pythiaCfgMb == "")
      {
        auto &param = o2::eventgen::GeneratorPythia8Param::Instance();
        pythiaCfgMb = param.config;
      }
      if (pythiaCfgMb == "")
      {
        pythiaCfgMb = "${O2DPG_MC_CONFIG_ROOT}/MC/config/PWGLF/pythia8/generator/pythia8_inel_136tev.cfg";
      }
      pythiaCfgMb = gSystem->ExpandPathName(pythiaCfgMb.c_str());
      if (!pythiaObjectMinimumBias.readFile(pythiaCfgMb))
      {
        LOG(fatal) << "Could not pythiaObjectMinimumBias.readFile(\"" << pythiaCfgMb << "\")";
      }
      pythiaObjectMinimumBias.readString("Random:setSeed = on");
      pythiaObjectMinimumBias.readString("Random:seed =" + std::to_string(gRandom->Integer(900000000 - 2) + 1));

      pythiaObjectMinimumBias.particleData.addParticle(1000100200, "20Ne", 6, 30, 0, 19.992440);
      mPythiaGun.particleData.addParticle(1000100200, "20Ne", 6, 30, 0, 19.992440);
      if (!pythiaObjectMinimumBias.init())
      {
        LOG(fatal) << "Could not pythiaObjectMinimumBias.init() from " << pythiaCfgMb;
      }

      mPythiaGun.readString("ProcessLevel:all off");

      auto &param = o2::eventgen::DecayerPythia8Param::Instance();
      for (int i = 0; i < 8; ++i)
      {
        if (param.config[i].empty())
        {
          continue;
        }
        std::string config = gSystem->ExpandPathName(param.config[i].c_str());
        readParticleDataLines(mPythia, config, "import Pythia");
        if (!mPythiaGun.readFile(config, true))
        {
          LOG(fatal) << "Failed to init \'DecayerPythia8\': problems with configuration file " << config;
          return;
        }
      }

      if (param.showChanged)
      {
        mPythiaGun.readString(std::string("Init:showChangedParticleData on"));
      }
      else
      {
        mPythiaGun.readString(std::string("Init:showChangedParticleData off"));
      }

      if (!mPythiaGun.init())
      {
        LOG(fatal) << "Failed to init \'DecayerPythia8\': init returned with error";
        return;
      }
    }
  }

  ~GeneratorPythia8LFRapidity() = default;

  bool Init() override
  {
    addSubGenerator(kSubGeneratorMinimumBias, "Minimum bias");
    addSubGenerator(kSubGeneratorLFSignal, "LF signal");
    return o2::eventgen::GeneratorPythia8::Init();
  }

  Bool_t generateEvent() override
  {
    mDoSignalThisEvent = isSignalEvent();
    notifySubGenerator(mDoSignalThisEvent ? kSubGeneratorLFSignal : kSubGeneratorMinimumBias);

    if (!mUseTriggering)
    {
      bool lGenerationOK = false;
      while (!lGenerationOK)
      {
        lGenerationOK = pythiaObjectMinimumBias.next();
      }
      copyMinimumBiasEventForInjection();

      if (!mDoSignalThisEvent)
      {
        return true;
      }
    }

    if (mUseTriggering)
    {
      mPythia.event.reset();
    }

    mConfigToUse = mOneInjectionPerEvent ? static_cast<int>(gRandom->Uniform(0.f, getNGuns())) : -1;

    int nConfig = mGunConfigs.size();
    for (const ConfigContainer &cfg : mGunConfigsGenDecayed)
    {
      nConfig++;
      if (mConfigToUse >= 0 && (nConfig - 1) != mConfigToUse)
      {
        continue;
      }

      if (mUseTriggering)
      {
        if (mDoSignalThisEvent)
        {
          bool satisfiesTrigger = false;
          int nTries = 0;
          while (!satisfiesTrigger)
          {
            if (!pythiaObjectSignal.next())
            {
              continue;
            }
            for (int j = 0; j < pythiaObjectSignal.event.size(); j++)
            {
              const int &pypid = pythiaObjectSignal.event[j].id();
              const float &pyeta = mUseRapidity ? pythiaObjectSignal.event[j].y() : pythiaObjectSignal.event[j].eta();
              const float &pypt = pythiaObjectSignal.event[j].pT();
              if (pypid == cfg.mPdg && cfg.mMin < pyeta && pyeta < cfg.mMax && pypt > cfg.mPtMin && pypt < cfg.mPtMax)
              {
                satisfiesTrigger = true;
                break;
              }
            }
            nTries++;
          }
          mPythia.event = pythiaObjectSignal.event;
        }
        else
        {
          bool lGenerationOK = false;
          while (!lGenerationOK)
          {
            lGenerationOK = pythiaObjectMinimumBias.next();
          }
          mPythia.event = pythiaObjectMinimumBias.event;
        }
        continue;
      }

      mPythiaGun.event.reset();
      for (int i{0}; i < cfg.mNInject; ++i)
      {
        const double pt = gRandom->Uniform(cfg.mPtMin, cfg.mPtMax);
        const double eta = gRandom->Uniform(cfg.mMin, cfg.mMax);
        const double phi = gRandom->Uniform(0, TMath::TwoPi());
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double mass = sampleMass(cfg); // Uses Flat Mass Sampling

        double pz = 0;
        double et = 0;

        if (mUseRapidity)
        {
          const double mT = std::sqrt(mass * mass + pt * pt);
          pz = mT * std::sinh(eta);
          et = mT * std::cosh(eta);
        }
        else
        {
          pz = pt * std::sinh(eta);
          const double p = pt * std::cosh(eta);
          et = std::sqrt(p * p + mass * mass);
        }

        Particle particle;
        particle.id(cfg.mPdg);
        particle.status(11);
        particle.m(mass);
        particle.px(px);
        particle.py(py);
        particle.pz(pz);
        particle.e(et);
        particle.xProd(0.f);
        particle.yProd(0.f);
        particle.zProd(0.f);
        particle.tProd(0.f);
        mPythiaGun.particleData.mayDecay(cfg.mPdg, true);
        mPythiaGun.event.append(particle);
      }

      mPythiaGun.moreDecays();
      mPythiaGun.next();

      int offset = mPythia.event.size();
      for (int i = 1; i < mPythiaGun.event.size(); ++i)
      {
        Particle &p = mPythiaGun.event[i];
        int mother1 = p.mother1() > 0 ? p.mother1() + offset - 1 : p.mother1();
        int mother2 = p.mother2() > 0 ? p.mother2() + offset - 1 : p.mother2();
        int daughter1 = p.daughter1() > 0 ? p.daughter1() + offset - 1 : p.daughter1();
        int daughter2 = p.daughter2() > 0 ? p.daughter2() + offset - 1 : p.daughter2();

        p.mothers(mother1, mother2);
        p.daughters(daughter1, daughter2);

        mPythia.event.append(p);
      }
    }
    return true;
  }

  Bool_t importParticles() override
  {
    if (!GeneratorPythia8::importParticles())
    {
      return false;
    }

    if (!mUseTriggering && mDoSignalThisEvent)
    {
      int nConfig = 0;
      for (const ConfigContainer &cfg : mGunConfigs)
      {
        nConfig++;
        if (mConfigToUse >= 0 && (nConfig - 1) != mConfigToUse)
        {
          continue;
        }

        for (int i{0}; i < cfg.mNInject; ++i)
        {
          const double pt = gRandom->Uniform(cfg.mPtMin, cfg.mPtMax);
          const double eta = gRandom->Uniform(cfg.mMin, cfg.mMax);
          const double phi = gRandom->Uniform(0, TMath::TwoPi());
          const double px{pt * std::cos(phi)};
          const double py{pt * std::sin(phi)};
          const double mass = sampleMass(cfg);
          double pz = 0;
          double et = 0;

          if (mUseRapidity)
          {
            const double mT = std::sqrt(mass * mass + pt * pt);
            pz = mT * std::sinh(eta);
            et = mT * std::cosh(eta);
          }
          else
          {
            pz = pt * std::sinh(eta);
            const double p = pt * std::cosh(eta);
            et = std::sqrt(p * p + mass * mass);
          }

          mParticles.push_back(TParticle(cfg.mPdg,
                                         MCGenStatusEncoding(1, 1).fullEncoding,
                                         -1, -1,
                                         -1, -1,
                                         px, py, pz, et,
                                         0., 0., 0., 0.));
          o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back());
        }
      }
    }

    mEventCounter++;
    return true;
  }

  struct ConfigContainer
  {
    // 1. Set default constructor arguments to 1.0 and 3.0
    ConfigContainer(int input_pdg = 10331, int n = 1,
                    float ptMin = 0.0, float ptMax = 30.0,
                    float min = -1.0, float max = 1.0,
                    double massMin = 1.0, double massMax = 3.0) : mPdg{input_pdg},
                                                                  mNInject{n},
                                                                  mPtMin{ptMin},
                                                                  mPtMax{ptMax},
                                                                  mMin{min},
                                                                  mMax{max},
                                                                  mMassMin{massMin},
                                                                  mMassMax{massMax}
    {
      mMass = GeneratorPythia8LongLivedGun::getMass(mPdg);
      if (mMass <= 0)
      {
        mMass = 1.710;
      }
      LOGF(info, "ConfigContainer: mPdg = %i, mNInject = %i, mPtMin = %f, mPtMax = %f, mMin = %f, mMax = %f, mMassMin = %f, mMassMax = %f",
           mPdg, mNInject, mPtMin, mPtMax, mMin, mMax, mMassMin, mMassMax);
    };

    ConfigContainer(TObjArray *arr) : ConfigContainer(
                                          arr->GetEntries() > 0 ? atoi(arr->At(0)->GetName()) : 10331,
                                          arr->GetEntries() > 1 ? atoi(arr->At(1)->GetName()) : 1,
                                          arr->GetEntries() > 2 ? atof(arr->At(2)->GetName()) : 0.0,
                                          arr->GetEntries() > 3 ? atof(arr->At(3)->GetName()) : 30.0,
                                          arr->GetEntries() > 4 ? atof(arr->At(4)->GetName()) : -1.0,
                                          arr->GetEntries() > 5 ? atof(arr->At(5)->GetName()) : 1.0,
                                          arr->GetEntries() > 6 ? atof(arr->At(6)->GetName()) : 1.0,
                                          arr->GetEntries() > 7 ? atof(arr->At(7)->GetName()) : 3.0) {};

    ConfigContainer(TString line) : ConfigContainer(line.Tokenize(" ")) {};

    // 2. Set jsonParams.value fallback defaults to 1.0 and 3.0
    ConfigContainer(const nlohmann::json &jsonParams, bool useRapidity = false)
        : ConfigContainer(jsonParams.value("pdg", 10331),
                          jsonParams.value("n", 1),
                          jsonParams.value("ptMin", 0.0f),
                          jsonParams.value("ptMax", 30.0f),
                          (useRapidity && jsonParams.contains("rapidityMin")) ? jsonParams["rapidityMin"].get<float>() : (jsonParams.contains("min") ? jsonParams["min"].get<float>() : jsonParams.value("etaMin", -1.0f)),
                          (useRapidity && jsonParams.contains("rapidityMax")) ? jsonParams["rapidityMax"].get<float>() : (jsonParams.contains("max") ? jsonParams["max"].get<float>() : jsonParams.value("etaMax", 1.0f)),
                          jsonParams.value("massMin", 1.0),
                          jsonParams.value("massMax", 3.0)) {};

    const int mPdg = 10331;
    const int mNInject = 1;
    const float mPtMin = 0.0;
    const float mPtMax = 30.0;
    const float mMin = -1.f;
    const float mMax = 1.f;
    double mMass = 0.f;
    double mMassMin = 1.0;
    double mMassMax = 3.0;

    void print() const
    {
      LOGF(info, "int mPdg = %i, mNInject = %i, mPtMin = %f, mPtMax = %f, mMin = %f, mMax = %f, mMassMin = %f, mMassMax = %f",
           mPdg, mNInject, mPtMin, mPtMax, mMin, mMax, mMassMin, mMassMax);
    }
  };

  // FLAT MASS SAMPLING LOGIC
  // FLAT MASS SAMPLING LOGIC
  double sampleMass(const ConfigContainer &cfg)
  {
    if (cfg.mMassMax > cfg.mMassMin && cfg.mMassMin > 0.0)
    {
      return gRandom->Uniform(cfg.mMassMin, cfg.mMassMax);
    }
    // Fallback if range is invalid or missing: flat uniform in [1.0, 3.0] GeV
    return gRandom->Uniform(1.0, 3.0);
  }

  ConfigContainer addGun(int input_pdg, int nInject = 1, float ptMin = 0, float ptMax = 30, float min = -1, float max = 1, double massMin = -1.0, double massMax = -1.0)
  {
    if (mUseTriggering)
    {
      return addGunGenDecayed(input_pdg, nInject, ptMin, ptMax, min, max, massMin, massMax);
    }
    ConfigContainer cfg{input_pdg, nInject, ptMin, ptMax, min, max, massMin, massMax};
    mGunConfigs.push_back(cfg);
    return cfg;
  }

  ConfigContainer addGun(ConfigContainer cfg) { return addGun(cfg.mPdg, cfg.mNInject, cfg.mPtMin, cfg.mPtMax, cfg.mMin, cfg.mMax, cfg.mMassMin, cfg.mMassMax); }

  ConfigContainer addGunGenDecayed(int input_pdg, int nInject = 1, float ptMin = 0, float ptMax = 30, float min = -1, float max = 1, double massMin = -1.0, double massMax = -1.0)
  {
    ConfigContainer cfg{input_pdg, nInject, ptMin, ptMax, min, max, massMin, massMax};
    mGunConfigsGenDecayed.push_back(cfg);
    return cfg;
  }

  ConfigContainer addGunGenDecayed(ConfigContainer cfg) { return addGunGenDecayed(cfg.mPdg, cfg.mNInject, cfg.mPtMin, cfg.mPtMax, cfg.mMin, cfg.mMax, cfg.mMassMin, cfg.mMassMax); }

  long int getNGuns() const { return mGunConfigs.size() + mGunConfigsGenDecayed.size(); }

private:
  static constexpr int kSubGeneratorMinimumBias = 0;
  static constexpr int kSubGeneratorLFSignal = 1;

  bool isSignalEvent() const { return mGapBetweenInjection <= 1 || mEventCounter % mGapBetweenInjection == 0; }

  void copyMinimumBiasEventForInjection()
  {
    mPythia.event = pythiaObjectMinimumBias.event;
    mPythia.event.init("Minimum-bias event with injected particles", &mPythia.particleData);
    mPythia.event.restorePtrs();
  }

  static bool isParticleDataLine(const std::string &line)
  {
    size_t pos = line.find_first_not_of(" \t");
    if (pos == std::string::npos)
      return false;
    if (line[pos] == '+' || line[pos] == '-')
      ++pos;
    if (pos >= line.size() || line[pos] < '0' || line[pos] > '9')
      return false;
    while (pos < line.size() && line[pos] >= '0' && line[pos] <= '9')
      ++pos;
    return pos < line.size() && line[pos] == ':';
  }

  static bool readParticleDataLines(Pythia8::Pythia &pythia, const std::string &config, const char *target)
  {
    std::ifstream input(config.c_str(), ios::in);
    if (!input.is_open())
      return false;
    std::string line;
    while (std::getline(input, line))
    {
      TString stripped = line;
      stripped.Strip(TString::kBoth, ' ');
      if (stripped.IsNull() || stripped.IsWhitespace() || stripped.BeginsWith("#"))
        continue;
      std::string command = stripped.Data();
      if (!isParticleDataLine(command))
        continue;
      if (!pythia.readString(command))
        return false;
    }
    return true;
  }

  const bool mOneInjectionPerEvent = true;
  const bool mUseTriggering = false;
  const int mGapBetweenInjection = 0;
  const bool mUseRapidity = false;

  int mConfigToUse = -1;
  int mEventCounter = 0;
  bool mDoSignalThisEvent = true;

  std::vector<ConfigContainer> mGunConfigs;
  std::vector<ConfigContainer> mGunConfigsGenDecayed;
  Pythia8::Pythia pythiaObjectSignal;
  Pythia8::Pythia pythiaObjectMinimumBias;
  Pythia8::Pythia mPythiaGun;
};

FairGenerator *generateLFRapidity(std::string configuration = "",
                                  bool injectOnePDGPerEvent = true,
                                  int gapBetweenInjection = 0,
                                  bool useTrigger = false,
                                  bool useRapidity = false,
                                  std::string pythiaCfgMb = "",
                                  std::string pythiaCfgSignal = "")
{
  std::vector<GeneratorPythia8LFRapidity::ConfigContainer> cfgVec;
  std::vector<GeneratorPythia8LFRapidity::ConfigContainer> cfgVecGenDecayed;

  if (!configuration.empty())
  {
    configuration = gSystem->ExpandPathName(configuration.c_str());
    std::ifstream inputFile(configuration.c_str(), ios::in);
    if (inputFile.is_open() && TString(configuration.c_str()).EndsWith(".json"))
    {
      nlohmann::json paramfile = nlohmann::json::parse(inputFile);
      for (const auto &param : paramfile)
      {
        if (param.value("genDecayed", true))
        {
          cfgVecGenDecayed.push_back(GeneratorPythia8LFRapidity::ConfigContainer{param, useRapidity});
        }
        else
        {
          cfgVec.push_back(GeneratorPythia8LFRapidity::ConfigContainer{param, useRapidity});
        }
      }
    }
  }

  // DEFAULT FALLBACK: If no configuration file passed or empty, default to PDG 10331 Flat Mass PHSP
  if (cfgVec.empty() && cfgVecGenDecayed.empty())
  {
    LOG(info) << "No particle list provided or empty. Falling back to default PDG 10331 (f0(1710)) Flat Mass setup.";
    GeneratorPythia8LFRapidity::ConfigContainer defaultCfg(10331, 1, 0.0, 30.0, -1.0, 1.0, 1.0, 3.0);
    cfgVecGenDecayed.push_back(defaultCfg);
  }

  GeneratorPythia8LFRapidity *multiGun = new GeneratorPythia8LFRapidity(injectOnePDGPerEvent, gapBetweenInjection, useTrigger, useRapidity, pythiaCfgMb, pythiaCfgSignal);
  for (const auto &c : cfgVec)
  {
    multiGun->addGun(c);
  }
  for (const auto &c : cfgVecGenDecayed)
  {
    multiGun->addGunGenDecayed(c);
  }
  return multiGun;
}