// Example of an implementation of an event generator
// that alternates between 2 gun generators. Serves as example
// to construct any meta-generator (such as cocktails) consisting
// or using a pool of underlying o2::eventgen::Generators.

// Test is using #o2-sim-dpl-eventgen --nEvents 10 --generator external --configKeyValues "GeneratorExternal.fileName=${O2DPG_MC_CONFIG_ROOT}/MC/config/examples/external/generator/SimpleCocktail.C;GeneratorExternal.funcName=getSimpleGap()"

namespace o2
{
namespace eventgen
{


/// A very simple gap generator alternating between 2 different particle guns
class SimpleGap : public Generator
{
public:
  SimpleGap() {
    // put 2 different generators in the cocktail of generators
    gens.push_back(new o2::eventgen::BoxGenerator(22,10,-5,5,0,10,0,360));
    gens.push_back(new o2::eventgen::BoxGenerator(11,10,-5,5,0,10,0,360));
  }

  ~SimpleGap() = default;

  Bool_t Init() override
  {
    // init all sub-gens
    for (auto gen : gens) {
      gen->Init();
    }
    addSubGenerator(0, "Gun 1"); // name the generators
    addSubGenerator(1, "Gun 2");
    return Generator::Init();
  }

  Bool_t generateEvent() override
  {
    // here we call the individual gun generators in turn
    // (but we could easily call all of them to have cocktails)
    currentindex++;
    currentgen = gens[currentindex % 2];
    currentgen->generateEvent();
    // notify the sub event generator
    notifySubGenerator(currentindex % 2);
    return true;
  }

  // We override this function to import the particles from the
  // underlying generators into **this** generator instance
  Bool_t importParticles() override
  {
    mParticles.clear(); // clear container of mother class
    currentgen->importParticles();
    std::copy(currentgen->getParticles().begin(), currentgen->getParticles().end(), std::back_insert_iterator(mParticles));

    // we need to fix particles statuses --> need to enforce this on the importParticles level of individual generators
    for (auto& p : mParticles) {
      auto st = o2::mcgenstatus::MCGenStatusEncoding(p.GetStatusCode(), p.GetStatusCode()).fullEncoding;
      p.SetStatusCode(st);
      p.SetBit(ParticleStatus::kToBeDone, true);
    }

    return true;
  }

private:
  int currentindex = -1;
  o2::eventgen::BoxGenerator* currentgen = nullptr;
  std::vector<o2::eventgen::BoxGenerator*> gens;
};

} // namespace eventgen
} // namespace o2

/** generator instance and settings **/

FairGenerator* getSimpleGap() {
  return new o2::eventgen::SimpleGap();
}
