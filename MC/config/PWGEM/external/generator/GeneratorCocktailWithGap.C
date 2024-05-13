#include <vector>

using namespace o2::eventgen;

// This is to evaluate MC efficiency. Not for comparison between data and LMEE cocktail.
class GeneratorCocktailWithGap : public Generator
{
 public:
   GeneratorCocktailWithGap() : Generator() {
     lGeneratedEvents = 0;
     lInverseTriggerRatio = 1;
     mGeneratorsSig->clear();
     mGeneratorsGap->clear();
     mGeneratorsSig->shrink_to_fit();
     mGeneratorsGap->shrink_to_fit();
   };

   GeneratorCocktailWithGap(int lInputTriggerRatio) : Generator() {
     lGeneratedEvents = 0;
     lInverseTriggerRatio = lInputTriggerRatio;
     mGeneratorsSig->clear();
     mGeneratorsGap->clear();
     mGeneratorsSig->shrink_to_fit();
     mGeneratorsGap->shrink_to_fit();
   };

  ~GeneratorCocktailWithGap() = default;

  // at init we init all generators
  bool Init() override
  {
    for (auto& g : *mGeneratorsSig) {
      g->Init();
    }
    for (auto& g : *mGeneratorsGap) {
      g->Init();
    }

    Generator::Init();
    return true;
  };

  void setInputTriggerRatio(int lInputTriggerRatio) { lInverseTriggerRatio = lInputTriggerRatio; };

  // call generate method for all generators
  bool generateEvent() override
  {
    // Simple straightforward check to alternate generators
    if (lGeneratedEvents % lInverseTriggerRatio == 0) {
      // Generate event of interest
      printf("generate signal event %lld\n", lGeneratedEvents);
      for (auto& g : *mGeneratorsSig){
        printf("generate signal event %s\n", g->GetName());
        bool isOK = g->generateEvent();
      }
    } else {
      // Generate gap event
      printf("generate gap event %lld\n", lGeneratedEvents);
      for (auto& g : *mGeneratorsGap){
        printf("generate gap event %s\n", g->GetName());
        bool isOK = g->generateEvent();
      }
    }
    lGeneratedEvents++;
    return true;
  };

  // at importParticles we add particles to the output particle vector
  bool importParticles() override
  {
    //note that lGeneratedEvents++ is called in generateEvent();
    if ((lGeneratedEvents-1) % lInverseTriggerRatio == 0) {
      for (auto& g : *mGeneratorsSig) {
        int nPart = mParticles.size();
        g->importParticles();
        printf("generator %s : ngen = %zu\n", g->GetName(), g->getParticles().size());
        for (auto p : g->getParticles()) {
          mParticles.push_back(p);
          auto& pEdit = mParticles.back();
          o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(pEdit);

          if (pEdit.GetFirstMother() > -1){
            pEdit.SetFirstMother(pEdit.GetFirstMother() + nPart);
          }
          if (pEdit.GetSecondMother() > -1){
            pEdit.SetLastMother(pEdit.GetSecondMother() + nPart);
          }
          if (pEdit.GetFirstDaughter() > -1){
            pEdit.SetFirstDaughter(pEdit.GetFirstDaughter() + nPart);
          }
          if (pEdit.GetLastDaughter() > -1){
            pEdit.SetLastDaughter(pEdit.GetLastDaughter() + nPart);
          }
        }
        g->clearParticles();
      }
    } else {
      for (auto& g : *mGeneratorsGap) {
        int nPart = mParticles.size();
        g->importParticles();
        printf("generator %s : ngen = %zu\n", g->GetName(), g->getParticles().size());
        for (auto p : g->getParticles()) {
          mParticles.push_back(p);
          auto& pEdit = mParticles.back();
          o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(pEdit);

          if (pEdit.GetFirstMother() > -1){
            pEdit.SetFirstMother(pEdit.GetFirstMother() + nPart);
          }
          if (pEdit.GetSecondMother() > -1){
            pEdit.SetLastMother(pEdit.GetSecondMother() + nPart);
          }
          if (pEdit.GetFirstDaughter() > -1){
            pEdit.SetFirstDaughter(pEdit.GetFirstDaughter() + nPart);
          }
          if (pEdit.GetLastDaughter() > -1){
            pEdit.SetLastDaughter(pEdit.GetLastDaughter() + nPart);
          }
        }
        g->clearParticles();
      }
    }

    //maybe, it is better to implement mParticle.shrink_to_fit() in Generator::clearParticles();

    return true;
  };

  void addGeneratorSig(Generator* gen, int ntimes = 1) {
    for (int in = 0; in < ntimes; in++){
      mGeneratorsSig->push_back(gen);
    }
  };
  void addGeneratorGap(Generator* gen, int ntimes = 1) {
    for (int in = 0; in < ntimes; in++){
      mGeneratorsGap->push_back(gen);
    }
  };

  std::vector<Generator*>* getGeneratorsSig() { return mGeneratorsSig; };
  std::vector<Generator*>* getGeneratorsGap() { return mGeneratorsGap; };

 private:
  // Control gap-triggering
  Long64_t lGeneratedEvents;
  int lInverseTriggerRatio;
  std::vector<Generator*>* mGeneratorsSig = new std::vector<Generator*>(); // vector of Generator for signal
  std::vector<Generator*>* mGeneratorsGap = new std::vector<Generator*>(); // vector of Generator for gap
};
