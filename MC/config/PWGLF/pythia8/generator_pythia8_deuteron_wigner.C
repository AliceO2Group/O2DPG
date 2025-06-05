#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "Pythia8/Pythia.h"
#include "TDatabasePDG.h"
#include "TMath.h"
#include "TParticlePDG.h"
#include "TRandom3.h"
#include "TSystem.h"
#include "TH2D.h"
#include "TH1D.h"
#include "TFile.h"
#include "fairlogger/Logger.h"
#include "CCDB/BasicCCDBManager.h"
#include <cmath>
#include <fstream>
#include <string>
#include <vector>
using namespace Pythia8;
#endif

/// Event generator for proton-proton (pp) collisions using Pythia8.
/// (Anti)deuterons are formed via nucleon coalescence modeled using the Wigner density formalism.

class GeneratorPythia8DeuteronWigner : public o2::eventgen::GeneratorPythia8 {
public:
  GeneratorPythia8DeuteronWigner(double sourceRadius = 1.2)
      : o2::eventgen::GeneratorPythia8(), mSourceRadius(sourceRadius) {
    
    // Connect to CCDB and retrieve coalescence probability two-dimensional table
    o2::ccdb::CcdbApi ccdb_api;
    ccdb_api.init("https://alice-ccdb.cern.ch");
          
    mTwoDimCoalProbability = ccdb_api.retrieveFromTFileAny<TH2D>("Users/a/alcaliva/WignerCoalescence/ArgonneProbability/AddedSDWave");

    if (!mTwoDimCoalProbability) {
      LOG(fatal) << "Could not find coalescence probability table in input file!";
    }
  }

  ~GeneratorPythia8DeuteronWigner() override = default;

  bool Init() override {
    addSubGenerator(0, "Pythia8 events with (anti)deuterons formed via coalescence using the Wigner density formalism, provided the coalescence condition is fulfilled");
    return o2::eventgen::GeneratorPythia8::Init();
  }

protected:
  bool generateEvent() override {
    
    if (GeneratorPythia8::generateEvent() && EventHasDeuteron(mPythia.event)) {
      LOG(debug) << ">> A Deuteron was formed!";
    }

    notifySubGenerator(0);
    ++mGeneratedEvents;
    return true;
  }

  bool EventHasDeuteron(Pythia8::Event& event) {

    bool deuteronIsFormed = false;
    const double md = 1.87561294257; // Deuteron mass [GeV]

    std::vector<int> proton_ID, neutron_ID;
    std::vector<int> proton_status, neutron_status;

    for (int iPart = 0; iPart < event.size(); ++iPart) {
      if (event[iPart].status() <= 0) {
        continue;
      }

      int absID = std::abs(event[iPart].id());
      if (absID == 2212) {
        proton_ID.push_back(iPart);
        proton_status.push_back(0);
      } else if (absID == 2112) {
        neutron_ID.push_back(iPart);
        neutron_status.push_back(0);
      }
    }

    int radiusBin = mTwoDimCoalProbability->GetXaxis()->FindBin(mSourceRadius);
    TH1D* prob_vs_q = mTwoDimCoalProbability->ProjectionY("prob_vs_q", radiusBin, radiusBin, "E");
    prob_vs_q->SetDirectory(nullptr);

    for (size_t ip = 0; ip < proton_ID.size(); ip++) {
      if (proton_status[ip] < 0) continue;

      for (size_t in = 0; in < neutron_ID.size(); in++) {
        if (neutron_status[in] < 0) continue;

        int protonID = proton_ID[ip];
        int neutronID = neutron_ID[in];
        int sign_p = event[protonID].id() / std::abs(event[protonID].id());
        int sign_n = event[neutronID].id() / std::abs(event[neutronID].id());
        if (sign_p != sign_n) continue;

        auto p1 = event[protonID].p();
        auto p2 = event[neutronID].p();
        auto p = p1 + p2;
        p1.bstback(p);
        p2.bstback(p);

        Vec4 deltaPVec = p1 - p2;
        double deltaP = 0.5 * deltaPVec.pAbs();

        int binQ = prob_vs_q->FindBin(deltaP);
        
        // Skip underflow and overflow bins
        if (binQ < 1 || binQ > prob_vs_q->GetNbinsX()) {
          continue;
        }
        double coalProb = prob_vs_q->GetBinContent(prob_vs_q->FindBin(deltaP));
        double rndCoalProb = gRandom->Uniform(0.0, 1.0);
        double rndSpinIsospin = gRandom->Uniform(0.0, 1.0);

        if (rndCoalProb < coalProb && rndSpinIsospin < 3.0/8.0) {
          double energy = std::hypot(p.pAbs(), md);
          p.e(energy);
          int deuteronPDG = sign_p * 1000010020;

          event.append(deuteronPDG, 121, 0, 0, 0, 0, 0, 0, p.px(), p.py(), p.pz(), p.e(), md);

          event[protonID].statusNeg();
          event[protonID].daughter1(event.size() - 1);
          proton_status[ip] = -1;

          event[neutronID].statusNeg();
          event[neutronID].daughter1(event.size() - 1);
          neutron_status[in] = -1;

          deuteronIsFormed = true;
        }
      }
    }

    // free allocated memory
    delete prob_vs_q;
    return deuteronIsFormed;
  }

private:
  double mSourceRadius = 1.2;
  uint64_t mGeneratedEvents = 0;
  TH2D* mTwoDimCoalProbability = nullptr;
};

///________________________________________________________________________________________________________
FairGenerator* generateAntideuteronsWignerCoalescence(double sourceRadius = 1.2) {
  auto myGenerator = new GeneratorPythia8DeuteronWigner(sourceRadius);
  auto seed = gRandom->TRandom::GetSeed() % 900000000;
  myGenerator->readString("Random:setSeed on");
  myGenerator->readString("Random:seed " + std::to_string(seed));
  return myGenerator;
}
