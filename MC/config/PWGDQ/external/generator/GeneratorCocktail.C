#include <vector>

using namespace o2::eventgen;

class GeneratorCocktail : public Generator
{
 public:
  GeneratorCocktail(){};
  ~GeneratorCocktail() = default;

  // at init we init all generators
  bool Init() override
  {
    for (auto& g : *mGenerators)
      g->Init();
    Generator::Init();
    return true;
  };

  // call generate method for all generators
  bool generateEvent() override
  {
    int index = 0;
    for (auto& g : *mGenerators)
      g->generateEvent();
    return true;
  };

  // at importParticles we add particles to the output particle vector
  bool importParticles() override
  {
    for (auto& g : *mGenerators) {
      int nPart = mParticles.size();
      g->importParticles();
      for (auto p : g->getParticles()) {
        mParticles.push_back(p);
        auto& pEdit = mParticles.back();
        o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(pEdit);
        if (pEdit.GetFirstMother() > -1)
          pEdit.SetFirstMother(pEdit.GetFirstMother() + nPart);
        if (pEdit.GetSecondMother() > -1)
          pEdit.SetLastMother(pEdit.GetSecondMother() + nPart);
        if (pEdit.GetFirstDaughter() > -1)
          pEdit.SetFirstDaughter(pEdit.GetFirstDaughter() + nPart);
        if (pEdit.GetLastDaughter() > -1)
          pEdit.SetLastDaughter(pEdit.GetLastDaughter() + nPart);
      }
      g->clearParticles();
    }
    return true;
  };

  void AddGenerator(Generator* gen, int ntimes = 1)
  {
    for (int in = 0; in < ntimes; in++)
      mGenerators->push_back(gen);
    return;
  };

  std::vector<Generator*>* getGenerators()
  {
    return mGenerators;
  };

 private:
  ///
  std::vector<Generator*>* mGenerators = new std::vector<Generator*>(); // vector of Generator
};
