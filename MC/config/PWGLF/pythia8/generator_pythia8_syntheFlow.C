
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

class GeneratorPythia8SyntheFlow : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8SyntheFlow() {
    lutGen = new o2::eventgen::FlowMapper();
    
    // -------- CONFIGURE SYNTHETIC FLOW ------------
    // specify a v2 vs pT here
    TFile *filehep = new TFile("/Users/daviddc/Downloads/HEPData-ins1116150-v1-Table_1.root", "READ");
    TH1D *hv = (TH1D*) filehep->Get("Table 1/Hist1D_y6");
    
    TFile *fileEcc = new TFile("/Users/daviddc/Downloads/eccentricityvsb.root", "READ");
    TH1D *hEccentricities = (TH1D*) fileEcc->Get("hEccentricities");
    
    cout<<"Generating LUT for flow test"<<endl;
    lutGen->CreateLUT(hv, hEccentricities);
    cout<<"Finished creating LUT!"<<endl;
    // -------- END CONFIGURE SYNTHETIC FLOW ------------
  }

  ///  Destructor
  ~GeneratorPythia8SyntheFlow() = default;
  
  //__________________________________________________________________
  Bool_t generateEvent() override {
    
    // Generate PYTHIA event
    Bool_t lPythiaOK = kFALSE;
    while (!lPythiaOK){
      lPythiaOK = mPythia.next();
    }
    
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    // loop over the entire event record and rotate all particles
    // synthetic flow exercise
    // first: get event plane
    float eventPlaneAngle = mPythia.info.hiInfo->phi();
    float impactParameter = mPythia.info.hiInfo->b();

    for ( Long_t j=0; j < mPythia.event.size(); j++ ) {
      float pyphi = mPythia.event[j].phi();
      float pypT = mPythia.event[j].pT();

      // calculate delta with EP
      float deltaPhiEP = pyphi - eventPlaneAngle;
      float shift = 0.0;
      while(deltaPhiEP<0.0){
        deltaPhiEP += 2*TMath::Pi();
        shift += 2*TMath::Pi();
      }
      while(deltaPhiEP>2*TMath::Pi()){
        deltaPhiEP -= 2*TMath::Pi();
        shift -= 2*TMath::Pi();
      }
      float newDeltaPhiEP = lutGen->MapPhi(deltaPhiEP, impactParameter, pypT);
      float pyphiNew = newDeltaPhiEP - shift + eventPlaneAngle;

      if(pyphiNew>TMath::Pi())
        pyphiNew -= 2.0*TMath::Pi();
      if(pyphiNew<-TMath::Pi())
        pyphiNew += 2.0*TMath::Pi();
      mPythia.event[j].rot(0.0, pyphiNew-pyphi);
    }
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    
    return true;
  }
  
private:
  o2::eventgen::FlowMapper *lutGen; // for mapping phi angles
};

 FairGenerator *generator_syntheFlow()
 {
   return new GeneratorPythia8SyntheFlow();
 }
