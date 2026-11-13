#include "FairGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TRandom.h"

#include <string>
#include <vector>

using namespace o2::eventgen;

namespace o2
{
namespace eventgen
{

class GeneratorLikeSignDimuonGapTriggered : public o2::eventgen::GeneratorPythia8 {
public:

  /// constructor
  GeneratorLikeSignDimuonGapTriggered(int inputTriggerRatio = 3)
  {
    mGeneratedEvents = 0;
    mInverseTriggerRatio = inputTriggerRatio;
    mRequiredMuonMultiplicity = 2;
    mMuonRapidityMin = -4.3;
    mMuonRapidityMax = -2.2;
    mVerbose = false;

    // minimum-bias Pythia8 instance
    auto seed = (gRandom->TRandom::GetSeed() % 900000000);
    TString pathconfigMB = gSystem->ExpandPathName("$O2DPG_MC_CONFIG_ROOT/MC/config/PWGDQ/pythia8/generator/pythia8_inel_cr2.cfg");
    pythiaMBgen.readFile(pathconfigMB.Data());
    pythiaMBgen.readString("Random:setSeed on");
    pythiaMBgen.readString("Random:seed " + std::to_string(seed));
  }
  /// Destructor
  ~GeneratorLikeSignDimuonGapTriggered() = default;

  void setMuonMultiplicity(int n) { mRequiredMuonMultiplicity = n; }
  void setMuonRapidity(double yMin, double yMax)
  {
    mMuonRapidityMin = yMin;
    mMuonRapidityMax = yMax;
  }
  void setVerbose(bool v) { mVerbose = v; }

  protected:

  Bool_t generateEvent() override
  {
    if (mGeneratedEvents % mInverseTriggerRatio == 0) {
      // signal event: keep generating until like-sign dimuon found
      bool genOk = false;
      while (!genOk) {
        mPythia.event.reset();
        genOk = GeneratorPythia8::generateEvent();
        if (genOk) genOk = selectLikeSignDimuon(mPythia.event);
      }
    } else {
      // minimum-bias event from the independent generator
      bool genOk = false;
      pythiaMBgen.event.reset();
      while (!genOk) genOk = pythiaMBgen.next();
      mPythia.event = pythiaMBgen.event;
    }
    mGeneratedEvents++;
    if (mVerbose) mOutputEvent.list();
    return true;
  }

  Bool_t Init() override
  {
    GeneratorPythia8::Init();
    pythiaMBgen.init();
    return true;
  }

  // Accept the event if at least mRequiredMuonMultiplicity muons fall in the rapidity window AND at least one same-sign pair exists among them.
  bool selectLikeSignDimuon(Pythia8::Event& event)
  {
    std::vector<const Pythia8::Particle*> muonsInWindow;
    for (int ipa = 0; ipa < event.size(); ++ipa) {
      if (std::abs(event[ipa].id()) != 13) continue;
      float rap = event[ipa].y();
      if (rap > mMuonRapidityMin && rap < mMuonRapidityMax) {
        muonsInWindow.push_back(&event[ipa]);
      }
    }
    if ((int)muonsInWindow.size() < mRequiredMuonMultiplicity) return false;
    for (size_t i = 0; i < muonsInWindow.size(); ++i) {
      for (size_t j = i + 1; j < muonsInWindow.size(); ++j) {
        if (muonsInWindow[i]->id() * muonsInWindow[j]->id() > 0) return true;
      }
    }
    return false;
  }

  private:
  Pythia8::Event mOutputEvent;

  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;
  Pythia8::Pythia pythiaMBgen;

  int mRequiredMuonMultiplicity;
  double mMuonRapidityMin;
  double mMuonRapidityMax;
  bool mVerbose;
};

} // namespace eventgen
} // namespace o2

FairGenerator* GeneratorLikeSignDimuonGapTriggered_dq(double rapidityMin = -4.3, double rapidityMax = -2.2, int requiredMuons = 2, int inputTriggerRatio = 3, bool verbose = false)
{
  auto gen = new o2::eventgen::GeneratorLikeSignDimuonGapTriggered(inputTriggerRatio);
  gen->setMuonMultiplicity(requiredMuons);
  gen->setMuonRapidity(rapidityMin, rapidityMax);
  gen->setVerbose(verbose);

  // random seed
  gen->readString("Random:setSeed on");
  uint random_seed;
  unsigned long long int random_value = 0;
  std::ifstream urandom("/dev/urandom", std::ios::in | std::ios::binary);
  urandom.read(reinterpret_cast<char*>(&random_value), sizeof(random_seed));
  gen->readString(Form("Random:seed = %d", random_value % 900000001));

  return gen;
}
