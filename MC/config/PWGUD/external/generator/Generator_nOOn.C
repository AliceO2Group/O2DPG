R__LOAD_LIBRARY(NeutronGenerator_cxx.so)
#include "GeneratorStarlight.C"
#include "NeutronGenerator.h"

class Generator_nOOn_class : public o2::eventgen::GeneratorStarlight_class
{
public:
  /// constructor
  Generator_nOOn_class(){};
  ///  Destructor
  ~Generator_nOOn_class() = default;

  bool Init() override
  {
    GeneratorStarlight_class::Init();
	mNeutronGen = new NeutronGenerator();
    mNeutronGen->SetRapidityCut(-6.0,6.0);

    float beam1energy = TMath::Sqrt(Double_t(projZ)/projA*targA/targZ)*eCM/2;
    float gamma1  = beam1energy/0.938272;
    mNeutronGen->SetRunMode(NeutronGenerator::kInterface);
    mNeutronGen->SetBeamParameters(NeutronGenerator::kPb208,gamma1);
    mNeutronGen->SetDataPath(gSystem->ExpandPathName("$nOOn_ROOT/include/Data/"));
    mNeutronGen->Initialize();
    mNeutronGen->Setup();
    return true;
  }

  bool generateEvent() override
  {
    GeneratorStarlight_class::generateEvent();
    mNeutronGen->GenerateEvent(getPhotonEnergy());
    return true;
  }

  bool importParticles() override
  {
    GeneratorStarlight_class::importParticles();

    mNeutrons = mNeutronGen->ImportParticles();
    for(Int_t i = 0; i<mNeutrons->GetEntriesFast(); i++){
      mParticles.push_back(*(TParticle*)(mNeutrons->At(i)));
      o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back(), true);
    }
    mNeutronGen->FinishEvent();
    mNeutrons->Clear("C");
    return true;
  }


private:
   NeutronGenerator *mNeutronGen = 0x0;
   TClonesArray *mNeutrons = 0x0;

};

///___________________________________________________________
FairGenerator *Generator_nOOn(std::string configuration = "empty",float energyCM = 5020, int beam1Z = 82, int beam1A = 208, int beam2Z = 82, int beam2A = 208, std::string extrapars = "")
{
  auto gen = new Generator_nOOn_class();
  gen->selectConfiguration(configuration);
  gen->setCollisionSystem(energyCM, beam1Z, beam1A, beam2Z, beam2A);
  gen->setExtraParams(extrapars);
  return gen;
}
