
#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h"
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "CCDB/BasicCCDBManager.h"
#include "TH1F.h"
#include "TH1D.h"

#include <map>
#include <unordered_set>

class GeneratorPythia8SyntheFlow : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8SyntheFlow() {
    lutGen = new o2::eventgen::FlowMapper();
    
    // -------- CONFIGURE SYNTHETIC FLOW ------------
    // establish connection to ccdb
    o2::ccdb::CcdbApi ccdb_api;
    ccdb_api.init("https://alice-ccdb.cern.ch");

    // config was placed at midpoint of run 544122, retrieve that
    std::map<string, string> metadataRCT, headers;
    headers = ccdb_api.retrieveHeaders("RCT/Info/RunInformation/544122", metadataRCT, -1);
    int64_t tsSOR = atol(headers["SOR"].c_str());
    int64_t tsEOR = atol(headers["EOR"].c_str());    
    int64_t midRun = 0.5*tsSOR+0.5*tsEOR;

    map<string, string> metadata; // can be empty
    auto list = ccdb_api.retrieveFromTFileAny<TList>("Users/d/ddobrigk/syntheflow", metadata, midRun);
  
    TH1D *hv2vspT = (TH1D*) list->FindObject("hFlowVsPt_ins1116150_v1_Table_1");
    TH1D *heccvsb = (TH1D*) list->FindObject("hEccentricityVsB");
    
    cout<<"Generating LUT for flow test"<<endl;
    lutGen->CreateLUT(hv2vspT, heccvsb);
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
  auto generator = new GeneratorPythia8SyntheFlow();
  gRandom->SetSeed(0);
  generator->readString("Random:setSeed = on");
  generator->readString("Random:seed =" + std::to_string(gRandom->Integer(900000000 - 2) + 1));
  return generator;
 }
