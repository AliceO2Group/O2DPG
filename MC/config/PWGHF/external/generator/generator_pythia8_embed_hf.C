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
    /// \param usePtHardBins flag to enable/disable pt-hard bins
    /// \param yQuarkMin minimum quark rapidity
    /// \param yQuarkMax maximum quark rapidity
    /// \param yHadronMin minimum hadron rapidity
    /// \param yHadronMax maximum hadron rapidity
    /// \param hadronPdgList list of PDG codes for hadrons to be used in trigger
    void setupGeneratorEvHF(int genType, bool usePtHardBins, float yQuarkMin, float yQuarkMax, float yHadronMin, float yHadronMax, std::vector<int> hadronPdgList = {}) {
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
        if (usePtHardBins) {
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
        mNumSigEvs = 5 + 0.886202881*std::pow(std::max(0.0f, 17.5f - x),1.7);
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
bool isFromCharmOrBeauty(const int partId, std::vector<TParticle> const& particles) {

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

        //LOG(info) << "### stage " << stage << ", arrayIds[-stage].size() = " << arrayIds[-stage].size();

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
           >>> we can ignore it! This might be useful only for jet analyses, however this approach of embedding N pp events into a Pb-Pb one might be not ideal for them
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
        const int idFirstDaughter = v.at(id).GetFirstDaughter();
        const int idLastDaughter = v.at(id).GetLastDaughter();
        LOG(info) << "   id = " << id << ", pdgCode = " << pdgCode << " --> idFirstMother=" << idFirstMother << ", idLastMother=" << idLastMother << ", idFirstDaughter=" << idFirstDaughter << ", idLastDaughter=" << idLastDaughter;
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
  LOG(info) << "************** New signal event considered **************";
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

      // for debug
      // LOG(info) << "";
      // LOG(info) << "============ Before HF event " << nEvsHF;
      // LOG(info) << "Full stack (size " << originalSize << "):";
      // printParticleVector(mParticles);

      /// copy the particles from the HF event in the particle stack
      auto particlesHfEvent = mGeneratorEvHF->getParticles();
      std::map<int, int /*particle id in HF event stack*/> mapHfParticles = {};
      int counterHfParticles = 0;

      // for debug
      // LOG(info) << "-----------------------------------------------";
      // LOG(info) << ">>> HF event " << nEvsHF;
      // LOG(info) << "  HF event stack:";
      // printParticleVector(particlesHfEvent);

      for(int iPart=0; iPart<particlesHfEvent.size(); iPart++) {
        auto particle = particlesHfEvent.at(iPart);

        /// Establish if this particle comes from charm or beauty
        /// If not, ignore this particle and increase the number of discarded particles from the pp event
        if(!isFromCharmOrBeauty(iPart, particlesHfEvent)) {
            continue;
        }
        /// if we arrive here, then the current particle is from charm or beauty, keep it!
        mapHfParticles[counterHfParticles++/*fill and update the counter*/] = iPart;
      }

      /// print the map (debug)
      // LOG(info) << "   >>>";
      // LOG(info) << "   >>> printing mapHfParticles:";
      // for(auto& p : mapHfParticles) {
      //     const int pdgCodeFromMap = particlesHfEvent.at(p.second).GetPdgCode();
      //     LOG(info) << "   >>>        entry " << p.first << ", original id = " << p.second << ", pdgCode=" << pdgCodeFromMap << " --> firstMotherId=" << particlesHfEvent.at(p.second).GetFirstMother() << ", lastMotherId=" << particlesHfEvent.at(p.second).GetSecondMother() << ", firstDaughterId=" << particlesHfEvent.at(p.second).GetFirstDaughter() << ", lastDaughterId=" << particlesHfEvent.at(p.second).GetLastDaughter();
      // }

    
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

        /// fix mother indices
        bool isFirstMotherOk = false;
        const int idFirstMotherOrig = idFirstMother; /// useful only if the 1st mother is not charm or beauty
        if(idFirstMother >= 0) {
            idFirstMother = findKey(mapHfParticles, idFirstMother);
            /// If idFirstMother>=0, the 1st mother is from charm or beauty, i.e. is not a light-flavoured parton
            /// Instead, if idFirstMother==-1 from findKey this means that the first mother was a light-flavoured parton --> not stored in the map
            if(idFirstMother >=0) {
                /// the 1st mother is from charm or beauty, i.e. is not a light-flavoured parton
                if(idLastMother != idFirstMotherOrig) {
                    if(idLastMother != -1) {
                        /// idLastMother is >= 0
                    }
                } else {
                    /// idLastMother is equal to idFirstMother
                    idLastMother = idFirstMother;
                }
                isFirstMotherOk = true;
            }
        }
        if(!isFirstMotherOk) {
            /// - If we are here, it means that the 1st mother was not from charm or beauty
            /// - No need to check whether idLastMother>=0,
            ///   because this would mean that none of the mother is from charm or beauty and this was checked already in isFromCharmOrBeauty
            /// - Need to loop between 1st and last mother, to treat cases like these
            /// [11:52:13][INFO]    id = 565, pdgCode = -2 --> idFirstMother=519, idLastMother=519
            /// [11:52:13][INFO]    id = 566, pdgCode = -4 --> idFirstMother=520, idLastMother=520
            /// [11:52:13][INFO]    id = 567, pdgCode = -1 --> idFirstMother=518, idLastMother=518
            /// [11:52:13][INFO]    id = 568, pdgCode = -311 --> idFirstMother=565, idLastMother=567
            /// [11:52:13][INFO]    id = 569, pdgCode = -4212 --> idFirstMother=565, idLastMother=567
            /// --> w/o loop between 1st and last mother, the mother Ids assigned to this Sc+ (4212) by findKey are -1, both first and last   
            bool foundAnyMother = false;
            for(int idMotherOrig=(idFirstMotherOrig+1); idMotherOrig<=idLastMother; idMotherOrig++) {
                const int idMother = findKey(mapHfParticles, idMotherOrig);
                if(idMother >= 0) {
                    /// this should mean that the mother is from HF, i.e. that we found the correct one
                    idFirstMother = idMother;
                    idLastMother = idFirstMother;
                    foundAnyMother = true;
                    break;
                }
            }
            // set last mother to -1 if no mother has been found so far
            if (!foundAnyMother) {
                idLastMother = -1;
            }
        }

        /// fix daughter indices
        idFirstDaughter = findKey(mapHfParticles, idFirstDaughter);
        idLastDaughter = findKey(mapHfParticles, idLastDaughter);

        /// adjust the particle mother and daughter indices
        particle.SetFirstMother((idFirstMother >= 0) ? idFirstMother + offset : idFirstMother);
        particle.SetLastMother((idLastMother >= 0) ? idLastMother + offset : idLastMother);
	    particle.SetFirstDaughter((idFirstDaughter >= 0) ? idFirstDaughter + offset : idFirstDaughter);
	    particle.SetLastDaughter((idLastDaughter >= 0) ? idLastDaughter + offset : idLastDaughter);

        /// copy inside this.mParticles from mGeneratorEvHF.mParticles, i.e. the particles generated in mGeneratorEvHF
        mParticles.push_back(particle);

      }

      // for debug
      // LOG(info) << "-----------------------------------------------";
      // LOG(info) << "============ After HF event " << nEvsHF;
      // LOG(info) << "Full stack:";
      // printParticleVector(mParticles);

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
FairGenerator * GeneratorPythia8EmbedHFCharm(bool usePtHardBins = false, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF();

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredCharm, usePtHardBins, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}

// Beauty enriched
FairGenerator * GeneratorPythia8EmbedHFBeauty(bool usePtHardBins = false, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF();

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredBeauty, usePtHardBins, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}

// Charm and beauty enriched (with same ratio)
FairGenerator * GeneratorPythia8EmbedHFCharmAndBeauty(bool usePtHardBins = false, float yQuarkMin = -1.5, float yQuarkMax = 1.5, float yHadronMin = -1.5, float yHadronMax = 1.5, std::vector<int> hadronPdgList = {})
{
    auto myGen = new GeneratorPythia8EmbedHF();

    /// setup the internal generator for HF events
    myGen->setupGeneratorEvHF(hf_generators::GapTriggeredCharmAndBeauty, usePtHardBins, yQuarkMin, yQuarkMax, yHadronMin, yHadronMax, hadronPdgList);

    return myGen;
}

