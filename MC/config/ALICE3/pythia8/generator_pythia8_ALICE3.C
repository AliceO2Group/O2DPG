
#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "Pythia8/Pythia.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "TMath.h"
#include <cmath>
using namespace Pythia8;
#endif

// Default pythia8 minimum bias generator
// Please do not change

class GeneratorPythia8ALICE3 : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8ALICE3() {}

  ///  Destructor
  ~GeneratorPythia8ALICE3() = default;
};

 FairGenerator *generator_pythia8_ALICE3() 
 {
   return new GeneratorPythia8ALICE3();
 }