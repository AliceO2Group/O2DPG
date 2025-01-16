#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "Pythia8/Pythia.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/Trigger.h"
#include <Generators/TriggerExternalParam.h>
#include "Generators/GeneratorPythia8.h"
#include <stdlib.h>
#include "CommonUtils/ConfigurationMacroHelper.h"

using namespace Pythia8;
#endif

// Basic implementation of deep-triggered Pythia8 as external generator

class GeneratorPythia8Deep : public o2::eventgen::GeneratorPythia8
{
  // Settings are fed via the configuration file specified in the .ini file
  // Triggers need to be handled like this otherwise the simulation with hybrid will
  // not be able to recognise the provided triggers.

public :

  GeneratorPythia8Deep() : o2::eventgen::GeneratorPythia8()
  {
    mInterface = reinterpret_cast<void *>(&mPythia);
    mInterfaceName = "pythia8";
    o2::eventgen::DeepTrigger deeptrigger = nullptr;

    // external trigger via ini file
    auto &params = o2::eventgen::TriggerExternalParam::Instance();
    LOG(info) << "Setting up external trigger for Pythia8 with following parameters";
    LOG(info) << params;
    auto external_trigger_filename = params.fileName;
    auto external_trigger_func = params.funcName;
    deeptrigger = o2::conf::GetFromMacro<o2::eventgen::DeepTrigger>(external_trigger_filename, external_trigger_func, "o2::eventgen::DeepTrigger", "deeptrigger");
    if (!deeptrigger)
    {
      LOG(fatal) << "Failed to retrieve \'external trigger\': problem with configuration ";
    } else {
      LOG(info) << "External trigger for Pythia8 is set";
      addDeepTrigger(deeptrigger);
      setTriggerMode(o2::eventgen::Generator::kTriggerOR);
    }
  }
};

FairGenerator *generator_pythia8_deep()
{
  return new GeneratorPythia8Deep();
}