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
            LOG(info) << "**********                           Default number of HF signal events to be merged (updated by notifyEmbedding): " << mNumSigEvs;
            mGeneratorEvHF = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(GeneratorPythia8GapTriggeredCharm(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList));
            break;
        case hf_generators::GapTriggeredBeauty:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapTriggeredBeauty **********";
            LOG(info) << "**********                           Default number of HF signal events to be merged (updated by notifyEmbedding): " << mNumSigEvs;
            mGeneratorEvHF = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(GeneratorPythia8GapTriggeredBeauty(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList));
            break;
        case hf_generators::GapTriggeredCharmAndBeauty:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapTriggeredCharmAndBeauty **********";
            LOG(info) << "**********                           Default number of HF signal events to be merged (updated by notifyEmbedding): " << mNumSigEvs;
            mGeneratorEvHF = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(GeneratorPythia8GapTriggeredCharmAndBeauty(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList));
            break;
        case hf_generators::GapHF:
            LOG(info) << "********** [GeneratorPythia8EmbedHF] configuring GeneratorPythia8GapHF **********";
            LOG(info) << "**********                           Default number of HF signal events to be merged (updated by notifyEmbedding): " << mNumSigEvs;
            mGeneratorEvHF = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(GeneratorPythia8GapHF(/*no gap trigger*/1, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList));
            break;
        default:
            LOG(fatal) << "********** [GeneratorPythia8EmbedHF] bad configuration, fix it! **********";
            break;
        }

        // we set pT hard bins
        auto seed = dynamic_cast<GeneratorPythia8GapTriggeredHF*>(mGeneratorEvHF)->getUsedSeed();
        float ptHardBins[4] = {2.76, 20., 50., 1000.};
        int iPt{0};
        if (seed % 10 < 7) {
            iPt = 0;
        } else if (seed % 10 < 9) {
            iPt = 1;
        } else {
            iPt = 2;
        }
        dynamic_cast<GeneratorPythia8GapTriggeredHF*>(mGeneratorEvHF)->readString(Form("PhaseSpace:pTHatMin = %f", ptHardBins[iPt]));
        dynamic_cast<GeneratorPythia8GapTriggeredHF*>(mGeneratorEvHF)->readString(Form("PhaseSpace:pTHatMax = %f", ptHardBins[iPt+1]));
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

/// @brief Main function for event generation
bool generateEvent() override
{
    /// Overriding that from GeneratorPythia8, to avoid the simulation of an untriggered event as first
    return true;
}

/// @brief Main function to find out whether the particle comes charm or beauty quark
/// @param partId is the index of the particle under study 
/// @param particles are the particles of the full event 
Bool_t isFromCharmOrBeauty(const int partId, std::vector<TParticle> const& particles) {

    // Let's check wheter this is already a c or b quark?
    const TParticle& part = particles.at(partId);
    const int pdgAbs = std::abs(part.GetPdgCode());
    if(pdgAbs == 4 || pdgAbs == 5) {
        return true;
    }
    
    // Let's check the mother particles of the hadron at all stages
    // and look for the charm or beauty quark
    std::vector<std::vector<int64_t>> arrayIds{};
    std::vector<int64_t> initVec{partId};
    arrayIds.push_back(initVec); // the first vector contains the index of the original particle
    int stage = 0;
    while(arrayIds[-stage].size() > 0) {

        LOG(info) << "### stage " << stage << ", arrayIds[-stage].size() = " << arrayIds[-stage].size();

        std::vector<int64_t> arrayIdsStage{};

        for (auto& iPart : arrayIds[-stage]) { // check all the particles that were the mothers at the previous stage
            const TParticle& partStage = particles.at(iPart);

            // check the first mother
            const int firstMotherId = partStage.GetFirstMother();
            if( firstMotherId >= 0) {
                const TParticle& firstMother = particles.at(firstMotherId);
                const int pdgAbsFirstMother = std::abs(firstMother.GetPdgCode());
                if(pdgAbsFirstMother == 4 || pdgAbsFirstMother == 5) {
                    return true;
                }
                // the first mother is not a charm or beauty quark
                arrayIdsStage.push_back(firstMotherId);
            }

            // let's check all other mothers, if any
            const int lastMotherId = partStage.GetSecondMother();
            if(lastMotherId >=0 && lastMotherId != firstMotherId) {
                for(int motherId = firstMotherId+1 /*first mother already considered*/; motherId <= lastMotherId; motherId++) {
                    const TParticle& mother = particles.at(motherId);
                    const int pdgAbsMother = std::abs(mother.GetPdgCode());
                    if(pdgAbsMother == 4 || pdgAbsMother == 5) {
                        return true;
                    }
                    // this mother is not a charm or beauty quark
                    arrayIdsStage.push_back(motherId);
                }
            }

        }

        /*
           All light-flavour mothers are not considered with this approach
           eg: D+ coming from c and uBar --> uBar lost
           --> TODO: check if the current particle has a charm or beauty hadron as daughter. If yes, keep it
           >>> we can ignore it! This might be useful only for jet analyses, however this approach of embedding N pp events into a Pb-Pb one might be not ideal
        */

        // none of the particle mothers is a charm or beauty quark, let's consider their indices for the next stage
        arrayIds.push_back(arrayIdsStage);
        stage--; // ready to go to next stage

    } /// end while(arrayIds[-stage].size() > 0)

    return false;
}


