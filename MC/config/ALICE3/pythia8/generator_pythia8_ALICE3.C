#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "Pythia8/Pythia.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include <stdlib.h>

using namespace Pythia8;
#endif

// Default pythia8 minimum bias generator

class GeneratorPythia8ALICE3 : public o2::eventgen::GeneratorPythia8
{
public:

  /// Constructor
  GeneratorPythia8ALICE3() {

    char* job_id = getenv("JOB_ID");
    int seed;

    if (job_id != NULL) {
      LOG(info) << "Seed set to JOB_ID: " << seed;
      seed = atoi(job_id);
    } else {
      LOG(info) << "Unable to retrieve JOB_ID";
      LOG(info) << "Setting seed to 0 (random)";
      seed = 0;
    }

    mPythia.readString("Random:seed = "+std::to_string(seed));
  }

  ///  Destructor
  ~GeneratorPythia8ALICE3() = default;

};

 FairGenerator *generator_pythia8_ALICE3() 
 {
   return new GeneratorPythia8ALICE3();
 }