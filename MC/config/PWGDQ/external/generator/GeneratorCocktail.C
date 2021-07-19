#include <vector>

using namespace o2::eventgen;


class GeneratorCocktail_class : public Generator
{
public:
  GeneratorCocktail_class() { };
  ~GeneratorCocktail_class() = default;

  // at init we init all generators
  bool Init() override {
    for (auto& g : *mEntries)  g->Init(); 
    Generator::Init();
    return true;
  };

  // call generate method for all generators
  bool generateEvent() override {  
         int index = 0;
	 for (auto& g : *mEntries)  g->generateEvent();
	    return true; };

  // at importParticles we add particles to the output particle vector
  bool importParticles() override { 
    for (auto& g : *mEntries) { 
     g->importParticles();
     for (auto& p : g->getParticles()) mParticles.push_back(p); 
     g->clearParticles();
    }
    return true;
  };

void AddGenerator(Generator *gen, int ntimes=1){
	for(int in=0; in<ntimes; in++) mEntries->push_back(gen);
	return;
	};

private:
  ///
  std::vector<Generator*> *mEntries = new  std::vector<Generator*>(); // vector of Generator
};

