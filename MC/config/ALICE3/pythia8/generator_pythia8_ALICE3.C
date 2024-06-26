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

    char* alien_proc_id = getenv("ALIEN_PROC_ID");
    uint64_t seedFull;
    uint64_t seed = 0;

    if (alien_proc_id != NULL) {
      seedFull = static_cast<uint64_t>(atol(alien_proc_id));
      for(int ii=0; ii<29; ii++) // there might be a cleaner way but this will work
        seed |= ((seedFull) & (static_cast<uint64_t>(1) << static_cast<uint64_t>(ii)));
      LOG(info) << "Value of ALIEN_PROC_ID: " << seedFull <<" truncated to 0-28 bits: "<<seed<<endl;
    } else {
      LOG(info) << "Unable to retrieve ALIEN_PROC_ID";
      LOG(info) << "Setting seed to 0 (random)";
      seed = 0;
    }
    mPythia.readString("Random:seed = "+std::to_string(static_cast<int>(seed)));
  }

  ///  Destructor
  ~GeneratorPythia8ALICE3() = default;

};

 FairGenerator *generator_pythia8_ALICE3() 
 {
   return new GeneratorPythia8ALICE3();
 }