void printParticleVector(std::vector<TParticle> v) {
    for(int id=0; id<v.size(); id++) {
        const int pdgCode = v.at(id).GetPdgCode();
        const int idFirstMother = v.at(id).GetFirstMother();
        const int idLastMother = v.at(id).GetSecondMother();
        LOG(info) << "   id = " << id << ", pdgCode = " << pdgCode << " --> idFirstMother=" << idFirstMother << ", idLastMother=" << idLastMother;
    }
}


int findKey(const std::map<int, int /*index*/>& m, int value) {
    for(std::pair<int, int> p : m) {
        if(p.second /*index*/ == value) {
            return p.first; // key --> it becomes the new index
        }
    }
    return -1;
}


/// @brief Main function to copy the generated particles in mPythia.event into the stack (this.mParticles)
Bool_t importParticles() override
{
  /// Import particles from generated event
  /// This should not do anything now, since we override generateEvent
  GeneratorPythia8::importParticles();

  LOG(info) << "";
  LOG(info) << "*************************************************************";
  LOG(info) << "************** New background event considered **************";
  LOG(info) << "*************************************************************";
  LOG(info) << "";
  
  /// Generate mNumSigEvs HF events to be merged in one
  int nEvsHF = 0;
  while(nEvsHF < mNumSigEvs) {

      /// generate the HF event
      bool genOk = false;
      while(!genOk) {
          genOk = (mGeneratorEvHF->generateEvent() && mGeneratorEvHF->importParticles() /*copy particles from mGeneratorEvHF.mPythia.event to mGeneratorEvHF.mParticles*/ );
      }

      int originalSize = mParticles.size(); // stack of this event generator

      LOG(info) << "";
      LOG(info) << "============ Before HF event " << nEvsHF;
      LOG(info) << "Full stack (size " << originalSize << "):";
      printParticleVector(mParticles);

      /// copy the particles from the HF event in the particle stack
      auto particlesHfEvent = mGeneratorEvHF->getParticles();
      //int originalSize = mParticles.size(); // stack of this event generator
      //int discarded = 0; // for index offset
      /*int kept = 0;*/
      std::map<int, int /*particle id in HF event stack*/> mapHfParticles = {};
      int counterHfParticles = 0;

      LOG(info) << "-----------------------------------------------";
      LOG(info) << ">>> HF event " << nEvsHF;
      LOG(info) << "  HF event stack:";
      printParticleVector(particlesHfEvent);

      for(int iPart=0; iPart<particlesHfEvent.size(); iPart++) {
        auto particle = particlesHfEvent.at(iPart);

        /// Establish if this particle comes from charm or beauty
        /// If not, ignore this particle and increase the number of discarded particles from the pp event
        LOG(info) << "starting isFromCharmOrBeauty";
        if(!isFromCharmOrBeauty(iPart, particlesHfEvent)) {
            LOG(info) << "isFromCharmOrBeauty is over, not interesting particle found";
            //discarded++;
            continue;
        }
        /*kept++;*/
        /// if we arrive here, then the current particle is from charm or beauty, keep it!
        mapHfParticles[counterHfParticles++/*fill and update the counter*/] =iPart;

/*
        LOG(info) << "applying offset";

        /// adjust the particle mother and daughter indices
        int offset = originalSize; //- discarded;
        if(particle.GetFirstMother() >= 0)   particle.SetFirstMother(particle.GetFirstMother() + offset);
        if(particle.GetSecondMother() >= 0)   particle.SetLastMother(particle.GetSecondMother() + offset);
	    if(particle.GetFirstDaughter() >= 0) particle.SetFirstDaughter(particle.GetFirstDaughter() + offset);
	    if(particle.GetLastDaughter() >= 0)  particle.SetLastDaughter(particle.GetLastDaughter() + offset);

        /// copy inside this.mParticles from mGeneratorEvHF.mParticles, i.e. the particles generated in mGeneratorEvHF
        mParticles.push_back(particle);
*/
      }

    
      // In the map we have only the particles from charm or beauty
      // Let's readapt the mother/daughter indices accordingly
      int offset = originalSize;
      for(int iHfPart=0; iHfPart<counterHfParticles; iHfPart++) {
        TParticle& particle = particlesHfEvent.at(mapHfParticles[iHfPart]);
        int idFirstMother = particle.GetFirstMother(); // NB: indices from the HF event stack
        int idLastMother = particle.GetSecondMother(); // NB: indices from the HF event stack
        int idFirstDaughter = particle.GetFirstDaughter(); // NB: indices from the HF event stack
        int idLastDaughter = particle.GetLastDaughter(); // NB: indices from the HF event stack
        const int pdgCode = particle.GetPdgCode();

        /// charm or beauty quark
        /// reset the mothers, and readapt daughter indices
        if(std::abs(pdgCode) == 4 || std::abs(pdgCode) == 5) {
            idFirstMother = -1;
            idLastMother = -1;
            idFirstDaughter = findKey(mapHfParticles, idFirstDaughter);
            idLastDaughter = findKey(mapHfParticles, idLastDaughter);
        }
        /// diquark, or charm or beauty hadron, or their decay products
        /// make first and last mother equal (--> possible other partonic mothers ignored in mapHfParticles), and readapt daughter indices
        else {
            /// fix mother indices
            /// the case with idFirstMother < 0 should never happen at this stage
            if(idFirstMother >= 0) {
                idFirstMother = findKey(mapHfParticles, idFirstMother);
                if(idLastMother != idFirstMother) {

                    if(idLastMother == -1) {
                        /// this particle has just one mother
                        /// let's put idLastMother equal to idFirstMother
                        idLastMother = idFirstMother;
                    } else {
                        /// idLastMother is >= 0
                        /// ASSUMPTION: idLastMother > idFirstMother
                        ///             In principle, the opposite can be true only in partonic processes
                        idLastMother = findKey(mapHfParticles, idLastMother);
                    }

                } else {
                    /// idLastMother is equal to idFirstMother
                    idLastMother = idFirstMother;
                }

            }

            /// fix daughter indices
            idFirstDaughter = findKey(mapHfParticles, idFirstDaughter);
            idLastDaughter = findKey(mapHfParticles, idLastDaughter);
        }

        /// adjust the particle mother and daughter indices
        particle.SetFirstMother(idFirstMother + offset);
        particle.SetLastMother(idLastMother + offset);
	    particle.SetFirstDaughter(idFirstDaughter + offset);
	    particle.SetLastDaughter(idLastDaughter + offset);

        /// copy inside this.mParticles from mGeneratorEvHF.mParticles, i.e. the particles generated in mGeneratorEvHF
        mParticles.push_back(particle);

      }


      LOG(info) << "-----------------------------------------------";
      LOG(info) << "============ After HF event " << nEvsHF;
      LOG(info) << "Full stack:";
      printParticleVector(mParticles);

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

