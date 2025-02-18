R__ADD_INCLUDE_PATH($O2DPG_MC_CONFIG_ROOT)
///#include "FairGenerator.h"
//#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "MC/config/PWGGAJE/hooks/jets_hook.C"
//#include "TRandom.h"
//#include <fairlogger/Logger.h>
//
//#include <string>
//#include <vector>

// Jet-jet custom event generator
// that alternates between 2 gun generators. 
// set up to inject MB events alongside jet-jet events
// in 'MB-gap' mode.
// The number of MB events injected, and the PYTHIA config
// for each event type is defined by the user in the .ini 
// generator file (e.g. GeneratorJE_gapgen5_hook.ini)
//
// Author: Jaime Norman (jaime.norman@cern.ch)

// o2-sim-dpl-eventgen --nEvents 10 --generator external --configKeyValues "GeneratorExternal.fileName=generator_pythia8_gaptrigger_jets_pythiabase.C;GeneratorExternal.funcName=getGeneratorPythia8GapGenJE()"

namespace o2
{
namespace eventgen
{

using namespace Pythia8;


/// A very simple gap generator alternating between 2 different particle guns
class GeneratorPythia8GapGenJE : public o2::eventgen::GeneratorPythia8
{
public:
  /// default constructor
  GeneratorPythia8GapGenJE(int inputTriggerRatio = 5,std::string pathMB = "",std::string pathSignal = "") {

    mGeneratedEvents = 0;
    mInverseTriggerRatio = inputTriggerRatio;

    auto seed = (gRandom->TRandom::GetSeed() % 900000000);

    cout << "Initalizing extra PYTHIA object used to generate min-bias events..." << endl;
    TString pathconfigMB = gSystem->ExpandPathName(TString(pathMB));
    pythiaObjectMinimumBias.readFile(pathconfigMB.Data());
    pythiaObjectMinimumBias.readString("Random:setSeed on");
    pythiaObjectMinimumBias.readString("Random:seed " + std::to_string(seed));
    pythiaObjectMinimumBias.init();
    cout << "Initalization complete" << endl;
    cout << "Initalizing extra PYTHIA object used to generate signal events..." << endl;
    TString pathconfigSignal = gSystem->ExpandPathName(TString(pathSignal));
    pythiaObjectSignal.readFile(pathconfigSignal.Data());
    pythiaObjectSignal.readString("Random:setSeed on");
    pythiaObjectSignal.readString("Random:seed " + std::to_string(seed));
    // load jet hook to ensure at least one jet is within detector acceptance
    Pythia8::UserHooks *hook = pythia8_userhooks_jets();
    pythiaObjectSignal.setUserHooksPtr(std::shared_ptr<Pythia8::UserHooks>(hook));
    pythiaObjectSignal.init();
    cout << "Initalization complete" << endl;
    // Add Sub generators
    addSubGenerator(0, "MB generator");
    addSubGenerator(1, "jet-jet generator");
  }


  ///  Destructor
  ~GeneratorPythia8GapGenJE() = default;

  void setUsedSeed(unsigned int seed)
  {
    mUsedSeed = seed;
  };
  unsigned int getUsedSeed() const
  {
    return mUsedSeed;
  };

  bool generateEvent() override
  {

    // Simple straightforward check to alternate generators
    mPythia.event.reset();

    if (mGeneratedEvents % mInverseTriggerRatio == 0) {
      LOG(info) << "Event " <<  mGeneratedEvents << ", generate signal event";
      // Generate event of interest
      Bool_t mGenerationOK = kFALSE;
      while (!mGenerationOK) {
        mGenerationOK = pythiaObjectSignal.next();
      }
      mPythia.event = pythiaObjectSignal.event;
      setEventHeaderProperties(pythiaObjectSignal);
      LOG(info) << "--- Print info properties custom...";
      printEventHeaderProperties(pythiaObjectSignal);
      notifySubGenerator(1);
    } 
    else {
      LOG(info) << "Event " <<  mGeneratedEvents << ", generate mb event";
      // Generate minimum-bias event
      Bool_t mGenerationOK = kFALSE;
      while (!mGenerationOK) {
        mGenerationOK = pythiaObjectMinimumBias.next();
      }
      mPythia.event = pythiaObjectMinimumBias.event;
      setEventHeaderProperties(pythiaObjectMinimumBias);
      LOG(info) << "--- Print info properties custom...";
      printEventHeaderProperties(pythiaObjectMinimumBias);
      notifySubGenerator(0);
    }
    mGeneratedEvents++;
    return true;
  }

  // for testing
  void printEventHeaderProperties (Pythia8::Pythia &pythiaObject) {
    LOG(info) << "Info name = " << pythiaObject.info.name();
    LOG(info) << "Info code = " << pythiaObject.info.code();
    LOG(info) << "Info weight = " << pythiaObject.info.weight();
    LOG(info) << "Info id1pdf = " << pythiaObject.info.id1pdf();
    LOG(info) << "Info id2pdf = " << pythiaObject.info.id2pdf();

    LOG(info) << "Info x1pdf = " << pythiaObject.info.x1pdf();
    LOG(info) << "Info x2pdf = " << pythiaObject.info.x2pdf();
    LOG(info) << "Info QFac = " << pythiaObject.info.QFac();
    LOG(info) << "Info pdf1 = " << pythiaObject.info.pdf1();
    LOG(info) << "Info pdf2 = " << pythiaObject.info.pdf2();

    // Set cross section
    LOG(info) << "Info sigmaGen = " << pythiaObject.info.sigmaGen();
    LOG(info) << "Info sigmaErr = " << pythiaObject.info.sigmaErr();

    // Set event scale and nMPI
    LOG(info) << "Info QRen = " << pythiaObject.info.QRen();
    LOG(info) << "Info nMPI = " << pythiaObject.info.nMPI();

    // Set accepted and attempted values
    LOG(info) << "Info accepted = " << pythiaObject.info.nAccepted();
    LOG(info) << "Info attempted = " << pythiaObject.info.nTried();

    // Set weights (overrides cross-section for each weight)
    size_t iw = 0;
    auto xsecErr = pythiaObject.info.weightContainerPtr->getTotalXsecErr();
    for (auto w : pythiaObject.info.weightContainerPtr->getTotalXsec()) {
      std::string post = (iw == 0 ? "" : "_" + std::to_string(iw));
      LOG(info) << "Info weight by index = " << pythiaObject.info.weightValueByIndex(iw);
      iw++;
    }

  }

