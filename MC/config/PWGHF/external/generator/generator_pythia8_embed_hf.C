#include "generator_pythia8_gaptriggered_hf.C"

using namespace Pythia8;

namespace hf_generators
{
    enum GenType : int {
        GapTriggeredCharm = 0,      // --> GeneratorPythia8GapTriggeredCharm: charm enriched
        GapTriggeredBeauty,         // --> GeneratorPythia8GapTriggeredBeauty: beauty enriched
        GapTriggeredCharmAndBeauty, // --> GeneratorPythia8GapTriggeredCharmAndBeauty: charm and beauty enriched (with same ratio)
        GapHF,                      // --> GeneratorPythia8GapHF
        NGenType
    };
}

class GeneratorPythia8EmbedHF : public o2::eventgen::GeneratorPythia8
{
public:

    /// default constructor
    GeneratorPythia8EmbedHF() = default;

    /// constructor
    GeneratorPythia8EmbedHF(int numSigEvs = 1) {
        mNumSigEvs = numSigEvs;
        //mGeneratedEvents = 0;
    }

    ///  Destructor
    ~GeneratorPythia8EmbedHF() = default;

    /// Init
    bool Init() override
    {
      return o2::eventgen::GeneratorPythia8::Init();
    }

    /// setters
    void setupGeneratorEvHF(int genType, float yQuarkMin, float yQuarkMax, float yHadronMin, float yHadronMax, std::vector<int> hadronPdgList = {}) {
        mGeneratorEvHF = nullptr;
        switch (genType)
        {
        case hf_generators::GapTriggeredCharm:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapTriggeredCharm **********";
            LOG(info) << "**********                           number of HF signal events to be merged: " << mNumSigEvs;
            mGeneratorEvHF = new GeneratorPythia8GapTriggeredCharm(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);
            break;
        case hf_generators::GapTriggeredBeauty:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapTriggeredBeauty **********";
            LOG(info) << "**********                           number of HF signal events to be merged: " << mNumSigEvs;
            mGeneratorEvHF = new GeneratorPythia8GapTriggeredBeauty(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);
            break;
        case hf_generators::GapTriggeredCharmAndBeauty:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapTriggeredCharmAndBeauty **********";
            LOG(info) << "**********                           number of HF signal events to be merged: " << mNumSigEvs;
            mGeneratorEvHF = new GeneratorPythia8GapTriggeredCharmAndBeauty(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);
            break;
        case hf_generators::GapHF:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapHF **********";
            LOG(info) << "**********                           number of HF signal events to be merged: " << mNumSigEvs;
            mGeneratorEvHF = new GeneratorPythia8GapHF(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);
            break;
        default:
            LOG(fatal) << "********** [GeneratorPythia8EmbedHF] bad configuration, fix it! **********";
            break;
        }
        mGeneratorEvHF->Init();
    }

protected:

Bool_t importParticles() override
{
  /// import particles from underlying event
  GeneratorPythia8::importParticles();
  
  /// Generate mNumSigEvs HF events to be merged in one
  int nEvsHF = 0;
  while(nEvsHF < mNumSigEvs) {

      /// generate the HF event
      bool genOk = false;
      while(!genOk) {
          genOk = (mGeneratorEvHF->generateEvent());
      }

      /// copy the particles from the HF event in the particle stack
      auto particlesHfEvent = mGeneratorEvHF->getParticles();
      for(int iPart=0; iPart<=particlesHfEvent.size(); iPart++) {
        mParticles.push_back(TParticle(particlesHfEvent.at(iPart)));
      }

      /// one more event generated, let's update the counter and clear it, to allow the next generation
      nEvsHF++;
      //mGeneratedEvents++;
      mGeneratorEvHF->clearParticles();
  }

  return true;
}

private:

    Generator* mGeneratorEvHF; // to generate HF signal events
    
    int mNumSigEvs; // number of HF signal events to be merged in one Pythia event
    //unsigned long long mGeneratedEvents;

};

// Charm enriched
FairGenerator * GeneratorPythia8EmbedHFCharm(int numSigEvs = 1, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF(numSigEvs);

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredCharm, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}

// Beauty enriched
FairGenerator * GeneratorPythia8EmbedHFBeauty(int numSigEvs = 1, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF(numSigEvs);

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredBeauty, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}

// Charm and beauty enriched (with same ratio)
FairGenerator * GeneratorPythia8EmbedHFCharmAndBeauty(int numSigEvs = 1, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF(numSigEvs);

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredCharmAndBeauty, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}