/// Select π⁰ and η within a given rapidity window for enhancement
/// pdgPartForAccCut: PDG of the particle to select (111=π⁰, 221=η)
/// minNb: minimum number of such particles per event for enhancement

////  authors: Rashi Gupta (rashi.gupta@cern.ch)
///  authors: Ravindra Singh (ravindra.singh@cern.ch)


#if !defined(__CLING__) || defined(__ROOTCLING__)
#include "FairGenerator.h"
#include "FairPrimaryGenerator.h"
#include "Generators/GeneratorPythia8.h"
#include "TRandom3.h"
#include "TParticlePDG.h"
#include "TDatabasePDG.h"
#include "TMath.h"
#include <cmath>
#include <vector>
#endif

#include "Pythia8/Pythia.h"
using namespace Pythia8;

class GeneratorPythia8Box : public o2::eventgen::GeneratorPythia8
{
public:
  
  GeneratorPythia8Box(std::vector<int> pdgList, int nInject = 3, float ptMin = 0.1, float ptMax = 50.0, float etaMin = -0.8, float etaMax = 0.8) 
    : mPdgList(pdgList), nParticles(nInject), genMinPt(ptMin), genMaxPt(ptMax), genMinEta(etaMin), genMaxEta(etaMax)
  {
  }

  ~GeneratorPythia8Box() = default;

Bool_t generateEvent() override
{
  bool hasElectron = false; 

  while (!hasElectron) {
    mPythia.event.reset();

    for (int i{0}; i < nParticles; ++i)
    {
      int currentPdg = mPdgList[gRandom->Integer(mPdgList.size())];
      double mass = TDatabasePDG::Instance()->GetParticle(currentPdg)->Mass();

      const double pt = gRandom->Uniform(genMinPt, genMaxPt);
      const double eta = gRandom->Uniform(genMinEta, genMaxEta);
      const double phi = gRandom->Uniform(0, TMath::TwoPi());

      const double px{pt * std::cos(phi)};
      const double py{pt * std::sin(phi)};
      const double pz{pt * std::sinh(eta)};
      const double et{std::hypot(std::hypot(pt, pz), mass)};

    
      mPythia.event.append(currentPdg, 11, 0, 0, px, py, pz, et, mass);
    }

   
    if (!mPythia.next()) continue;

  
    for (int i = 0; i < mPythia.event.size(); ++i) {
      if (std::abs(mPythia.event[i].id()) == 11) {
        
      
        double childPt = mPythia.event[i].pT();
        double childEta = mPythia.event[i].eta();

        if (childPt > 0.1 && std::abs(childEta) < 1.2) {
          hasElectron = true; // Mil gaya!
          break; 
        }
      }
    }
  
  }

  return true; 
}

private:
  std::vector<int> mPdgList;
  double genMinPt, genMaxPt;
  double genMinEta, genMaxEta;
  int nParticles;
};


FairGenerator *generatePythia8Box(float ptMin = 0.1, float ptMax = 50.0)
{

  std::vector<int> pdgList = {111, 221};
  return new GeneratorPythia8Box(pdgList, 3, ptMin, ptMax, -0.8, 0.8);
}
