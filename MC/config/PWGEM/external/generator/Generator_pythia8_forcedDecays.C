#include "Generators/DecayerPythia8.h"
#include "Generators/GeneratorPythia8.h"
#include "SimulationDataFormat/MCGenProperties.h"
#include "SimulationDataFormat/ParticleStatus.h"
#include "TLorentzVector.h"

namespace o2 {
namespace eventgen {

class DecayerPythia8ForceDecays : public DecayerPythia8 {
public:
  DecayerPythia8ForceDecays(){
    mPythia.readString("Random:setSeed = on");
    char* alien_proc_id = getenv("ALIEN_PROC_ID");
    int seed;
    if (alien_proc_id != NULL) {
      seed = atoi(alien_proc_id);
      LOG(info) << "Seed for DecayerPythia8 set to ALIEN_PROC_ID: " << seed;
    } else {
      LOG(info) << "Unable to retrieve ALIEN_PROC_ID";
      LOG(info) << "Setting seed for DecayerPyhtia8 to 0 (random)";
      seed = 0;
    }
    mPythia.readString("Random:seed = "+std::to_string(seed));
  }
  ~DecayerPythia8ForceDecays() = default;


  void calculateWeights(std::vector<int> &pdgs) {
    TLorentzVector mom = TLorentzVector(0., 0., 0., 9999999.);
    for (int pdg : pdgs) {
      Decay(pdg, &mom); // do one fake decay to initalize everything correctly
      auto particleData = mPythia.particleData.particleDataEntryPtr(pdg);
      double weight = 0.;
      for (int c = 0; c < particleData->sizeChannels(); c++) {
        weight += particleData->channel(c).currentBR();
      }
      LOG(info) << "PDG = " << pdg
                << ": sum of branching ratios of active decay channels = "
                << weight;
      mWeights[pdg] = weight;
      mPythia.particleData.mayDecay(pdg, false);
    }
  }

  void forceDecays(std::vector<TParticle> &mParticles, int mother_pos) {
    TParticle *p = &mParticles[mother_pos];
    int pdg = p->GetPdgCode();
    TLorentzVector mom = TLorentzVector(p->Px(), p->Py(), p->Pz(), p->Energy());
    Decay(pdg, &mom);
    TClonesArray daughters = TClonesArray("TParticle");
    int nParticles = ImportParticles(&daughters);
    int mcGenStatus = o2::mcgenstatus::getGenStatusCode(p->GetStatusCode());
    p->SetStatusCode(o2::mcgenstatus::MCGenStatusEncoding(2, -mcGenStatus).fullEncoding);
    p->SetBit(ParticleStatus::kToBeDone, false);
    double mother_weight = p->GetWeight();
    TParticle *mother = static_cast<TParticle *>(daughters[0]);
    int mParticles_size = mParticles.size();
    p->SetFirstDaughter(mother->GetFirstDaughter() + mParticles_size - 1);
    p->SetLastDaughter(mother->GetLastDaughter() + mParticles_size - 1);
    for (int j = 1; j < nParticles;
         j++) { // start loop at 1 to not include mother
      TParticle *d = static_cast<TParticle *>(daughters[j]);
      double decay_weight = mWeights[abs(pdg)];
      if (decay_weight == 0) {
        LOG(error) << "Decaying particle (PDG = " << pdg
                   << ") with decay weight = 0. Did you set the pdg codes for "
                      "calculating weights correctly?";
      }
      d->SetWeight(decay_weight * mother_weight);
      if (d->GetStatusCode() == 1) {
        d->SetStatusCode(
            o2::mcgenstatus::MCGenStatusEncoding(1, 91).fullEncoding);
        d->SetBit(ParticleStatus::kToBeDone, true);
      } else {
        d->SetStatusCode(
            o2::mcgenstatus::MCGenStatusEncoding(2, -91).fullEncoding);
        d->SetBit(ParticleStatus::kToBeDone, false);
      }
      int firstmother = d->GetFirstMother();
      int firstdaughter = d->GetFirstDaughter();
      int lastdaughter = d->GetLastDaughter();
      if (firstmother == 0) {
        d->SetFirstMother(mother_pos);
        d->SetLastMother(mother_pos);
      } else {
        d->SetFirstMother(firstmother + mParticles_size - 1);
        d->SetLastMother(firstmother + mParticles_size - 1);
      }
      if (firstdaughter == 0) {
        d->SetFirstDaughter(-1);
      } else {
        d->SetFirstDaughter(firstdaughter + mParticles_size - 1);
      }
      if (lastdaughter == 0) {
        d->SetLastDaughter(-1);
      } else {
        d->SetLastDaughter(lastdaughter + mParticles_size - 1);
      }
      mParticles.push_back(*d);
    }
  }

private:
  std::map<int, double> mWeights;
};

class GeneratorPythia8ForcedDecays : public GeneratorPythia8 {

public:
  GeneratorPythia8ForcedDecays(){
    mPythia.readString("Random:setSeed = on");
    char* alien_proc_id = getenv("ALIEN_PROC_ID");
    int seed;
    if (alien_proc_id != NULL) {
      seed = atoi(alien_proc_id);
      LOG(info) << "Seed for GeneratorPythia8 set to ALIEN_PROC_ID: " << seed;
    } else {
      LOG(info) << "Unable to retrieve ALIEN_PROC_ID";
      LOG(info) << "Setting seed for GeneratorPyhtia8 to 0 (random)";
      seed = 0;
    }
    mPythia.readString("Random:seed = "+std::to_string(seed));
  }
  ~GeneratorPythia8ForcedDecays() = default;

  // overriden methods
  bool Init() override { return GeneratorPythia8::Init() && InitDecayer(); };
  bool importParticles() override {
    return GeneratorPythia8::importParticles() && makeForcedDecays();
  };

  void setPDGs(TString pdgs) {
    TObjArray *obj = pdgs.Tokenize(";");
    for (int i = 0; i < obj->GetEntriesFast(); i++) {
      std::string spdg = obj->At(i)->GetName();
      int pdg = std::stoi(spdg);
      mPdgCodes.push_back(pdg);
      LOG(info) << "Force decay of PDG = " << pdg;
    }
  }

protected:
  bool InitDecayer() {
    mDecayer = new DecayerPythia8ForceDecays();
    mDecayer->Init();
    mDecayer->calculateWeights(mPdgCodes);
    for (int pdg : mPdgCodes) {
      mPythia.particleData.mayDecay(pdg, false);
    }
    return true;
  }

  bool makeForcedDecays() {
    int mParticles_size = mParticles.size();
    for (int i = 0; i < mParticles_size; i++) {
      int pdg = mParticles[i].GetPdgCode();
      if (std::find(mPdgCodes.begin(), mPdgCodes.end(), abs(pdg)) !=
          mPdgCodes.end()) {
        mDecayer->forceDecays(mParticles, i);
        mParticles_size = mParticles.size();
      }
    }
    return true;
  }

private:
  DecayerPythia8ForceDecays *mDecayer;
  std::vector<int> mPdgCodes;
};

} // namespace eventgen
} // namespace o2

FairGenerator *GeneratePythia8ForcedDecays(TString pdgs) {
  auto gen = new o2::eventgen::GeneratorPythia8ForcedDecays();
  gen->setPDGs(pdgs);
  return gen;
}