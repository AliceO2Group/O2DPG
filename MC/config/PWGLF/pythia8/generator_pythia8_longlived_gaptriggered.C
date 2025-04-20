
#include "Pythia8/Pythia.h"
#include "Pythia8/HeavyIons.h" // for event plane angle

#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "fairlogger/Logger.h"
#include "CCDB/BasicCCDBManager.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "TSystem.h"
#include "TMath.h"
#include <cmath>
#include <vector>
#include <fstream>
#include <string>
using namespace Pythia8;
#endif

class GeneratorPythia8LongLivedGapTriggered : public o2::eventgen::GeneratorPythia8
{
public:
  /// Constructor
  GeneratorPythia8LongLivedGapTriggered(std::vector<int> input_pdg, int input_trigger_ratio = 1, int n_injected = 1, float pt_min = 1, float pt_max = 10, float y_min = -1, float y_max = 1, bool addSyntheticFlow = false)
  {
    mPdg = input_pdg;
    setNinjected(n_injected);
    mInverseTriggerRatio = input_trigger_ratio;
    setPt(pt_min, pt_max);
    setY(y_min, y_max);
    mMass = getMass(input_pdg);
    mGeneratedEvents = 0;
    mAlternatingPDGsign = true;
    mAddSyntheticFlow = addSyntheticFlow;

    if(mAddSyntheticFlow){ 
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
  }

  /// Constructor from config file
  GeneratorPythia8LongLivedGapTriggered(std::string file_name, int input_trigger_ratio = 1, bool addSyntheticFlow = false)
  {
    auto expanded_file_name = gSystem->ExpandPathName(file_name.c_str());
    std::ifstream config_file(expanded_file_name);
    LOGF(info, "Using configuration file %s", expanded_file_name);
    std::string header;
    int pdg = 0;
    unsigned long n_inj = 0;
    float pt_min = 0.;
    float pt_max = 0.;
    float y_min = 0.;
    float y_max = 0.;
    if (!config_file.is_open())
    {
      LOGF(fatal, "File %s cannot be opened.", expanded_file_name);
    }
    std::getline(config_file, header); // skip first line
    while (config_file >> pdg >> n_inj >> pt_min >> pt_max >> y_min >> y_max)
    {
      mPdg.push_back(pdg);
      mNinjected.push_back(n_inj);
      mPtMin.push_back(pt_min);
      mPtMax.push_back(pt_max);
      mYmin.push_back(y_min);
      mYmax.push_back(y_max);
    }
    config_file.close();
    mInverseTriggerRatio = input_trigger_ratio;
    mMass = getMass(mPdg);
    mGeneratedEvents = 0;
    mAlternatingPDGsign = true;
    mAddSyntheticFlow = addSyntheticFlow;

    if(mAddSyntheticFlow){ 
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
  }

  /// Destructor
  ~GeneratorPythia8LongLivedGapTriggered() = default;

  /// Randomize the PDG code sign of core particle
  void setAlternatingPDGsign(bool val) { mAlternatingPDGsign = val; }

  /// Set transverse momentum
  void setPt(float pt_min, float pt_max)
  {
    for (auto part : mPdg)
    {
      mPtMin.push_back(pt_min);
      mPtMax.push_back(pt_max);
    }
  }

  /// Set rapidity
  void setY(float y_min, float y_max)
  {
    for (auto part : mPdg)
    {
      mYmin.push_back(y_min);
      mYmax.push_back(y_max);
    }
  }

  /// Set pseudorapidity
  void setNinjected(unsigned long n_injected)
  {
    for (auto part : mPdg)
    {
      mNinjected.push_back(n_injected);
    }
  }

  /// Get mass from TParticlePDG
  static std::vector<double> getMass(std::vector<int> input_pdg)
  {
    std::vector<double> mass_vec;
    for (auto pdg : input_pdg)
    {
      double mass = 0;
      if (TDatabasePDG::Instance())
      {
        TParticlePDG *particle = TDatabasePDG::Instance()->GetParticle(pdg);
        if (particle)
        {
          mass = particle->Mass();
        }
        else
        {
          std::cout << "===> Unknown particle requested with PDG " << pdg << ", mass set to 0" << std::endl;
        }
      }
      mass_vec.push_back(mass);
    }
    return mass_vec;
  }

  Bool_t importParticles() override
  {
    GeneratorPythia8::importParticles();
    if (mGeneratedEvents % mInverseTriggerRatio == 0)
    {
      static int sign = 1;
      int injectionIndex = (int)gRandom->Uniform(0, mPdg.size());
      int currentPdg = mPdg[injectionIndex];
      double currentMass = mMass[injectionIndex];
      for (int i = 0; i < mNinjected[injectionIndex]; ++i)
      {
        const double pt = gRandom->Uniform(mPtMin[injectionIndex], mPtMax[injectionIndex]);
        const double rapidity = gRandom->Uniform(mYmin[injectionIndex], mYmax[injectionIndex]);
        const double phi = gRandom->Uniform(0, TMath::TwoPi());
        const double px{pt * std::cos(phi)};
        const double py{pt * std::sin(phi)};
        const double mt{std::hypot(pt, currentMass)};
        const double pz{mt * std::sinh(rapidity)};
        const double et{mt * std::cosh(rapidity)};
        if (mAlternatingPDGsign)
        {
          sign *= 1 - 2 * (gRandom->Uniform() > 0.5);
        }
        mParticles.push_back(TParticle(sign * currentPdg, 1, -1, -1, -1, -1, px, py, pz, et, 0., 0., 0., 0.));
        // make sure status code is encoded properly. Transport flag will be set by default and we have nothing
        // to do since all pushed particles should be tracked.
        o2::mcutils::MCGenHelper::encodeParticleStatusAndTracking(mParticles.back());
      }
    }

    if(mAddSyntheticFlow){
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
    }
    //+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    mGeneratedEvents++;
    return true;
  }

private:
  std::vector<int> mPdg;     /// particle mPdg code
  std::vector<double> mMass; /// particle mass [GeV/c^2]

  std::vector<double> mPtMin; /// minimum transverse momentum for generated particles
  std::vector<double> mPtMax; /// maximum transverse momentum for generated particles
  std::vector<double> mYmin; /// minimum rapidity for generated particles
  std::vector<double> mYmax; /// maximum rapidity for generated particles

  bool mAlternatingPDGsign = true; /// bool to randomize the PDG code of the core particle
  bool mAddSyntheticFlow = false; /// switch to add synthetic flow (requires EP angle from PYTHIA)

  std::vector<int> mNinjected; /// Number of injected particles

  // Control gap-triggering
  unsigned long long mGeneratedEvents; /// number of events generated so far
  int mInverseTriggerRatio;            /// injection gap

  o2::eventgen::FlowMapper *lutGen; // for mapping phi angles
};

///___________________________________________________________
FairGenerator *generateLongLivedGapTriggered(std::vector<int> mPdg, int input_trigger_ratio, int n_injected = 1, float pt_min = 1, float pt_max = 10, float y_min = -1, float y_max = 1, bool alternate_sign = true, bool addSyntheticFlow = false)
{
  auto myGen = new GeneratorPythia8LongLivedGapTriggered(mPdg, input_trigger_ratio, n_injected, pt_min, pt_max, y_min, y_max, addSyntheticFlow);
  myGen->setAlternatingPDGsign(alternate_sign);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}

///___________________________________________________________
FairGenerator *generateLongLivedGapTriggered(std::string config_file_name, int input_trigger_ratio, bool alternate_sign = true, bool addSyntheticFlow = false)
{
  auto myGen = new GeneratorPythia8LongLivedGapTriggered(config_file_name, input_trigger_ratio, addSyntheticFlow);
  myGen->setAlternatingPDGsign(alternate_sign);
  auto seed = (gRandom->TRandom::GetSeed() % 900000000);
  myGen->readString("Random:setSeed on");
  myGen->readString("Random:seed " + std::to_string(seed));
  return myGen;
}
