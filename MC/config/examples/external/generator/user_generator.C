/// \author R+Preghenella - June 2021

// Example of an implementation of a simple user generator
// that injects particles at wish according to predefined setting
// which are defined by configuration strings
// 
//
//   usage: o2sim -g external --configKeyValues 'GeneratorExternal.fileName=user_generator.C;GeneratorExternal.funcName=user_generator("one_proton_and_one_photon")'

#include <string>

using namespace o2::eventgen;

class user_generator_class : public Generator
{
public:
  user_generator_class() { };
  ~user_generator_class() = default;
  void selectConfiguration(std::string val) { mSelectedConfiguration = val; };

  // at init we check that the selected configuration is known
  bool Init() override {
    Generator::Init();
    if (std::find(mKnownConfigurations.begin(), mKnownConfigurations.end(), mSelectedConfiguration) != mKnownConfigurations.end()) {
      std::cout << " --- user_generator initialised with configuration: " << mSelectedConfiguration << std::endl;
      return true;
    }
    std::cout << " --- [ERROR] user_generator has unknown selected configuration: " << mSelectedConfiguration << std::endl;
    return false;
  };

  // it generatrEvent we do nothing
  bool generateEvent() override { return true; };
  
  // at importParticles we add particles to the output particle vector
  // according to the selected configuration
  bool importParticles() override {
    TLorentzVector lv;
    TParticle particle;
    particle.SetFirstMother(-1);
    particle.SetLastMother(-1);
    particle.SetFirstDaughter(-1);
    particle.SetLastDaughter(-1);
    particle.SetStatusCode(1);
    particle.SetProductionVertex(0., 0., 0., 0.);
    if (mSelectedConfiguration.compare("one_proton_and_one_photon") == 0) {
      // one proton
      lv.SetPtEtaPhiM(10., 0.5, M_PI, 0.93827200);
      particle.SetPdgCode(2212);
      particle.SetMomentum(lv);
      mParticles.push_back(particle);
      // one photon
      lv.SetPtEtaPhiM(10., -0.5, M_PI, 0.);
      particle.SetPdgCode(22);
      particle.SetMomentum(lv);
      mParticles.push_back(particle);
      return true;
    }
    if (mSelectedConfiguration.compare("two_protons_and_two_photons") == 0) {
      // one proton
      lv.SetPtEtaPhiM(10., 0.5, M_PI, 0.93827200);
      particle.SetPdgCode(2212);
      particle.SetMomentum(lv);
      mParticles.push_back(particle);
      // another proton
      lv.SetPtEtaPhiM(10., 0.5, -M_PI, 0.93827200);
      particle.SetPdgCode(2212);
      particle.SetMomentum(lv);
      mParticles.push_back(particle);
      // one photon
      lv.SetPtEtaPhiM(10., -0.5, M_PI, 0.);
      particle.SetPdgCode(22);
      particle.SetMomentum(lv);
      mParticles.push_back(particle);
      // another photon
      lv.SetPtEtaPhiM(10., -0.5, -M_PI, 0.);
      particle.SetPdgCode(22);
      particle.SetMomentum(lv);
      mParticles.push_back(particle);
      return true;
    }

    // failure
    return false;
  };

private:

  const std::vector<std::string> mKnownConfigurations = {"one_proton_and_one_photon", "two_protons_and_two_photons"};
  std::string mSelectedConfiguration = "";
  
};

FairGenerator*
user_generator(std::string configuration = "empty")
{
  auto gen = new user_generator_class;
  gen->selectConfiguration(configuration);
  return gen;
}
