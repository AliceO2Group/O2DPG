///
/// \file   generator_pythia8_longlived_multiple.C
/// \author Nicolò Jacazio nicolo.jacazio@cern.ch
/// \brief  Implementation of a gun generator for multiple particles, built on generator_pythia8_longlived.C
///         usage:
///               o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_longlived_multiple.C;GeneratorExternal.funcName=generateLongLivedMultiple({1010010030}, {10}, {0.5}, {10})'
///         or:
///               o2-sim -g external --configKeyValues 'GeneratorExternal.fileName=generator_pythia8_longlived_multiple.C;GeneratorExternal.funcName=generateLongLivedMultiple({{1010010030, 10, 0.5, 10}})'
///

#include "generator_pythia8_longlived.C"
#include "TSystem.h"
#include <fstream>

using namespace Pythia8;

class GeneratorPythia8LongLivedGunMultiple : public GeneratorPythia8LongLivedGun
{
 public:
  /// constructor
  GeneratorPythia8LongLivedGunMultiple() : GeneratorPythia8LongLivedGun{0}
  {
  }

  ///  Destructor
  ~GeneratorPythia8LongLivedGunMultiple() = default;

  //__________________________________________________________________
  Bool_t importParticles() override
  {
    GeneratorPythia8::importParticles();
    for (const ConfigContainer& cfg : gunConfigs) {
      for (int i{0}; i < cfg.nInject; ++i) {
        const double pt = gRandom->Uniform(cfg.ptMin, cfg.ptMax);
        const double eta = gRandom->Uniform(cfg.etaMin, cfg.etaMax);
        const double phi = gRandom->Uniform(0, TMath::TwoPi());
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double pz{pt * std::sinh(eta)};
        const double et{std::hypot(std::hypot(pt, pz), cfg.mass)};
        mParticles.push_back(TParticle(cfg.pdg, 1, -1, -1, -1, -1, px, py, pz, et, 0., 0., 0., 0.));
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
      Printf("int pdg = %i", pdg);
      Printf("int nInject = %i", nInject);
      Printf("float ptMin = %f", ptMin);
      Printf("float ptMax = %f", ptMax);
      Printf("float etaMin = %f", etaMin);
      Printf("float etaMax = %f", etaMax);
      Printf("double mass = %f", mass);
    }
  };

  //__________________________________________________________________
  ConfigContainer addGun(int input_pdg, int nInject = 1, float ptMin = 1, float ptMax = 10)
  {
    ConfigContainer cfg{input_pdg, nInject, ptMin, ptMax};
    gunConfigs.push_back(cfg);
    return cfg;
  }

  //__________________________________________________________________
  ConfigContainer addGun(ConfigContainer cfg) { return addGun(cfg.pdg, cfg.nInject, cfg.ptMin, cfg.ptMax); }

 private:
  std::vector<ConfigContainer> gunConfigs; // List of gun configurations to use
};

///___________________________________________________________
/// Create generator via arrays of entries
FairGenerator* generateLongLivedMultiple(std::vector<int> PDGs, std::vector<int> nInject, std::vector<float> ptMin, std::vector<float> ptMax)
{
  const std::vector<unsigned long> entries = {PDGs.size(), nInject.size(), ptMin.size(), ptMax.size()};
  if (!std::equal(entries.begin() + 1, entries.end(), entries.begin())) {
    Printf("Not equal number of entries, check configuration");
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
FairGenerator* generateLongLivedMultiple(std::vector<GeneratorPythia8LongLivedGunMultiple::ConfigContainer> cfg)
{
  if (cfg.size() == 1) {
    return new GeneratorPythia8LongLivedGun(cfg[0].pdg, cfg[0].nInject, cfg[0].ptMin, cfg[0].ptMax);
  }
  GeneratorPythia8LongLivedGunMultiple* multiGun = new GeneratorPythia8LongLivedGunMultiple();
  for (const auto& c : cfg) {
    Printf("Adding gun");
    c.print();
    multiGun->addGun(c);
  }
  return multiGun;
}

///___________________________________________________________
/// Create generator via input file
FairGenerator* generateLongLivedMultiple(std::string configuration = "${O2DPG_ROOT}/MC/config/PWGLF/pythia8/generator/particlelist.gun")
{
  configuration = gSystem->ExpandPathName(configuration.c_str());
  Printf("Using configuration file '%s'", configuration.c_str());
  std::ifstream inputFile(configuration.c_str(), ios::in);
  std::vector<GeneratorPythia8LongLivedGunMultiple::ConfigContainer> cfgVec;
  if (inputFile.is_open()) {
    std::string l;
    int n = 0;
    while (getline(inputFile, l)) {
      TString line = l;
      line.Strip(TString::kBoth, ' ');

      std::cout << n++ << " " << line << endl;
      if (line.BeginsWith("#")) {
        std::cout << "Skipping\n";
        continue;
      }

      GeneratorPythia8LongLivedGunMultiple::ConfigContainer cfg(line.Tokenize(" "));
      cfgVec.push_back(cfg);
    }
  } else {
    Printf("ERROR: can't open '%s'", configuration.c_str());
    return nullptr;
  }
  return generateLongLivedMultiple(cfgVec);
}

///___________________________________________________________
void generator_pythia8_longlived_multiple()
{
  Printf("Compiled correctly!");
}