  // in order to save the event weight we need to override the following function
  // from the inherited o2::eventgen::GeneratorPythia8 class. The event header properties
  // are created as members of this class, and are set using the active event generator
  // (MB or jet-jet), then propagated to the event header
  void updateHeader(o2::dataformats::MCEventHeader* eventHeader) override {
    /** update header **/
    using Key = o2::dataformats::MCInfoKeys;

    eventHeader->putInfo<std::string>(Key::generator, "pythia8");
    eventHeader->putInfo<int>(Key::generatorVersion, PYTHIA_VERSION_INTEGER);
    eventHeader->putInfo<std::string>(Key::processName, name);
    eventHeader->putInfo<int>(Key::processCode, code);
    eventHeader->putInfo<float>(Key::weight, weight);

    // Set PDF information
    eventHeader->putInfo<int>(Key::pdfParton1Id, id1pdf);
    eventHeader->putInfo<int>(Key::pdfParton2Id, id2pdf);
    eventHeader->putInfo<float>(Key::pdfX1, x1pdf);
    eventHeader->putInfo<float>(Key::pdfX2, x2pdf);
    eventHeader->putInfo<float>(Key::pdfScale, QFac);
    eventHeader->putInfo<float>(Key::pdfXF1, pdf1);
    eventHeader->putInfo<float>(Key::pdfXF2, pdf2);

    // Set cross section
    eventHeader->putInfo<float>(Key::xSection, sigmaGen * 1e9);
    eventHeader->putInfo<float>(Key::xSectionError, sigmaErr * 1e9);

    // Set event scale and nMPI
    eventHeader->putInfo<float>(Key::eventScale, QRen);
    eventHeader->putInfo<int>(Key::mpi, nMPI);

    // Set accepted and attempted events
    eventHeader->putInfo<int>(Key::acceptedEvents, accepted);
    eventHeader->putInfo<int>(Key::attemptedEvents, attempted);

    LOG(info) << "--- updated header weight = " << weight;

    // The following is also set in the base class updateHeader function
    // but as far as I can tell, there is no Xsec weight in the default
    // header so this is not copied over for now

    //size_t iw = 0;
    //auto xsecErr = info.weightContainerPtr->getTotalXsecErr();
    //for (auto w : info.weightContainerPtr->getTotalXsec()) {
    //  std::string post = (iw == 0 ? "" : "_" + std::to_string(iw));
    //  eventHeader->putInfo<float>(Key::weight + post, info.weightValueByIndex(iw));
    //  eventHeader->putInfo<float>(Key::xSection + post, w * 1e9);
    //  eventHeader->putInfo<float>(Key::xSectionError + post, xsecErr[iw] * 1e9);
    //  iw++;
    //}
  }

  void setEventHeaderProperties (Pythia8::Pythia &pythiaObject) {

    auto& info = pythiaObject.info;

    name = info.name();
    code = info.code();
    weight = info.weight();
    // Set PDF information
    id1pdf = info.id1pdf();
    id2pdf = info.id2pdf();
    x1pdf = info.x1pdf();
    x2pdf = info.x2pdf();
    QFac = info.QFac();
    pdf1 = info.pdf1();
    pdf2 = info.pdf2();
    // Set cross section
    sigmaGen = info.sigmaGen();
    sigmaErr = info.sigmaErr();
    // Set event scale and nMPI
    QRen = info.QRen();
    nMPI = info.nMPI();
    // Set accepted and attempted events
    accepted = info.nAccepted();
    attempted = info.nTried();
  }

private:
  // Interface to override import particles
  Pythia8::Event mOutputEvent;

  // Properties of selection
  unsigned int mUsedSeed;

  // Control gap-triggering
  unsigned long long mGeneratedEvents;
  int mInverseTriggerRatio;

  // Handling generators
  Pythia8::Pythia pythiaObjectMinimumBias;
  Pythia8::Pythia pythiaObjectSignal;

  // header info - needed to save event properties 
  std::string  name;
  int  code;
  float  weight;
  // PDF information
  int  id1pdf;
  int  id2pdf;
  float  x1pdf;
  float  x2pdf;
  float  QFac;
  float  pdf1;
  float  pdf2;
  // cross section
  float  sigmaGen;
  float  sigmaErr;
  // event scale and nMPI
  float  QRen;
  int  nMPI;
  // accepted and attempted events
  int  accepted;
  int  attempted;
};

} // namespace eventgen
} // namespace o2

/** generator instance and settings **/

FairGenerator* getGeneratorPythia8GapGenJE(int inputTriggerRatio = 5, std::string pathMB = "",std::string pathSignal = "") {
  auto myGen = new o2::eventgen::GeneratorPythia8GapGenJE(inputTriggerRatio, pathMB, pathSignal);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->setUsedSeed(seed);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  myGen->readString("HardQCD:all = on");
  return myGen;
}
