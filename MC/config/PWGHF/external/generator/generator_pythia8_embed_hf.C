///////////////////////////////////////////////////////////////////////////////
///                                                                         ///
///  HF MC generator for Pb-Pb                                              ///
///  Option 1: generate N PYTHIA events triggered on ccbar and/or bbbar     ///
///            to be embedded with a underlying Pb-Pb event                 ///
///                                                                         ///
///////////////////////////////////////////////////////////////////////////////

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
    //GeneratorPythia8EmbedHF(int numSigEvs = 1) {
    //    mNumSigEvs = numSigEvs;
    //    //mGeneratedEvents = 0;
    //}

    ///  Destructor
    ~GeneratorPythia8EmbedHF() = default;

    /// Init
    bool Init() override
    {
      return o2::eventgen::GeneratorPythia8::Init();
    }

    /// @brief setup the event generator for HF signals
    /// \param gentype generator type (only ccbar, only bbbar, both)
    /// \param yQuarkMin minimum quark rapidity
    /// \param yQuarkMax maximum quark rapidity
    /// \param yHadronMin minimum hadron rapidity
    /// \param yHadronMax maximum hadron rapidity
    /// \param hadronPdgList list of PDG codes for hadrons to be used in trigger
    void setupGeneratorEvHF(int genType, float yQuarkMin, float yQuarkMax, float yHadronMin, float yHadronMax, std::vector<int> hadronPdgList = {}) {
        mGeneratorEvHF = nullptr;
        switch (genType)
        {
        case hf_generators::GapTriggeredCharm:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapTriggeredCharm **********";
            LOG(info) << "**********                           number of HF signal events to be merged: " << mNumSigEvs;
            mGeneratorEvHF = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(GeneratorPythia8GapTriggeredCharm(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList));
            break;
        case hf_generators::GapTriggeredBeauty:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapTriggeredBeauty **********";
            LOG(info) << "**********                           number of HF signal events to be merged: " << mNumSigEvs;
            mGeneratorEvHF = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(GeneratorPythia8GapTriggeredBeauty(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList));
            break;
        case hf_generators::GapTriggeredCharmAndBeauty:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapTriggeredCharmAndBeauty **********";
            LOG(info) << "**********                           number of HF signal events to be merged: " << mNumSigEvs;
            mGeneratorEvHF = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(GeneratorPythia8GapTriggeredCharmAndBeauty(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList));
            break;
        case hf_generators::GapHF:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapHF **********";
            LOG(info) << "**********                           number of HF signal events to be merged: " << mNumSigEvs;
            mGeneratorEvHF = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(GeneratorPythia8GapHF(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList));
            break;
        default:
            LOG(fatal) << "********** [GeneratorPythia8EmbedHF] bad configuration, fix it! **********";
            break;
        }
        mGeneratorEvHF->Init();
    }

    // This function is called by the primary generator
    // for each event in case we are in embedding mode.
    // We use it to setup the number of signal events
    // to be generated and to be embedded on the background.
    void notifyEmbedding(const o2::dataformats::MCEventHeader* bkgHeader) override
    {
        LOG(info) << "[notifyEmbedding] ----- Function called";
        
        /// Impact parameter between the two nuclei
        const float x = bkgHeader->GetB();
        LOG(info) << "[notifyEmbedding] ----- Collision impact parameter: " << x;

        /// number of events to be embedded in a background event
        mNumSigEvs = std::max(1.,120.*(x<5.)+80.*(1.-x/20.)*(x>5.)*(x<11.)+240.*(1.-x/13.)*(x>11.));
        LOG(info) << "[notifyEmbedding] ----- generating " << mNumSigEvs << " signal events " << std::endl;
    };

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
          genOk = (mGeneratorEvHF->generateEvent() && mGeneratorEvHF->importParticles() /*copy particles from mGeneratorEvHF.mPythia.event to mGeneratorEvHF.mParticles*/ );
      }

      /// copy the particles from the HF event in the particle stack
      auto particlesHfEvent = mGeneratorEvHF->getParticles();
      int originalSize = mParticles.size(); // stack of this event generator
      for(int iPart=0; iPart<particlesHfEvent.size(); iPart++) {
        auto particle = particlesHfEvent.at(iPart);

        /// adjust the particle mother and daughter indices
        if(particle.GetFirstMother() >= 0)   particle.SetFirstMother(particle.GetFirstMother() + originalSize);
	    if(particle.GetFirstDaughter() >= 0) particle.SetFirstDaughter(particle.GetFirstDaughter() + originalSize);
	    if(particle.GetLastDaughter() >= 0)  particle.SetLastDaughter(particle.GetLastDaughter() + originalSize);

        /// copy inside this.mParticles from mGeneratorEvHF.mParticles, i.e. the particles generated in mGeneratorEvHF
        mParticles.push_back(particle);
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
    
    int mNumSigEvs{1}; // number of HF signal events to be merged in one Pythia event
    //unsigned long long mGeneratedEvents;

};

// Charm enriched
FairGenerator * GeneratorPythia8EmbedHFCharm(float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF();

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredCharm, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}

// Beauty enriched
FairGenerator * GeneratorPythia8EmbedHFBeauty(float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF();

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredBeauty, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}

// Charm and beauty enriched (with same ratio)
FairGenerator * GeneratorPythia8EmbedHFCharmAndBeauty(float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF();

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredCharmAndBeauty, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}