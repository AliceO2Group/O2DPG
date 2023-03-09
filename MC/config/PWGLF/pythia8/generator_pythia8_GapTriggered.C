#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"

#include <map>
#include <unordered_set>
//#include <utility>	// for std::pair

using namespace Pythia8;

class GeneratorPythia8GapTriggered : public o2::eventgen::GeneratorPythia8{
public:
  /// default constructor
  GeneratorPythia8GapTriggered() = default;
  
  /// constructor
  GeneratorPythia8GapTriggered(int lInputTriggerPDG, int lInputTriggerRatio = 5){
    genMinPt=0.0;
    genMaxPt=20.0;
    genminEta=-0.8;
    genmaxEta=0.8;
    
    lGeneratedEvents=0;
    lTriggerPDG = lInputTriggerPDG;
    lInverseTriggerRatio=lInputTriggerRatio;
    
    cout<<"Initalizing extra PYTHIA object used to generate min-bias events..."<<endl;
    pythiaObjectMinimumBias.readFile("${O2DPG_ROOT}/MC/config/PWGLF/pythia8/pythia8_inel_minbias.cfg");
    pythiaObjectMinimumBias.init();
    cout << "Initalization complete" << endl;
    cout<<"Initalizing extra PYTHIA object used to generate signal events..."<<endl;
    pythiaObjectSignal.readFile("${O2DPG_ROOT}/MC/config/PWGLF/pythia8/pythia8_inel_signal.cfg");
    pythiaObjectSignal.init();
    cout << "Initalization complete" << endl;
  }
  
  ///  Destructor
  ~GeneratorPythia8GapTriggered() = default;
  
protected:
  //__________________________________________________________________
  Bool_t generateEvent() override {
    /// reset event
    mPythia.event.reset();
    
    // Simple straightforward check to alternate generators
    if( lGeneratedEvents % lInverseTriggerRatio == 0 ){
      //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      // Generate event of interest
      cout<<"[gap-triggering] #"<<lGeneratedEvents<<" Generate EoI triggering on pdg: "<<lTriggerPDG<<endl;
      Bool_t lGenerationOK = kFALSE;
      while (!lGenerationOK){
        lGenerationOK = pythiaObjectSignal.next();
        if(!lGenerationOK) continue; // eh not good, try again
        if(lTriggerPDG!=0){
          //Check if triggered condition satisfied
          lGenerationOK = kFALSE;
          for ( Long_t j=0; j < pythiaObjectSignal.event.size(); j++ ) {
            Int_t pypid = pythiaObjectSignal.event[j].id();
            Float_t pyeta = pythiaObjectSignal.event[j].eta();
            if( pypid == lTriggerPDG && genminEta<pyeta && pyeta<genmaxEta){
              lGenerationOK = kTRUE;
              break;
            }
          }
        }
      }
      mPythia.event = pythiaObjectSignal.event;
      //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    }else{
      //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      // Generate minimum-bias event
      Bool_t lGenerationOK = kFALSE;
      cout<<"[gap-triggering] #"<<lGeneratedEvents<<" Generate MB"<<endl;
      while (!lGenerationOK)
        lGenerationOK = pythiaObjectMinimumBias.next();
      mPythia.event = pythiaObjectMinimumBias.event;
      //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    }
    
    lGeneratedEvents++;
    mPythia.next();
    
    return true;
  }

private:
  // Interface to override import particles
  Pythia8::Event mOutputEvent;
  
  // Properties of selection
  int lTriggerPDG;
  double genMinPt;
  double genMaxPt;
  double genminY;
  double genmaxY;
  double genminEta;
  double genmaxEta;
  
  // Control gap-triggering
  Long64_t lGeneratedEvents;
  int lInverseTriggerRatio;
  
  // Base event generators
  Pythia pythiaObjectMinimumBias; ///Minimum bias collision generator
  Pythia pythiaObjectSignal; ///Signal collision generator
};

// Use the 'TriggeredOn' series to select on specific particles
FairGenerator* generateTriggeredOnOmegaCCC(){
  auto myGen = new GeneratorPythia8GapTriggered(4444);
  return myGen;
}

FairGenerator* generateTriggeredOnOmegaCC(){
  auto myGen = new GeneratorPythia8GapTriggered(4432);
  return myGen;
}

FairGenerator* generateTriggeredOnOmegaC(){
  auto myGen = new GeneratorPythia8GapTriggered(4332);
  return myGen;
}

FairGenerator* generateTriggeredOnOmega(){
  auto myGen = new GeneratorPythia8GapTriggered(3334);
  return myGen;
}

FairGenerator* generatePlain(){
  // Use this to just alternate between the two PYTHIA configurations
  auto myGen = new GeneratorPythia8GapTriggered(0);
  return myGen;
}
