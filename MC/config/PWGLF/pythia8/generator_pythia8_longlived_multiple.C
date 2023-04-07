///
/// \file   generator_pythia8_longlived_multiple.C
/// \author Nicolò Jacazio nicolo.jacazio@cern.ch
/// \since  05/08/2022
/// \brief  Implementation of a gun generator for multiple particles, built on generator_pythia8_longlived.C
///         Needs PDG, Number of injected, minimum and maximum pT. These can be provided in three ways, bundeling variables, particles or from input file
///         usage:
///               `o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_longlived_multiple.C;GeneratorExternal.funcName=generateLongLivedMultiple({1000010020, 1000010030}, {10, 10}, {0.5, 0.5}, {10, 10})'`
///               Here PDG, Number injected, pT limits are separated and matched by index
///         or:
///               `o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_longlived_multiple.C;GeneratorExternal.funcName=generateLongLivedMultiple({{1000010020, 10, 0.5, 10}, {1000010030, 10, 0.5, 10}})'`
///               Here PDG, Number injected, pT limits are separated are divided per particle
///         or:
///               `o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_longlived_multiple.C;GeneratorExternal.funcName=generateLongLivedMultiple("${O2DPG_ROOT}/MC/config/PWGLF/pythia8/generator/particlelist.gun")'`
///               Here PDG, Number injected, pT limits are provided via an intermediate configuration file
///

#include "generator_pythia8_longlived.C"
#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "SimulationDataFormat/MCGenStatus.h"
#include "SimulationDataFormat/MCUtils.h"
#include "fairlogger/Logger.h"
#include "TSystem.h"
#include <fstream>
#endif

using namespace Pythia8;
using namespace o2::mcgenstatus;

class GeneratorPythia8LongLivedGunMultiple : public GeneratorPythia8LongLivedGun
{
 public:
  /// constructor
  GeneratorPythia8LongLivedGunMultiple(bool injOnePerEvent = true) : GeneratorPythia8LongLivedGun{0}, mOneInjectionPerEvent{injOnePerEvent}
  {
  }

  ///  Destructor
  ~GeneratorPythia8LongLivedGunMultiple() = default;

  int mConfigToUse = -1;
  int mEventCounter = 0;
  //__________________________________________________________________
  Bool_t generateEvent() override
  {
    LOG(info) << "generateEvent" << mEventCounter;
    if (!mPythia.next()) {
      return false;
    }

    mConfigToUse = mOneInjectionPerEvent ? static_cast<int>(gRandom->Uniform(0.f, getNGuns())) : -1;
    LOGF(info, "Using configuration %i out of %lli, %lli transport decayed, %lli generator decayed", mConfigToUse, getNGuns(), mGunConfigs.size(), mGunConfigsGenDecayed.size());

    int nConfig = mGunConfigs.size(); // We start counting from the configurations of the transport decayed particles
    for (const ConfigContainer& cfg : mGunConfigsGenDecayed) {
      if (mConfigToUse >= 0 && nConfig != mConfigToUse) {
        nConfig++;
        continue;
      }

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
        particle.status(MCGenStatusEncoding(1, 1).fullEncoding);
        particle.status(11);
        particle.m(cfg.mass);
        particle.px(px);
        particle.py(py);
        particle.pz(pz);
        particle.e(et);
        particle.xProd(0.f);
        particle.yProd(0.f);
        particle.zProd(0.f);
        LOG(info) << "Appending particle " << i << " pdg = " << particle.id;
        mPythia.event.append(particle);
      }
    }
    mPythia.next();
    mPythia.stat();
    return true;
  }

  //__________________________________________________________________
  Bool_t importParticles() override
  {
    LOG(info) << "importParticles " << mEventCounter++;
    GeneratorPythia8::importParticles();
    int nConfig = 0;
    for (const ConfigContainer& cfg : mGunConfigs) {
      if (mConfigToUse >= 0 && nConfig != mConfigToUse) {
        nConfig++;
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
    if (1) {
      int nP = 0;
      for (const auto& p : mParticles) {
        LOG(info) << "Particle " << nP++ << " " << p.Px() << " " << p.Py() << " " << p.Pz() << " " << p.Energy() << " " << p.GetPdgCode();
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
    LOG(info) << "GeneratorPythia8LongLivedGunMultiple configuration with " << getNGuns() << " guns:";
    LOG(info) << "Particles decayed by the transport:";
    for (const auto& cfg : mGunConfigs) {
      cfg.print();
    }
    LOG(info) << "Particles decayed by the generator:";
    for (const auto& cfg : mGunConfigsGenDecayed) {
      cfg.print();
    }
  }

 private:
  const bool mOneInjectionPerEvent = true;            // if true, only one injection per event is performed, i.e. if multiple PDG (including antiparticles) are requested to be injected only one will be done per event
  std::vector<ConfigContainer> mGunConfigs;           // List of gun configurations to use
  std::vector<ConfigContainer> mGunConfigsGenDecayed; // List of gun configurations to use that will be decayed by the generator
};

///___________________________________________________________
/// Create generator via arrays of entries
FairGenerator* generateLongLivedMultiple(std::vector<int> PDGs, std::vector<int> nInject, std::vector<float> ptMin, std::vector<float> ptMax)
{
  const std::vector<unsigned long> entries = {PDGs.size(), nInject.size(), ptMin.size(), ptMax.size()};
  if (!std::equal(entries.begin() + 1, entries.end(), entries.begin())) {
    LOGF(fatal, "Not equal number of entries, check configuration");
    return nullptr;
  }
  GeneratorPythia8LongLivedGunMultiple* multiGun = new GeneratorPythia8LongLivedGunMultiple();
  for (unsigned long i = 0; i < entries[0]; i++) {
    multiGun->addGun(PDGs[i], nInject[i], ptMin[i], ptMax[i]);
  }
  return multiGun;
}

///___________________________________________________________
/// Create generator via an array of configurations
FairGenerator* generateLongLivedMultiple(std::vector<GeneratorPythia8LongLivedGunMultiple::ConfigContainer> cfg,
                                         std::vector<GeneratorPythia8LongLivedGunMultiple::ConfigContainer> cfgGenDecayed)
{
  GeneratorPythia8LongLivedGunMultiple* multiGun = new GeneratorPythia8LongLivedGunMultiple();
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
FairGenerator* generateLongLivedMultiple(std::string configuration = "${O2DPG_ROOT}/MC/config/PWGLF/pythia8/generator/particlelist.gun")
{
  configuration = gSystem->ExpandPathName(configuration.c_str());
  LOGF(info, "Using configuration file '%s'", configuration.c_str());
  std::ifstream inputFile(configuration.c_str(), ios::in);
  std::vector<GeneratorPythia8LongLivedGunMultiple::ConfigContainer> cfgVec;
  std::vector<GeneratorPythia8LongLivedGunMultiple::ConfigContainer> cfgVecGenDecayed;
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
        cfgVecGenDecayed.push_back(GeneratorPythia8LongLivedGunMultiple::ConfigContainer{line.Tokenize(" ")});
      } else {
        cfgVec.push_back(GeneratorPythia8LongLivedGunMultiple::ConfigContainer{line.Tokenize(" ")});
      }
    }
  } else {
    LOGF(fatal, "Can't open '%s' !", configuration.c_str());
    return nullptr;
  }
  return generateLongLivedMultiple(cfgVec, cfgVecGenDecayed);
}

///___________________________________________________________
void generator_pythia8_longlived_multiple()
{
  Printf("Compiled correctly!");
}
